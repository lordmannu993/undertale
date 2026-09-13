"""Strict GMS2 room/path front end; unsupported layer features remain named stops.

Instance IDs encode the decompiler's hexadecimal name in a disjoint 2**32 band.
This is a reversible mapping, not a guessed GameMaker runtime instance index.
Tile RLE is decoded with exact cardinality checks before any drawable is emitted.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from convert import lua
from gml2 import compile_gml2_event, function_expression
from yellow.gms2 import GMS2Error, read, ref_name
from yellow.objects import ObjectConverter

INSTANCE_BASE = 2**32


def tile_data(tiles: dict) -> list[int]:
    size = tiles['SerialiseWidth'] * tiles['SerialiseHeight']
    if size < 0 or size > 10_000_000:
        raise GMS2Error('Invalid tile grid dimensions')
    if 'TileCompressedData' not in tiles:
        result = list(tiles.get('TileSerialiseData', []))
    else:
        if tiles.get('TileDataFormat') != 1:
            raise GMS2Error('Unknown tile compression format')
        data, result, i = tiles['TileCompressedData'], [], 0
        while i < len(data):
            count = data[i]
            i += 1
            if not count or len(result) + abs(count) > size:
                raise GMS2Error('Invalid tile RLE run length')
            if count < 0:
                if i >= len(data):
                    raise GMS2Error('Truncated repeated tile run')
                result.extend([data[i]] * -count)
                i += 1
            else:
                if i + count > len(data):
                    raise GMS2Error('Truncated literal tile run')
                result.extend(data[i:i + count])
                i += count
    if len(result) != size:
        raise GMS2Error(f'Tile grid has {len(result)} cells, expected {size}')
    if any(not isinstance(n, int) or n < 0 or n > 0xffffffff for n in result):
        raise GMS2Error('Invalid unsigned tile data')
    return result


class RoomConverter:
    def __init__(self, registry, root: Path, provenance: dict, prefix: str):
        self.registry, self.source, self.prefix = registry, registry.source, prefix
        self.resolver = ObjectConverter(registry, root, provenance, prefix).resolver
        self.modules, self.paths, self.path_points = {}, {}, {}
        self.counts, self.stops = Counter(), []
        self.tilesets = {}
        self.sprites = {}
        self.speed = read(self.source / "options/main/options_main.yy")["option_game_speed"]

    def asset(self, kind, ref):
        name = ref_name(ref)
        return self.registry.merged(kind, name) if name else -1

    def code(self, relative):
        path = (self.source / relative).resolve()
        if not path.is_relative_to(self.source.resolve()):
            raise GMS2Error(f'Creation code escapes source: {relative}')
        source = path.read_text(encoding='utf-8-sig')
        module, _, _ = compile_gml2_event(source, relative, self.resolver)
        self.counts['creation_code'] += 1
        return function_expression(module)

    def convert(self, name):
        data = read(self.source / 'rooms' / name / f'{name}.yy')
        settings, viewsettings = data['roomSettings'], data['viewSettings']
        room = dict(name=name, id=self.registry.merged('rooms', name),
                    width=settings['Width'], height=settings['Height'], speed=self.speed,
                    persistent=settings['persistent'], colour=0, showcolour=True,
                    enableViews=viewsettings['enableViews'], views=[], backgrounds=[], tiles=[],
                    instances=[], yellow={'layers': data['layers'], 'unsupported': []})
        def stop(feature):
            if feature not in room['yellow']['unsupported']:
                room['yellow']['unsupported'].append(feature)
                self.stops.append({'room': name, 'feature': feature})
        if data.get('parentRoom') or data.get('inheritLayers') or data.get('inheritCreationOrder'):
            stop('inherited room')
        if data.get('sequenceId'):
            stop('room sequence ' + ref_name(data['sequenceId']))
        if data.get('physicsSettings', {}).get('PhysicsWorld'):
            stop('physics world')
        for view in data['views']:
            room['views'].append({**view, 'object': self.asset('objects', view.get('objectId'))})
        instances, codes = {}, {}
        def layers(entries):
            for layer in entries:
                yield layer
                yield from layers(layer.get('layers', []))
        for layer in layers(data['layers']):
            kind, depth = layer['resourceType'], layer['depth']
            self.counts[kind] += 1
            visible = layer.get('visible', True)
            if layer.get('effectEnabled') and layer.get('effectType'):
                stop('layer effect ' + layer['name'] + ': ' + layer['effectType'])
            if kind == 'GMRInstanceLayer':
                for spec in layer['instances']:
                    if spec.get('ignore') or spec.get('properties') or spec.get('inheritCode'):
                        raise GMS2Error(f'{name}/{spec["name"]}: unsupported instance overrides')
                    instance_name = spec['name']
                    if instance_name in instances or not instance_name.startswith('inst_'):
                        raise GMS2Error(f'{name}: invalid/duplicate instance name {instance_name}')
                    instance = dict(spec, id=INSTANCE_BASE + int(instance_name[5:], 16),
                                    object=self.asset('objects', spec['objectId']), depth=depth,
                                    layerVisible=visible, yellow=True)
                    instances[instance_name] = instance
                    if spec['hasCreationCode']:
                        codes[instance_name] = self.code(f'rooms/{name}/InstanceCreationCode_{instance_name}.gml')
            elif kind == 'GMRTileLayer':
                cells = tile_data(layer['tiles'])
                tsname = ref_name(layer.get('tilesetId'))
                if not tsname:
                    if any(cells):
                        raise GMS2Error(f'{name}/{layer["name"]}: nonempty grid has no tileset')
                    continue
                if tsname not in self.tilesets:
                    self.tilesets[tsname] = read(self.source / 'tilesets' / tsname / f'{tsname}.yy')
                ts = self.tilesets[tsname]
                background = self.asset('backgrounds', layer['tilesetId'])
                width, height, columns = ts['tileWidth'], ts['tileHeight'], ts['out_columns']
                if min(width, height, columns) <= 0:
                    raise GMS2Error(f'{tsname}: invalid tile geometry')
                if ts.get('tileAnimation', {}).get('SerialiseFrameCount', 1) > 1:
                    stop('animated tileset ' + tsname)
                for cell, value in enumerate(cells):
                    index = value & 0x7ffff
                    if not index:
                        continue
                    if index >= ts['tile_count']:
                        raise GMS2Error(f'{name}/{layer["name"]}: tile {index} outside {tsname}')
                    if value != index:
                        stop('transformed tile data ' + layer['name'])
                    # Decompiled texture pages are unpadded source grids. The
                    # out_tile*border values describe a future texture compiler,
                    # not borders in the pinned PNG (checked by asset tests).
                    room['tiles'].append(dict(background=background, depth=depth, visible=visible,
                        x=layer['x'] + cell % layer['tiles']['SerialiseWidth'] * width,
                        y=layer['y'] + cell // layer['tiles']['SerialiseWidth'] * height,
                        xo=ts['tilexoff'] + index % columns * (width + ts['tilehsep']),
                        yo=ts['tileyoff'] + index // columns * (height + ts['tilevsep']),
                        w=width, h=height, colour=0xffffffff))
            elif kind == 'GMRAssetLayer':
                for graphic in layer['assets']:
                    item = dict(graphic, sprite=self.asset('sprites', graphic['spriteId']),
                                depth=depth, visible=visible)
                    if graphic['resourceType'] == 'GMRGraphic':
                        item.update(xo=graphic['u0'], yo=graphic['v0'],
                                    w=graphic['u1']-graphic['u0'], h=graphic['v1']-graphic['v0'])
                        if item['w'] == 0 or item['h'] == 0:
                            raise GMS2Error(f'{name}/{graphic["name"]}: empty source rectangle')
                        item.update(scaleX=graphic['w']/item['w'], scaleY=graphic['h']/item['h'])
                    elif graphic['resourceType'] == 'GMRSpriteGraphic':
                        sprite_name = ref_name(graphic['spriteId'])
                        if sprite_name not in self.sprites:
                            self.sprites[sprite_name] = read(self.source / 'sprites' / sprite_name / f'{sprite_name}.yy')
                        if graphic['animationSpeed'] and len(self.sprites[sprite_name]['frames']) > 1:
                            stop('animated room sprite ' + graphic['name'])
                    else:
                        stop('asset ' + graphic['resourceType'] + ': ' + graphic['name'])
                    room['tiles'].append(item)
            elif kind == 'GMRBackgroundLayer':
                if layer.get('spriteId'):
                    sprite_name = ref_name(layer['spriteId'])
                    if sprite_name not in self.sprites:
                        self.sprites[sprite_name] = read(self.source / 'sprites' / sprite_name / f'{sprite_name}.yy')
                    if layer['hspeed'] or layer['vspeed'] or (layer['animationFPS'] and len(self.sprites[sprite_name]['frames']) > 1):
                        stop('moving or animated background ' + layer['name'])
                    # A Studio background is an animated sprite at an arbitrary
                    # depth, NOT a GM1 background asset in a front/back slot.
                    room['tiles'].append(dict(layer, sprite=self.asset('sprites', layer['spriteId']),
                                              backgroundLayer=True))
                elif visible:
                    if layer['colour'] >> 24 == 0:
                        continue
                    if layer['name'] != 'Compatibility_Colour':
                        stop('depth-sorted colour layer ' + layer['name'])
                    room['colour'] = layer['colour'] & 0xffffff
            elif kind not in ('GMREffectLayer', 'GMRPathLayer'):
                stop('layer ' + kind + ': ' + layer['name'])
        order = [ref_name(entry) for entry in data['instanceCreationOrder']]
        if len(order) != len(set(order)) or set(order) != set(instances):
            raise GMS2Error(f'{name}: creation order does not match room instances')
        room['instances'] = [instances[n] for n in order]
        self.counts['instances'] += len(order)
        self.counts['drawables'] += len(room['tiles'])
        output = ['local room = ' + lua(room)]
        for i, n in enumerate(order, 1):
            if n in codes:
                output.append(f'room.instances[{i}].create = ' + codes[n])
        if data['creationCodeFile']:
            output.append('room.create = ' + self.code(data['creationCodeFile']))
        output.append('return room\n')
        return room, '\n'.join(output)

    def run(self, writer):
        for name in self.registry.project_order['rooms']:
            _, module = self.convert(name)
            writer.write(f'rooms/{name}.lua', module)
            self.modules[self.registry.merged('rooms', name)] = self.prefix + '.rooms.' + name
        project = read(self.source / 'Undertale_Yellow.yyp')
        self.order = [self.asset('rooms', entry['roomId']) for entry in project['RoomOrderNodes']]
        if len(self.order) != len(set(self.order)) or set(self.order) != set(self.modules):
            raise GMS2Error('RoomOrderNodes does not enumerate every recovered room exactly once')
        for name in self.registry.project_order['paths']:
            data = read(self.source / 'paths' / name / f'{name}.yy')
            index = self.registry.merged('paths', name)
            self.paths[index] = name
            self.path_points[index] = {k: data[k] for k in ('name', 'kind', 'closed', 'precision', 'points')}
        return dict(converted=len(self.modules), paths=len(self.paths), compile_errors=[],
                    counts=dict(self.counts), unsupported=self.stops)
