"""Room conversion gates, including the complete pinned source when available.

These prove conversion, NOT connected-world gameplay or native Yellow rendering.
"""
import json
import os
from pathlib import Path
import sys

import pytest
from lupa.lua51 import LuaRuntime as Lua51
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import yellow_support as support
from yellow.gms2 import GMS2Error, read
from yellow.registry import Registry
from yellow.rooms import RoomConverter, INSTANCE_BASE, tile_data
from yellow_convert import Writer, stage_rooms


def test_tile_literal_and_repeated_runs():
    assert tile_data(dict(SerialiseWidth=3, SerialiseHeight=2, TileDataFormat=1,
                          TileCompressedData=[-2, 0, 3, 1, 2, 3, -1, 8])) == [0, 0, 1, 2, 3, 8]
    assert tile_data(dict(SerialiseWidth=2, SerialiseHeight=1, TileSerialiseData=[0, 1])) == [0, 1]


@pytest.mark.parametrize('data', [[0], [-7, 0], [-2], [3, 0], [1, 0], [-6, -1]])
def test_tile_decoder_rejects_malformed_data(data):
    with pytest.raises(GMS2Error):
        tile_data(dict(SerialiseWidth=3, SerialiseHeight=2, TileDataFormat=1, TileCompressedData=data))


@pytest.fixture()
def fixture(tmp_path):
    source, provenance = support.build_source(tmp_path)
    registry = Registry(source, provenance)
    obj = registry.project_order['objects'][0]
    for name in registry.project_order['rooms']:
        spec = dict(name='inst_ABC', objectId={'name': obj}, x=12, y=24, scaleX=2, scaleY=3,
                    rotation=45, colour=0x80ffffff, imageIndex=2, imageSpeed=.5, hasCreationCode=True)
        data = dict(name=name, roomSettings=dict(Width=320, Height=240, persistent=False),
                    viewSettings=dict(enableViews=True),
                    views=[dict(visible=True, objectId={'name': obj}, wview=320, hview=240,
                                wport=320, hport=240)], creationCodeFile=f'rooms/{name}/RoomCreationCode.gml',
                    instanceCreationOrder=[{'name': spec['name']}], layers=[dict(
                        resourceType='GMRInstanceLayer', name='Actors', depth=-37, visible=True,
                        instances=[spec])])
        folder = source / 'rooms' / name
        (folder / f'{name}.yy').write_text(json.dumps(data))
        (folder / 'InstanceCreationCode_inst_ABC.gml').write_text('x += 3;')
        (folder / 'RoomCreationCode.gml').write_text('global.room_entered = true;')
    for name in registry.project_order['paths']:
        (source / 'paths' / name / f'{name}.yy').write_text(json.dumps(dict(
            name=name, closed=False, kind=0, precision=4, points=[dict(x=10, y=20, speed=100)])))
    project_path = source / 'Undertale_Yellow.yyp'
    project = read(project_path)
    project['RoomOrderNodes'] = [{'roomId': {'name': name}} for name in reversed(registry.project_order['rooms'])]
    project_path.write_text(json.dumps(project))
    return source, provenance, registry


def test_room_order_depth_creation_code_and_paths(fixture, tmp_path):
    source, provenance, registry = fixture
    converter = RoomConverter(registry, source, provenance, 'probe')
    report = converter.run(Writer(tmp_path / 'generated'))
    assert report['converted'] == len(registry.project_order['rooms'])
    assert converter.order == [registry.merged('rooms', n) for n in reversed(registry.project_order['rooms'])]
    for name in registry.project_order['paths']:
        original = read(source / 'paths' / name / f'{name}.yy')
        assert converter.path_points[registry.merged('paths', name)] == original
    room, code = converter.convert(registry.project_order['rooms'][0])
    assert room['instances'][0]['depth'] == -37
    assert room['instances'][0]['id'] == INSTANCE_BASE + 0xABC
    assert room['views'][0]['object'] == registry.merged('objects', registry.project_order['objects'][0])
    vm = LuaJIT(unpack_returned_tuples=True)
    result = vm.execute(code)
    vm.execute("R=require('port.runtime').new({names={},rooms={},room_order={},keys={}},require('port.input').new(),{headless=true})")
    R = vm.globals().R
    vm.execute("R.objects[1]={name='probe',sprite=-1,mask=-1,parent=-1,depth=0,events={}}; i=R:create(1,12,24,nil,true)")
    instance = vm.globals().i
    result.instances[1].create(R, R.scope(R, instance))
    assert instance.v.x == 15


def test_bad_creation_order_and_missing_code_fail(fixture):
    source, provenance, registry = fixture
    name = registry.project_order['rooms'][0]
    path = source / 'rooms' / name / f'{name}.yy'
    converter = RoomConverter(registry, source, provenance, 'probe')
    data = read(path)
    data['instanceCreationOrder'] = []
    path.write_text(json.dumps(data))
    with pytest.raises(GMS2Error, match='creation order'):
        converter.convert(name)
    (source / 'rooms' / name / 'InstanceCreationCode_inst_ABC.gml').unlink()
    with pytest.raises(FileNotFoundError):
        converter.convert(name)


