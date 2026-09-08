if(instance_exists(782/* OBJ_WRITER */) && keyboard_multicheck_pressed(1/* ANYKEY */)) {
    // OBJ_WRITER
    with(782) {
        if(halt == 0) {
            stringpos= string_length(originalstring);
        }
        if(halt == 1) {
            myletter= " ";
            stringpos= 1;
            stringno++;
            originalstring= mystring[stringno];
            myx= writingx;
            myy= writingy;
            lineno= 0;
            halt= 0;
            alarm[0]= textspeed;
        }
        if(halt == 2 || halt == 4) {
            global.myfight= 0;
            global.mnfight= 1;
            keyboard_clear(13/* ENTER */);
            instance_destroy();
        }
    }
    keyboard_clear(16/* SHIFT */);
}
