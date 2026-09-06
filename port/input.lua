-- Source-owned keyboard state. Touch, hardware keys and gamepad buttons never
-- release one another. Edges are consumed by GAME ticks, not display frames.
local Input = {}
Input.__index = Input

local function copy(t)
    local r = {}; for k, v in pairs(t) do r[k] = v end; return r
end
local keycodes = {
    backspace=8, tab=9, return_=13, kpenter=13, lshift=16, rshift=16,
    lctrl=17, rctrl=17, lalt=18, ralt=18, pause=19, capslock=20,
    escape=27, space=32, pageup=33, pagedown=34, ["end"]=35, home=36,
    left=37, up=38, right=39, down=40, insert=45, delete=46,
    kp0=96, kp1=97, kp2=98, kp3=99, kp4=100, kp5=101, kp6=102,
    kp7=103, kp8=104, kp9=105, ["kp*"]=106, ["kp+"]=107, ["kp-"]=109,
    ["kp."]=110, ["kp/"]=111,
}
keycodes["return"] = 13
for i=1,12 do keycodes["f"..i] = 111+i end
for i=65,90 do keycodes[string.char(i+32)] = i end
for i=48,57 do keycodes[string.char(i)] = i end
Input.keycodes = keycodes

function Input.new()
    return setmetatable({sources={}, mapping={}, raw={}, logical={}, pendingDown={}, pendingUp={},
        pendingRawDown={}, pendingRawUp={}, down={}, pressed={}, released={}, direct={},
        directPressed={}, directReleased={}, suppressed={}, inFrame=false, lastkey=0}, Input)
end

local function collect(sources, mapping)
    local raw, mapped = {}, {}
    for _, keys in pairs(sources) do
        for key in pairs(keys) do
            raw[key] = true
            mapped[mapping[key] or key] = true
        end
    end
    return raw, mapped
end

function Input:recompute()
    local raw, logical = collect(self.sources, self.mapping)
    local function edges(old, new, pd, pu, frame, fp, fr)
        for k in pairs(new) do
            if not old[k] then
                pd[k] = true
                if self.inFrame then frame[k], fp[k], fr[k] = true, true, nil; pd[k] = nil end
                self.lastkey = k
            end
        end
        for k in pairs(old) do
            if not new[k] then
                pu[k] = true
                if self.inFrame then frame[k], fr[k] = nil, true; pu[k] = nil end
            end
        end
    end
    edges(self.raw, raw, self.pendingRawDown, self.pendingRawUp, self.direct, self.directPressed, self.directReleased)
    edges(self.logical, logical, self.pendingDown, self.pendingUp, self.down, self.pressed, self.released)
    self.raw, self.logical = raw, logical
    for k in pairs(self.suppressed) do if not logical[k] then self.suppressed[k] = nil end end
end

function Input:setSource(source, keys)
    local set = {}
    for _, key in ipairs(keys or {}) do set[key] = true end
    self.sources[source] = next(set) and set or nil
    self:recompute()
end

function Input:releasePrefix(prefix)
    for source in pairs(self.sources) do
        if source:sub(1,#prefix) == prefix then self.sources[source] = nil end
    end
    self:recompute()
end

function Input:keypressed(key, isrepeat)
    if isrepeat then return end
    local code = keycodes[key]
    if code then self:setSource("keyboard:"..key, {code}) end
end

function Input:keyreleased(key)
    self:setSource("keyboard:"..key, {})
end

function Input:setMap(from, to)
    self.mapping[from] = to
    self:recompute()
end

function Input:beginFrame()
    self.down, self.direct = copy(self.logical), copy(self.raw)
    self.pressed, self.released = self.pendingDown, self.pendingUp
    self.directPressed, self.directReleased = self.pendingRawDown, self.pendingRawUp
    self.pendingDown, self.pendingUp, self.pendingRawDown, self.pendingRawUp = {}, {}, {}, {}
    -- A tap entirely between 30 Hz ticks must still last one game tick. Defer
    -- its release so both keyboard_check and keyboard_check_pressed see it.
    for k in pairs(self.pressed) do
        if not self.down[k] then self.down[k], self.pendingUp[k], self.released[k] = true, true, nil end
    end
    for k in pairs(self.directPressed) do
        if not self.direct[k] then self.direct[k], self.pendingRawUp[k], self.directReleased[k] = true, true, nil end
    end
    self.inFrame = true
end

function Input:endFrame()
    self.inFrame = false
end

function Input:check(code, edge, direct)
    local state = direct and (edge == "pressed" and self.directPressed or edge == "released" and self.directReleased or self.direct)
        or (edge == "pressed" and self.pressed or edge == "released" and self.released or self.down)
    if code == 0 or code == 1 then
        local any = false
        for k in pairs(state) do if k<=255 and (direct or not self.suppressed[k]) then any = true; break end end
        return code == 0 and not any or code == 1 and any
    end
    return state[code] == true and (direct or not self.suppressed[code])
end

function Input:mouseButton(source, button, down)
    self:setSource("mouse:"..tostring(source)..":"..button, down and {1000+button} or {})
end

function Input:checkMouse(button, edge)
    return self:check(1000+button,edge)
end

function Input:clear(code)
    self.down[code], self.pressed[code], self.released[code] = nil, nil, nil
    self.pendingDown[code], self.pendingUp[code] = nil, nil
    -- Clearing an event must not retrigger a held finger on the next frame.
    if self.logical[code] then self.suppressed[code] = true end
end

function Input:cancelAll()
    self.sources, self.raw, self.logical, self.down, self.direct = {}, {}, {}, {}, {}
    self.pressed, self.released, self.directPressed, self.directReleased = {}, {}, {}, {}
    self.pendingDown, self.pendingUp, self.pendingRawDown, self.pendingRawUp, self.suppressed = {}, {}, {}, {}, {}
    self.inFrame = false
end

function Input:gamepadpressed(joystick, button)
    local map = {a=90, b=88, x=88, y=67, start=13, back=27,
        dpup=38, dpdown=40, dpleft=37, dpright=39, leftshoulder=16, rightshoulder=67}
    self:setSource("gamepad:"..tostring(joystick)..":"..button, map[button] and {map[button]} or {})
end
function Input:gamepadreleased(joystick, button)
    self:setSource("gamepad:"..tostring(joystick)..":"..button, {})
end
function Input:gamepadaxis(joystick, axis, value)
    if axis ~= "leftx" and axis ~= "lefty" then return end
    local source = "gamepad:"..tostring(joystick)..":"..axis
    local threshold = self.sources[source] and 0.30 or 0.45 -- hysteresis, no drift
    local keys = {}
    if math.abs(value) > threshold then
        keys[1] = axis == "leftx" and (value < 0 and 37 or 39) or (value < 0 and 38 or 40)
    end
    self:setSource(source, keys)
end
return Input
