-- Sandboxed, per-application saves. No desktop paths and no executable save data.
return function(R)
    local B=R.builtins
    local fs=love and love.filesystem
    local memory=R.options.storage or {}
    local handles,nextHandle={},1
    local ini=nil
    local replace=os.rename
    if fs and love.system.getOS()=="Windows" then
        -- Windows C rename does not replace an existing destination. Use the
        -- Unicode replace API through the LuaJIT bundled with official LOVE.
        local ffi=require("ffi")
        ffi.cdef[[
            int __stdcall MultiByteToWideChar(unsigned int, unsigned long, const char*, int, uint16_t*, int);
            int __stdcall MoveFileExW(const uint16_t*, const uint16_t*, unsigned long);
            unsigned long __stdcall GetLastError(void);
        ]]
        local kernel=ffi.load("kernel32")
        local function wide(s)
            local n=kernel.MultiByteToWideChar(65001,0,s,-1,nil,0)
            if n==0 then error("Cannot encode Windows save path") end
            local buffer=ffi.new("uint16_t[?]",n)
            if kernel.MultiByteToWideChar(65001,0,s,-1,buffer,n)==0 then error("Cannot encode Windows save path") end
            return buffer
        end
        replace=function(from,to)
            if kernel.MoveFileExW(wide(from),wide(to),9)~=0 then return true end -- REPLACE_EXISTING | WRITE_THROUGH
            return nil,"Windows error "..tonumber(kernel.GetLastError())
        end
    end
    local function path(name)
        if type(name)~="string" then error("Save path must be a string") end
        name=name:gsub("\\","/")
        if name=="" or name:sub(1,1)=="/" or name:find(":",1,true) or name:find("%z") then error("Unsafe save path") end
        for part in name:gmatch("[^/]+") do if part==".." or part=="." then error("Save path traversal rejected") end end
        return name
    end
    local function read(name)
        name=path(name)
        if memory[name]~=nil then return memory[name] end
        if fs then return fs.read(name) end
    end
    local function write(name,data)
        name=path(name)
        if not fs then memory[name]=data;return true end
        local dir=name:match("^(.*)/")
        if dir then assert(fs.createDirectory(dir)) end
        -- Keep the old save if the device loses power partway through writing.
        local temp=name..".tmp"
        local ok,err=fs.write(temp,data)
        if not ok then error("Cannot write save: "..tostring(err)) end
        local save=fs.getSaveDirectory()
        local renamed,why=replace(save.."/"..temp,save.."/"..name)
        if not renamed then error("Cannot replace save atomically: "..tostring(why)) end
        return true
    end
    local function exists(name) return read(name)~=nil end
    B.file_exists=function(_,name) return R.num(exists(name)) end
    B.file_delete=function(_,name)
        name=path(name);memory[name]=nil
        return fs and R.num(fs.remove(name)) or 1
    end
    B.file_rename=function(_,from,to)
        from,to=path(from),path(to)
        local data=read(from)
        if not data then return 0 end
        write(to,data)
        memory[from]=nil;if fs then fs.remove(from) end
        return 1
    end
    local function open(name,mode)
        name=path(name)
        local data=mode=="w" and "" or read(name)
        if data==nil then return -1 end
        local id=nextHandle;nextHandle=nextHandle+1
        handles[id]={name=name,mode=mode,data=data,pos=1}
        return id
    end
    local function handle(id,mode)
        local h=handles[id]
        if not h or (mode and h.mode~=mode) then error("Invalid "..tostring(mode or "").." file handle "..tostring(id)) end
        return h
    end
    B.file_text_open_read=function(_,name) return open(name,"r") end
    B.file_text_open_write=function(_,name) return open(name,"w") end
    B.file_text_close=function(_,id)
        local h=handle(id)
        if h.mode=="w" then write(h.name,h.data) end
        handles[id]=nil
    end
    B.file_text_eof=function(_,id) local h=handle(id,"r");return R.num(h.pos>#h.data) end
    B.file_text_read_string=function(_,id)
        local h=handle(id,"r");local e=h.data:find("[\r\n]",h.pos) or #h.data+1
        local s=h.data:sub(h.pos,e-1);h.pos=e;return s
    end
    B.file_text_readln=function(_,id)
        local h=handle(id,"r");local e=h.data:find("\n",h.pos,true)
        h.pos=e and e+1 or #h.data+1
    end
    B.file_text_read_real=function(_,id)
        local h=handle(id,"r")
        local start,ending,number=h.data:find("^%s*([+-]?[%d.]+[eE]?[+-]?%d*)",h.pos)
        if not start then return 0 end
        h.pos=ending+1;return tonumber(number) or 0
    end
    local function append(id,text) local h=handle(id,"w");h.data=h.data..text end
    B.file_text_write_string=function(_,id,text) append(id,tostring(text)) end
    B.file_text_write_real=function(_,id,number) append(id,string.format("%.15g",number)) end
    B.file_text_writeln=function(_,id) append(id,"\n") end
    local function trim(s) return s:match("^%s*(.-)%s*$") end
    local function serialize(document)
        local sections={};for name in pairs(document) do sections[#sections+1]=name end;table.sort(sections)
        local lines={}
        for _,name in ipairs(sections) do
            lines[#lines+1]="["..name.."]"
            local keys={};for k in pairs(document[name]) do keys[#keys+1]=k end;table.sort(keys)
            for _,k in ipairs(keys) do lines[#lines+1]=k.."="..document[name][k] end
            lines[#lines+1]=""
        end
        return table.concat(lines,"\n")
    end
    B.ini_close=function()
        if ini and ini.dirty then write(ini.name,serialize(ini.data)) end
        ini=nil
    end
    B.ini_open=function(_,name)
        B.ini_close()
        name=path(name)
        ini={name=name,data={},dirty=false}
        local data=read(name) or ""
        local section=""
        for line in (data.."\n"):gmatch("([^\n]*)\n") do
            line=trim(line)
            local s=line:match("^%[(.-)%]$")
            if s then section=s;ini.data[section]=ini.data[section] or {}
            elseif line:sub(1,1)~=";" and line:sub(1,1)~="#" then
                local k,v=line:match("^([^=]+)=(.*)$")
                if k then
                    v=trim(v)
                    if v:sub(1,1)=='"' and v:sub(-1)=='"' then v=v:sub(2,-2) end
                    ini.data[section]=ini.data[section] or {};ini.data[section][trim(k)]=v
                end
            end
        end
    end
    local function get(section,key,default)
        if not ini then error("INI access before ini_open") end
        return ini.data[section] and ini.data[section][key] or default
    end
    B.ini_read_real=function(_,section,key,default) return tonumber(get(section,key,default)) or default end
    B.ini_read_string=function(_,section,key,default) return tostring(get(section,key,default)) end
    B.ini_section_exists=function(_,section) return R.num(ini and ini.data[section]~=nil) end
    local function put(section,key,value)
        if not ini then error("INI write before ini_open") end
        if tostring(value):find("[\r\n]") or section:find("[\r\n%]]") or key:find("[\r\n=]") then error("Invalid INI value") end
        ini.data[section]=ini.data[section] or {};ini.data[section][key]=tostring(value);ini.dirty=true
    end
    B.ini_write_real=function(_,section,key,value) put(section,key,string.format("%.15g",value)) end
    B.ini_write_string=function(_,section,key,value) put(section,key,value) end
    function R:flushSaves()
        B.ini_close()
        for id,h in pairs(handles) do if h.mode=="w" then write(h.name,h.data);handles[id]=nil end end
    end
    R.saveMemory=memory
end