def test_runtime_applies_studio_metadata_and_rejects_rooms_before_teardown():
    vm = LuaJIT(unpack_returned_tuples=True)
    vm.execute('''
        package.path='./?.lua;./?/init.lua;'..package.path
        R=require('port.runtime').new({names={},rooms={},room_order={},keys={}},require('port.input').new(),{headless=true})
        R.objects[1]={name='probe',sprite=-1,mask=-1,parent=-1,depth=0,visible=true,events={}}
        i=R:create(1,12,24,{id=4294967297,yellow=true,depth=-37,imageIndex=2,imageSpeed=.5,
                          colour=2164260863,scaleX=2,scaleY=3,rotation=45},true)
        assert(i.v.depth==-37 and i.v.image_index==2 and i.v.image_speed==.5)
        assert(i.v.image_alpha==128/255 and i.v.image_xscale==2 and i.v.image_yscale==3)
        R.rooms[2]={name='unsupported_probe',yellow={unsupported={'named effect'}}}
        local ok,err=pcall(function() R:loadRoom(2,false) end)
        assert(not ok and tostring(err):find('named effect',1,true))
        assert(i.alive and R.byId[i.id]==i and #R.instances==1)
    ''')


LIVE = (ROOT / 'yellow_src/Undertale_Yellow.yyp').is_file()
@pytest.fixture(scope='module')
def converted_live():
    if not LIVE and os.environ.get('PORT_REQUIRE_YELLOW') != '1':
        pytest.skip('fetch pinned yellow_src/ to run complete room conversion')
    provenance = json.loads((ROOT / 'port/yellow_source.json').read_text())
    registry = Registry(ROOT / 'yellow_src', provenance)
    output = ROOT / 'generated/yellow_rooms_test'
    report = stage_rooms(registry, provenance, Writer(output), ROOT, ROOT, 'generated.yellow_rooms_test')
    return registry, output, report


def test_all_pinned_rooms_paths_and_creation_code(converted_live):
    registry, output, report = converted_live
    assert report['rooms']['converted'] == 287
    assert report['rooms']['paths'] == 68
    assert report['rooms']['counts']['instances'] == 7637
    assert report['rooms']['counts']['creation_code'] == 1340
    assert report['rooms']['compile_errors'] == []
    assert report['rooms']['unsupported'], 'unsupported source features must never disappear'
    vm = LuaJIT(unpack_returned_tuples=True)
    manifest = vm.execute((output / 'manifest.lua').read_text())
    assert len(manifest.room_order) == 287
    for name in registry.project_order['paths']:
        original = read(registry.source / 'paths' / name / f'{name}.yy')
        path = manifest.path_points[registry.merged('paths', name)]
        assert path.kind == original['kind'] and path.closed == original['closed']
        for i, point in enumerate(original['points'], 1):
            assert dict(path.points[i]) == point


@pytest.mark.parametrize('vm_type', [Lua51, LuaJIT])
def test_every_pinned_room_chunk_compiles(converted_live, vm_type):
    _, output, _ = converted_live
    vm = vm_type(unpack_returned_tuples=True)
    compile_ = vm.eval('function(code,name) local f,e=loadstring(code,name); assert(f,e); return true end')
    for path in sorted((output / 'rooms').glob('*.lua')):
        assert compile_(path.read_text(), str(path))
    assert compile_((output / 'manifest.lua').read_text(), 'Yellow room manifest')


def test_room_effect_is_preserved_and_becomes_named_stop(fixture):
    source, provenance, registry = fixture
    name = registry.project_order['rooms'][0]
    path = source / 'rooms' / name / f'{name}.yy'
    data = read(path)
    effect = dict(resourceType='GMREffectLayer', name='Colourise', depth=-1,
                  effectEnabled=True, effectType='_filter_colourise', visible=True)
    data['layers'].append(effect)
    path.write_text(json.dumps(data))
    room, _ = RoomConverter(registry, source, provenance, 'probe').convert(name)
    assert room['yellow']['layers'][-1] == effect
    assert room['yellow']['unsupported'] == ['layer effect Colourise: _filter_colourise']


def test_static_yellow_drawables_keep_crops_scale_tint_and_visibility():
    vm = LuaJIT(unpack_returned_tuples=True)
    vm.execute('''
        local calls={}
        local R={assets={sprites={[1]={width=20,height=10}}},vars={room_width=100,room_height=100}}
        local draw=require('port.yellow_graphics').install(R,function(...) calls[#calls+1]={...} end)
        local view={x=0,y=0,w=100,h=100}
        draw({sprite=1,visible=false},view)
        assert(#calls==0)
        draw({sprite=1,x=12,y=14,xo=2,yo=3,w=4,h=5,scaleX=2,scaleY=3,colour=2164260863},view)
        assert(#calls==1)
        assert(calls[1][4]==12 and calls[1][5]==14 and calls[1][6]==2 and calls[1][7]==3)
        assert(calls[1][9]==16777215 and calls[1][10]==128/255)
        assert(calls[1][11][1]==2 and calls[1][11][4]==5)
        draw({sprite=1,backgroundLayer=true,x=0,y=0,stretch=true,colour=4294967295},view)
        assert(#calls==2 and calls[2][6]==5 and calls[2][7]==10)
        draw({sprite=1,resourceType='GMRSpriteGraphic',x=5,y=6,scaleX=2,scaleY=2,
              rotation=45,headPosition=3,colour=4294967295},view)
        assert(calls[3][3]==3 and calls[3][8]==45)
    ''')
