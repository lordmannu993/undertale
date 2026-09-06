function love.conf(t)
    t.identity = "undertale-love-port"
    t.version = "11.4"
    t.console = false
    t.gammacorrect = false
    t.accelerometerjoystick = false
    t.externalstorage = false
    t.window.title = "UNDERTALE - experimental LOVE port"
    t.window.width = 1120
    t.window.height = 700
    t.window.resizable = true
    t.window.minwidth = 480
    t.window.minheight = 320
    t.window.highdpi = true
    t.window.vsync = 1
    t.modules.physics = false
    t.modules.video = false
end
