-- GameMaker Studio 2 compatibility helpers used by Yellow's converted scripts.
-- This is intentionally a small, explicit adapter: a builtin that is not
-- implemented below remains a named Runtime:unsupported stop instead of being
-- silently treated as a no-op.
return function(R)
    local B, N = R.builtins, R.num
    local function has_script(name)
        local index=R.manifest.names and R.manifest.names[name]
        local scripts=R.manifest.scripts or {}
        return scripts[name] ~= nil or (index ~= nil and scripts[index] ~= nil)
    end
    local function reg(name, fn)
        -- Both games have generated compatibility scripts with names that look
        -- like Studio builtins (notably keyboard_multicheck_pressed).  A real
        -- script is more specific than this fallback adapter, so never shadow
        -- one, whether its manifest key is a name or a recovered GMX index.
        if B[name] == nil and not has_script(name) then
            B[name] = function(_, ...) return fn(...) end
        end
    end
    local function unsupported(name, detail)
        return function() R:unsupported(name, detail or "GameMaker Studio 2 builtin is not implemented by this port.") end
    end

    reg("array_create", function(size, value)
        local out = R.defaults(value == nil and 0 or value)
        for i = 0, math.max(0, math.floor(size or 0)) - 1 do out[i] = value == nil and 0 or value end
        return out
    end)
    local function array_length(value)
        if type(value) ~= "table" then return 0 end
        local max = -1
        for key in pairs(value) do if type(key) == "number" and key >= 0 and key == math.floor(key) then max = math.max(max, key) end end
        return max + 1
    end
    reg("array_length", array_length)
    reg("array_length_1d", array_length)
    reg("array_length_2d", function(value) return array_length(value) end)
    reg("array_get", function(value, index) return type(value) == "table" and value[index] or 0 end)
    reg("array_set", function(value, index, item) if type(value) == "table" then value[index] = item end return value end)
    reg("array_set_post", function(value, index, item)
        local old = type(value) == "table" and value[index] or 0
        if type(value) == "table" then value[index] = item end
        return old
    end)
    reg("array_push", function(value, ...) local i = array_length(value);for _,item in ipairs({...}) do value[i]=item;i=i+1 end;return i end)
    reg("array_pop", function(value) local i=array_length(value)-1;local item=value[i] or 0;value[i]=nil;return item end)
    reg("array_insert", function(value, index, item) for i=array_length(value),index+1,-1 do value[i]=value[i-1] end;value[index]=item;return value end)
    reg("array_delete", function(value, index, count) count=math.max(1,math.floor(count or 1));local n=array_length(value);for i=index,n-count-1 do value[i]=value[i+count] end;for i=n-count,n-1 do value[i]=nil end;return value end)
    reg("array_copy", function(destination, dest_index, source, source_index, length)
        for i=0,math.max(0,math.floor(length or 0))-1 do destination[dest_index+i]=source[source_index+i] end
        return destination
    end)
    reg("array_equals", function(a,b)
        if type(a) ~= "table" or type(b) ~= "table" then return N(a == b) end
        local n = math.max(array_length(a),array_length(b));for i=0,n-1 do if a[i] ~= b[i] then return 0 end end;return 1
    end)

    reg("sign", function(value) return value < 0 and -1 or value > 0 and 1 or 0 end)
    reg("sqr", function(value) return value * value end)
    reg("clamp", function(value, low, high) return math.max(low, math.min(high, value)) end)
    reg("lerp", function(a,b,amount) return a + (b-a)*amount end)
    reg("random_range", function(a,b) return a + math.random()*(b-a) end)
    reg("irandom_range", function(a,b) return math.random(math.floor(a), math.floor(b)) end)
    reg("mean", function(...) local values={...};local total=0;for _,v in ipairs(values) do total=total+v end;return #values>0 and total/#values or 0 end)
    reg("angle_difference", function(a,b) local d=(a-b+180)%360-180;return d end)
    reg("is_undefined", function(value) return N(value == nil or value == R.UNDEFINED) end)
    reg("is_array", function(value) return N(type(value) == "table" and value._instance ~= true) end)
    reg("is_string", function(value) return N(type(value) == "string") end)
    reg("is_real", function(value) return N(type(value) == "number") end)
    reg("is_ptr", function() return 0 end)

    reg("string_copy", function(value, index, count)
        return tostring(value):sub(math.max(1,math.floor(index or 1)), math.max(1,math.floor(index or 1))+math.max(0,math.floor(count or 0))-1)
    end)
    reg("string_format", function(format, ...) return string.format(format, ...) end)
    reg("string_lettersdigits", function(value) return tostring(value):gsub("[^%w]", "") end)
    reg("string_hash_to_newline", function(value) return tostring(value):gsub("#", "\n") end)
    reg("string_repeat", function(value, count) return string.rep(tostring(value), math.max(0,math.floor(count or 0))) end)
    reg("string_replace_all", function(value, old, new) return tostring(value):gsub(tostring(old):gsub("([^%w])", "%%%1"), tostring(new)) end)
    reg("string_trim", function(value) return tostring(value):gsub("^%s+", ""):gsub("%s+$", "") end)

    reg("asset_get_index", function(name)
        if type(name) == "number" then return name end
        return (R.constants[tostring(name)] ~= nil and R.constants[tostring(name)]) or -1
    end)
    reg("variable_global_exists", function(name) return N(R.globalNames[tostring(name)] or R.global[tostring(name)] ~= nil) end)
    reg("variable_instance_exists", function(instance, name)
        local target = R:select(instance, nil)[1]
        return N(target and target.v[tostring(name)] ~= nil)
    end)
    reg("object_exists", function(index) return N(R.manifest.objects[index] ~= nil) end)
    reg("room_exists", function(index) return N(R.manifest.rooms[index] ~= nil) end)
    reg("script_exists", function(name)
        local scripts=R.manifest.scripts or {};local names=R.manifest.names or {}
        return N(scripts[name] ~= nil or scripts[names[name]] ~= nil)
    end)
    reg("room_get_name", function(index) local room=R.manifest.rooms[index] and R:roomData(index);return room and room.name or "" end)

    if B.instance_create_depth == nil and not has_script("instance_create_depth") then
        B.instance_create_depth=function(_,x,y,depth,object)
            local instance=R:create(object,x,y);instance.v.depth=depth;return instance.id
        end
    end
    if B.instance_place == nil and not has_script("instance_place") then
        B.instance_place=function(E,x,y,object) return B.collision_point(E,x,y,object,1,0) end
    end
    if B.instance_position == nil and not has_script("instance_position") then
        B.instance_position=function(E,x,y,object) return B.collision_point(E,x,y,object,1,0) end
    end

    -- Studio 2 colour spelling and a few renamed input aliases.
    if B.draw_set_color and B.draw_set_colour == nil then B.draw_set_colour=B.draw_set_color end
    if B.draw_rectangle_color and B.draw_rectangle_colour == nil then B.draw_rectangle_colour=B.draw_rectangle_color end
    reg("keyboard_multicheck", function(...) for _,key in ipairs({...}) do if R.input:check(key) then return 1 end end;return 0 end)
    reg("keyboard_multicheck_pressed", function(...) for _,key in ipairs({...}) do if R.input:check(key,"pressed") then return 1 end end;return 0 end)

    -- These facilities are represented in Yellow's source but have no safe
    -- GameMaker 1.4 equivalent.  Registering them makes the eventual failure
    -- name stable and lets the conversion report enumerate the limitation.
    local unsupported_names = {
        "layer_get_all", "layer_get_all_elements", "layer_get_name", "layer_get_element_type",
        "layer_create", "layer_destroy", "layer_set_target_room", "layer_get_target_room",
        "layer_sequence_create", "layer_sequence_destroy", "camera_create", "camera_apply",
        "camera_get_active", "camera_get_default", "view_get_camera", "matrix_set", "matrix_get",
        "matrix_build_identity", "matrix_build_lookat", "matrix_build_projection_ortho",
        "matrix_build_projection_perspective", "matrix_multiply", "vertex_create_buffer",
        "vertex_submit", "buffer_create", "buffer_write", "buffer_read", "ds_list_create",
        "ds_list_add", "ds_list_delete", "ds_map_create", "ds_map_write", "surface_create",
        "shader_get_uniform", "shader_set_uniform_f", "texture_prefetch", "texture_flush",
        "timeline_moment_add_script", "url_open", "show_question", "get_string", "live_call",
        "gml_pragma",
    }
    -- The fetched Yellow scripts also reference these Studio-only families.
    -- Keep them explicit rather than relying on Runtime:call's generic unknown
    -- function error; this preserves the builtin name in the failure report.
    local source_unsupported = {
        -- audio, buffers and cameras
        "alarm_set", "asset_get_tags", "audio_delete", "audio_exists", "audio_falloff_set_model",
        "audio_get_name", "audio_listener_orientation", "audio_listener_position", "audio_master_gain",
        "audio_play_sound_at", "audio_sound_length", "buffer_delete", "buffer_poke", "buffer_seek", "buffer_tell",
        "camera_create_view", "camera_destroy", "camera_get_proj_mat", "camera_get_view_angle",
        "camera_get_view_border_x", "camera_get_view_border_y", "camera_get_view_height",
        "camera_get_view_speed_x", "camera_get_view_speed_y", "camera_get_view_target",
        "camera_get_view_width", "camera_get_view_x", "camera_get_view_y", "camera_set_proj_mat",
        "camera_set_view_angle", "camera_set_view_border", "camera_set_view_mat", "camera_set_view_pos",
        "camera_set_view_size", "camera_set_view_speed", "camera_set_view_target",
        -- geometry, drawing, GPU and data structures
        "collision_ellipse", "date_second_span", "dcos", "draw_clear", "draw_ellipse_colour",
        "draw_get_alpha", "draw_get_color", "draw_get_colour", "draw_light_define_ambient",
        "draw_light_define_direction", "draw_light_define_point", "draw_light_enable", "draw_primitive_begin",
        "draw_primitive_end", "draw_self", "draw_set_lighting", "draw_sprite_general",
        "draw_sprite_stretched_ext", "draw_sprite_tiled", "draw_sprite_tiled_ext", "draw_vertex_color",
        "draw_vertex_colour", "ds_exists", "ds_grid_create", "ds_grid_read", "ds_grid_write",
        "ds_list_clear", "ds_list_empty", "ds_list_find_index", "ds_list_find_value", "ds_list_insert",
        "ds_list_read", "ds_list_shuffle", "ds_list_size", "ds_list_sort", "ds_list_write", "ds_map_read",
        "dsin", "frac", "gamepad_axis_count", "gamepad_axis_value", "gamepad_button_check",
        "gamepad_button_check_pressed", "gamepad_button_check_released", "gamepad_button_count",
        "gamepad_button_value", "gamepad_get_description", "gamepad_is_connected", "gamepad_set_axis_deadzone",
        "gpu_get_alphatestenable", "gpu_get_alphatestref", "gpu_get_texrepeat", "gpu_set_alphatestenable",
        "gpu_set_alphatestref", "gpu_set_blendenable", "gpu_set_blendmode", "gpu_set_blendmode_ext",
        "gpu_set_colorwriteenable", "gpu_set_cullmode", "gpu_set_fog", "gpu_set_texfilter",
        "gpu_set_texfilter_ext", "gpu_set_texrepeat", "gpu_set_texrepeat_ext", "gpu_set_ztestenable",
        "gpu_set_zwriteenable",
        -- Studio layers and tile elements
        "layer_background_alpha", "layer_background_blend", "layer_background_change", "layer_background_create",
        "layer_background_exists", "layer_background_get_alpha", "layer_background_get_blend",
        "layer_background_get_htiled", "layer_background_get_index", "layer_background_get_sprite",
        "layer_background_get_stretch", "layer_background_get_visible", "layer_background_get_vtiled",
        "layer_background_get_xscale", "layer_background_get_yscale", "layer_background_htiled",
        "layer_background_stretch", "layer_background_visible", "layer_background_vtiled",
        "layer_background_xscale", "layer_background_yscale", "layer_depth", "layer_element_move",
        "layer_force_draw_depth", "layer_get_depth", "layer_get_element_layer", "layer_get_hspeed",
        "layer_get_visible", "layer_get_vspeed", "layer_get_x", "layer_get_y", "layer_hspeed",
        "layer_set_visible", "layer_tile_alpha", "layer_tile_blend", "layer_tile_change", "layer_tile_create",
        "layer_tile_destroy", "layer_tile_exists", "layer_tile_get_alpha", "layer_tile_get_blend",
        "layer_tile_get_region", "layer_tile_get_sprite", "layer_tile_get_visible", "layer_tile_get_x",
        "layer_tile_get_xscale", "layer_tile_get_y", "layer_tile_get_yscale", "layer_tile_region",
        "layer_tile_visible", "layer_tile_x", "layer_tile_xscale", "layer_tile_y", "layer_tile_yscale",
        "layer_vspeed", "layer_x", "layer_y", "matrix_build", "matrix_build_projection_perspective_fov",
        "matrix_stack_clear", "matrix_stack_is_empty", "matrix_stack_pop", "matrix_stack_push",
        "matrix_stack_set", "matrix_stack_top", "matrix_transform_vertex",
        -- object/room/path, shader, surface, sprite, timeline and vertex helpers
        "object_get_name", "object_is_ancestor", "path_add", "path_add_point", "path_delete",
        "path_set_closed", "path_set_kind", "place_free", "place_meeting", "position_meeting",
        "rectangle_in_rectangle", "room_get_camera", "room_set_camera", "room_set_viewport",
        "shader_get_sampler_index", "shader_reset", "shader_set", "shader_set_uniform_i", "show_debug_message",
        "sprite_add", "sprite_assign", "sprite_duplicate", "sprite_get_number", "sprite_get_texture",
        "sprite_get_uvs", "sprite_get_xoffset", "sprite_get_yoffset", "sprite_prefetch", "sprite_prefetch_multi",
        "sprite_save", "sprite_set_alpha_from_sprite", "string_insert", "surface_exists", "surface_free",
        "surface_reset_target", "surface_set_target", "texture_get_texel_height", "texture_get_texel_width",
        "texture_get_uvs", "texture_is_ready", "texture_set_stage", "timeline_add", "timeline_clear",
        "timeline_exists", "vertex_begin", "vertex_colour", "vertex_create_buffer_from_buffer",
        "vertex_delete_buffer", "vertex_end", "vertex_format_add_colour", "vertex_format_add_normal",
        "vertex_format_add_position_3d", "vertex_format_add_texcoord", "vertex_format_begin",
        "vertex_format_end", "vertex_freeze", "vertex_normal", "vertex_position_3d", "vertex_texcoord",
        "view_get_hport", "view_get_surface_id", "view_get_visible", "view_get_wport", "view_get_xport",
        "view_get_yport", "view_set_camera", "view_set_hport", "view_set_surface_id", "view_set_visible", "view_set_wport",
        "view_set_xport", "view_set_yport",
    }
    for _,name in ipairs(unsupported_names) do
        if B[name] == nil and not has_script(name) then B[name]=unsupported(name) end
    end
    for _,name in ipairs(source_unsupported) do
        if B[name] == nil and not has_script(name) then B[name]=unsupported(name) end
    end
end
