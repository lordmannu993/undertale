-- Asset IDs and playback-instance IDs are distinct, like GameMaker audio.
return function(R)
    local B=R.builtins
    local audio=love and love.audio
    R.audioState={voices={},defaults={},templates={},next=10000000,max=128}
    local A=R.audioState
    local function settings(asset)
        A.defaults[asset]=A.defaults[asset] or {gain=1,pitch=1}
        return A.defaults[asset]
    end
    local function each(target,fn)
        if A.voices[target] then fn(A.voices[target]);return end
        for _,v in pairs(A.voices) do if v.asset==target then fn(v) end end
    end
    local function gain(v,value)
        v.gain=value
        if v.source then v.source:setVolume(math.max(0,math.min(1,value))) end
    end
    B.audio_channel_num=function(_,n) A.max=math.max(1,math.floor(n)) end
    B.audio_play_sound=function(_,asset,priority,loop)
        local def=R.assets.sounds[asset]
        if not def then R:warn("sound:"..tostring(asset),"Unresolved sound ID "..tostring(asset).."; this cue is unavailable.");return -1 end
        local active=0;local victim
        for id,v in pairs(A.voices) do active=active+1;if not victim or v.priority<A.voices[victim].priority or (v.priority==A.voices[victim].priority and id<victim) then victim=id end end
        if active>=A.max and victim then
            if A.voices[victim].priority>priority then return -1 end
            if A.voices[victim].source then A.voices[victim].source:stop();A.voices[victim].source:release() end
            A.voices[victim]=nil
        end
        local source
        if audio and not R.options.headless then
            local isStream=def.file:match("%.ogg$") or def.file:match("%.mp3$") or def.name:sub(1,4)=="mus_"
            local ok,result=pcall(function()
                if isStream then return audio.newSource(def.file,"stream") end
                if not A.templates[asset] then A.templates[asset]=audio.newSource(def.file,"static") end
                return A.templates[asset]:clone()
            end)
            if not ok then R:warn("sound-file:"..def.file,"Cannot play "..def.file..": "..tostring(result));return -1 end
            source=result
        end
        local s=settings(asset)
        local id=A.next;A.next=A.next+1
        local v={asset=asset,priority=priority,loop=R.truth(loop),source=source,gain=s.gain*(def.volume or 1),pitch=s.pitch,paused=false,position=0}
        A.voices[id]=v
        if source then source:setLooping(v.loop);gain(v,v.gain);source:setPitch(math.max(0.01,v.pitch));source:play() end
        return id
    end
    B.audio_stop_sound=function(_,target)
        local remove={}
        if A.voices[target] then remove[1]=target else for id,v in pairs(A.voices) do if v.asset==target then remove[#remove+1]=id end end end
        for _,id in ipairs(remove) do local v=A.voices[id];if v.source then v.source:stop();v.source:release() end;A.voices[id]=nil end
    end
    B.audio_stop_all=function()
        for _,v in pairs(A.voices) do if v.source then v.source:stop();v.source:release() end end
        A.voices={}
    end
    B.audio_pause_sound=function(_,target) each(target,function(v) v.paused=true;if v.source then v.source:pause() end end) end
    B.audio_resume_sound=function(_,target) each(target,function(v) v.paused=false;if v.source and not v.appPaused then v.source:play() end end) end
    B.audio_is_playing=function(_,target)
        local playing=false
        each(target,function(v) if not v.paused and not v.appPaused and (not v.source or v.source:isPlaying()) then playing=true end end)
        return R.num(playing)
    end
    B.audio_sound_gain=function(_,target,value,milliseconds)
        value=math.max(0,value)
        if not A.voices[target] then settings(target).gain=value end
        each(target,function(v)
            if milliseconds and milliseconds>0 then v.fade={from=v.gain,to=value,duration=milliseconds/1000,t=0}
            else v.fade=nil;gain(v,value) end
        end)
    end
    B.audio_sound_pitch=function(_,target,pitch)
        if not A.voices[target] then settings(target).pitch=pitch end
        each(target,function(v) v.pitch=pitch;if v.source then v.source:setPitch(math.max(0.01,pitch)) end end)
    end
    B.audio_sound_get_gain=function(_,target) return A.voices[target] and A.voices[target].gain or settings(target).gain end
    B.audio_sound_get_pitch=function(_,target) return A.voices[target] and A.voices[target].pitch or settings(target).pitch end
    B.audio_sound_get_track_position=function(_,target)
        local position=0;each(target,function(v) position=v.source and v.source:tell("seconds") or v.position end);return position
    end
    B.audio_sound_set_track_position=function(_,target,position) each(target,function(v) v.position=position;if v.source then v.source:seek(position,"seconds") end end) end
    function R:updateAudio(dt)
        local remove={}
        for id,v in pairs(A.voices) do
            if not v.paused and not v.appPaused then
                v.position=v.position+dt*v.pitch
                if v.fade then local f=v.fade;f.t=math.min(f.duration,f.t+dt);gain(v,f.from+(f.to-f.from)*f.t/f.duration);if f.t>=f.duration then v.fade=nil end end
                if v.source and not v.source:isPlaying() then remove[#remove+1]=id end
            end
        end
        for _,id in ipairs(remove) do local v=A.voices[id];if v.source then v.source:release() end;A.voices[id]=nil end
    end
    function R:suspendAudio()
        for _,v in pairs(A.voices) do v.appPaused=true;if v.source then v.source:pause() end end
    end
    function R:resumeAudio()
        for _,v in pairs(A.voices) do
            if v.appPaused then v.appPaused=false;if v.source and not v.paused then v.source:play() end end
        end
    end
    function R:trimAudioCache()
        for _,source in pairs(A.templates) do source:release() end
        A.templates={}
    end
    function R:releaseAudio()
        B.audio_stop_all()
        self:trimAudioCache()
    end
end
