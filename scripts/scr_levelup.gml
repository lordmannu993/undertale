currentlevel= global.lv;
// flag[478] = EXP from the STAT-menu 709 EXP button: real EXP, never LOVE
effxp= global.xp - global.flag[478];
if(effxp < 0) effxp= 0;
if(effxp >= 10) global.lv= 2;
if(effxp >= 30) global.lv= 3;
if(effxp >= 70) global.lv= 4;
if(effxp >= 120) global.lv= 5;
if(effxp >= 200) global.lv= 6;
if(effxp >= 300) global.lv= 7;
if(effxp >= 500) global.lv= 8;
if(effxp >= 800) global.lv= 9;
if(effxp >= 1200) global.lv= 10;
if(effxp >= 1700) global.lv= 11;
if(effxp >= 2500) global.lv= 12;
if(effxp >= 3500) global.lv= 13;
if(effxp >= 5000) global.lv= 14;
if(effxp >= 7000) global.lv= 15;
if(effxp >= 10000) global.lv= 16;
if(effxp >= 15000) global.lv= 17;
if(effxp >= 25000) global.lv= 18;
if(effxp >= 50000) global.lv= 19;
if(effxp >= 99999) {
    global.lv= 20;
    global.xp= 99999;
}
if(global.lv != currentlevel) {
    levelup= 1;
    global.maxhp= 16 + global.lv * 4;
    global.at= 8 + global.lv * 2;
    global.df= 9 + ceil(global.lv / 4);
    if(global.lv == 20) {
        global.maxhp= 99;
        global.at= 99;
        global.df= 99;
    }
} else  levelup= 0;
