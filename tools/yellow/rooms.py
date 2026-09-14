"""Strict GMS2 room/path front end; unsupported layer features remain named stops.

Instance IDs encode the decompiler's hexadecimal name in a disjoint 2**32 band.
This is a reversible mapping, not a guessed GameMaker runtime instance index.
Tile RLE is decoded with exact cardinality checks before any drawable is emitted.

Piece 4 draws everything a Studio 2 room *authors* rather than stopping on it:

* tile data transform bits (mirror bit 28, flip bit 29, rotate bit 30 — the
  layout the GameMaker manual documents for a tile data blob);
* tileset animation, from the tileset's own ``FrameData`` rows, cross-checked
  against its ``tileAnimationFrames`` groups so the two pinned records have to
  agree before either is used;
* asset-layer sprite animation (``animationSpeed`` multiplies the sprite's own
  playback speed, ``headPosition`` is its first frame, ``frozen`` stops it);
* background layers that scroll (``hspeed``/``vspeed``) or animate
  (``animationFPS`` + ``animationSpeedType``);
* colour-only background layers at any depth, which Studio 2 fills with the
  layer colour — that is where a GM1 room's own background colour goes on
  import (``Compatibility_Colour``).

Layer effects (Studio shaders) and physics worlds still stop with their own
name: this runtime has neither, and a silently motionless or unfiltered layer
would be worse than the visible stop.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from convert import lua
from gml2 import compile_gml2_event, function_expression
from yellow.assets import image_speed
from yellow.gms2 import GMS2Error, read, ref_name
from yellow.objects import ObjectConverter

INSTANCE_BASE = 2**32

#: Tile data blob layout, per the GameMaker manual's Tile Map Elements page:
#: bits 0-18 are the tile index, bit 28 mirrors, bit 29 flips, bit 30 rotates
#: 90 degrees, bits 19-27 and 31 are unused.
TILE_INDEX_MASK = 0x7FFFF
TILE_MIRROR = 1 << 28
TILE_FLIP = 1 << 29
TILE_ROTATE = 1 << 30
TILE_KNOWN_BITS = TILE_INDEX_MASK | TILE_MIRROR | TILE_FLIP | TILE_ROTATE

#: Layer kinds whose elements this runtime can draw.
DRAWABLE_LAYERS = ('GMRInstanceLayer', 'GMRTileLayer', 'GMRAssetLayer', 'GMRBackgroundLayer')


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


def tile_transform(value: int) -> dict:
    """The transform flags of one tile data blob, or a hard error on unknown bits.

    Bits 19-27 and 31 are documented as unused, and a room is free to claim
    part of the index for a custom mask (``tilemap_set_mask``). Yellow does
    neither, so any such bit is a conversion error instead of a guessed flag.
    """
    unknown = value & ~TILE_KNOWN_BITS
    if unknown:
        raise GMS2Error(f'tile data {value:#x} uses bits outside the documented '
                        f'index/mirror/flip/rotate layout: {unknown:#x}')
    flags = {}
    if value & TILE_MIRROR:
        flags['mirror'] = True
    if value & TILE_FLIP:
        flags['flip'] = True
    if value & TILE_ROTATE:
        flags['rotate'] = True
    return flags


class RoomConverter:
    def __init__(self, registry, root: Path, provenance: dict, prefix: str):
        self.registry, self.source, self.prefix = registry, registry.source, prefix
        self.resolver = ObjectConverter(registry, root, provenance, prefix).resolver
        self.modules, self.paths, self.path_points = {}, {}, {}
        self.counts, self.stops = Counter(), []
        self.tilesets = {}
        self.sprites = {}
        self.animations = {}
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

    def sprite_record(self, name):
        if name not in self.sprites:
            self.sprites[name] = read(self.source / 'sprites' / name / f'{name}.yy')
        return self.sprites[name]

    def sprite_speed(self, name):
        """GameMaker 1.4 image_speed for a sprite, from its own Studio 2 numbers."""
        sequence = self.sprite_record(name).get('sequence') or {}
        return image_speed(sequence.get('playbackSpeed', 1), sequence.get('playbackSpeedType', 1), self.speed)

    def tileset_record(self, name):
        if name not in self.tilesets:
            self.tilesets[name] = read(self.source / 'tilesets' / name / f'{name}.yy')
        return self.tilesets[name]

    def tileset_animation(self, name):
        """Validate one tileset's two animation records against each other.

        ``tileAnimation.FrameData`` is the authoritative table the runtime reads
        (one row of ``SerialiseFrameCount`` tile indices per tile, so a placed
        frame animates from itself onwards, exactly as the tile set editor
        documents). ``tileAnimationFrames`` lists the authored groups; the two
        must agree or the pinned source is being misread.
        """
        if name in self.animations:
            return self.animations[name]
        data = self.tileset_record(name)
        animation = data.get('tileAnimation') or {}
        frame_count = int(animation.get('SerialiseFrameCount', 1) or 1)
        frame_data = animation.get('FrameData') or []
        tile_count = int(data.get('tile_count', 0) or 0)
        groups = data.get('tileAnimationFrames') or []
        if frame_count <= 1:
            if groups:
                raise GMS2Error(f'{name}: {len(groups)} animation groups with SerialiseFrameCount {frame_count}')
            if frame_data and frame_data != list(range(len(frame_data))):
                raise GMS2Error(f'{name}: single-frame tileset has a non-identity FrameData table')
            self.animations[name] = None
            return None
        if len(frame_data) != tile_count * frame_count:
            raise GMS2Error(f'{name}: FrameData has {len(frame_data)} entries, expected '
                            f'{tile_count} tiles x {frame_count} frames')
        for group in groups:
            frames = group.get('frames') or []
            if len(frames) != frame_count:
                raise GMS2Error(f"{name}/{group.get('name')}: {len(frames)} frames, tileset animates {frame_count}")
            master = frames[0]
            if not 0 <= master < tile_count:
                raise GMS2Error(f"{name}/{group.get('name')}: first frame {master} is outside {tile_count} tiles")
            if frame_data[master * frame_count:(master + 1) * frame_count] != frames:
                raise GMS2Error(f"{name}/{group.get('name')}: tileAnimationFrames disagrees with FrameData")
        animated = sum(1 for i in range(tile_count)
                       if len(set(frame_data[i * frame_count:(i + 1) * frame_count])) > 1)
        record = {'frame_count': frame_count, 'animated_tiles': animated, 'groups': len(groups),
                  'speed': float(data.get('tileAnimationSpeed') or 0)}
        self.animations[name] = record
        self.counts['animated_tilesets'] += 1
        return record

    def convert(self, name):
        data = read(self.source / 'rooms' / name / f'{name}.yy')
        settings, viewsettings = data['roomSettings'], data['viewSettings']
        room = dict(name=name, id=self.registry.merged('rooms', name),
                    width=settings['Width'], height=settings['Height'], speed=self.speed,
                    persistent=settings['persistent'], colour=0, showcolour=True,
                    enableViews=viewsettings['enableViews'], views=[], backgrounds=[], tiles=[],
                    instances=[], layers=[], yellow={'layers': data['layers'], 'unsupported': []})
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
            # The runtime's layer model: one record per Studio 2 layer, in
            # traversal order, so layer_get_id/layer_set_visible/layer_depth and
            # friends have something real to address. Drawable and instance
            # positions are layer-relative, exactly as Studio 2 authors them.
            record = {'name': layer['name'], 'kind': kind, 'depth': depth, 'visible': visible,
                      'x': layer.get('x') or 0, 'y': layer.get('y') or 0,
                      'hspeed': layer.get('hspeed') or 0, 'vspeed': layer.get('vspeed') or 0}
            room['layers'].append(record)
            index = len(room['layers'])
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
                                    layer=index, layerVisible=visible, yellow=True)
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
                ts = self.tileset_record(tsname)
                animation = self.tileset_animation(tsname)
                background = self.asset('backgrounds', layer['tilesetId'])
                width, height, columns = ts['tileWidth'], ts['tileHeight'], ts['out_columns']
                if min(width, height, columns) <= 0:
                    raise GMS2Error(f'{tsname}: invalid tile geometry')
                grid = layer['tiles']
                for cell, value in enumerate(cells):
                    index_bits = value & TILE_INDEX_MASK
                    if not value:
                        continue
                    if not index_bits:
                        raise GMS2Error(f'{name}/{layer["name"]}: transform flags on the empty tile {value:#x}')
                    if index_bits >= ts['tile_count']:
                        raise GMS2Error(f'{name}/{layer["name"]}: tile {index_bits} outside {tsname}')
                    # Positions are layer-relative, as Studio 2 authors them: the
                    # runtime adds the layer's own x/y (and its hspeed/vspeed
                    # drift) when it draws, so layer_x()/layer_y() keep working.
                    tile = dict(background=background, depth=depth, visible=visible, yellow=True,
                                layer=index,
                                x=cell % grid['SerialiseWidth'] * width,
                                y=cell // grid['SerialiseWidth'] * height,
                                xo=ts['tilexoff'] + index_bits % columns * (width + ts['tilehsep']),
                                yo=ts['tileyoff'] + index_bits // columns * (height + ts['tilevsep']),
                                w=width, h=height, colour=0xffffffff, **tile_transform(value))
                    if animation:
                        # FrameData is read at draw time, so an animated tile
                        # carries its own tileset index instead of a baked frame.
                        tile['index'] = index_bits
                    room['tiles'].append(tile)
            elif kind == 'GMRAssetLayer':
                for graphic in layer['assets']:
                    if graphic.get('ignore'):
                        continue
                    if graphic.get('inheritItemSettings') or graphic.get('properties'):
                        raise GMS2Error(f'{name}/{graphic["name"]}: unsupported asset overrides')
                    sprite_name = ref_name(graphic['spriteId'])
                    item = {'sprite': self.asset('sprites', graphic['spriteId']), 'depth': depth,
                            'visible': visible, 'yellow': True, 'layer': index,
                            'x': graphic['x'], 'y': graphic['y'],
                            'colour': graphic.get('colour', 0xffffffff),
                            'resourceType': graphic['resourceType']}
                    if graphic['resourceType'] == 'GMRGraphic':
                        item.update(xo=graphic['u0'], yo=graphic['v0'],
                                    w=graphic['u1'] - graphic['u0'], h=graphic['v1'] - graphic['v0'])
                        if item['w'] == 0 or item['h'] == 0:
                            raise GMS2Error(f'{name}/{graphic["name"]}: empty source rectangle')
                        item.update(scaleX=graphic['w'] / item['w'], scaleY=graphic['h'] / item['h'])
                    elif graphic['resourceType'] == 'GMRSpriteGraphic':
                        frames = len(self.sprite_record(sprite_name).get('frames') or [])
                        # The item's animationSpeed multiplies the sprite's own
                        # playback speed; frozen stops the item on its first frame.
                        speed = float(graphic.get('animationSpeed', 1) or 0)
                        item.update(scaleX=graphic['scaleX'], scaleY=graphic['scaleY'],
                                    rotation=graphic['rotation'], headPosition=graphic.get('headPosition', 0),
                                    frame=graphic.get('headPosition', 0), frames=frames,
                                    speed=0 if graphic.get('frozen') else speed * self.sprite_speed(sprite_name))
                        if graphic.get('frozen'):
                            self.counts['frozen_sprites'] += 1
                    else:
                        stop('asset ' + graphic['resourceType'] + ': ' + graphic['name'])
                    room['tiles'].append(item)
            elif kind == 'GMRBackgroundLayer':
                if layer.get('spriteId'):
                    sprite_name = ref_name(layer['spriteId'])
                    frames = len(self.sprite_record(sprite_name).get('frames') or [])
                    fps = float(layer.get('animationFPS') or 0)
                    # animationSpeedType 0 authors the layer's speed in frames
                    # per second, 1 in frames per game frame; Yellow's own game
                    # speed converts the first into this runtime's unit.
                    per_step = fps if int(layer.get('animationSpeedType', 1) or 0) == 1 else fps / max(1, self.speed)
                    room['tiles'].append({
                        'sprite': self.asset('sprites', layer['spriteId']), 'backgroundLayer': True,
                        'depth': depth, 'visible': visible, 'yellow': True, 'layer': index,
                        'x': 0, 'y': 0, 'colour': layer['colour'],
                        'stretch': bool(layer.get('stretch')), 'htiled': bool(layer.get('htiled')),
                        'vtiled': bool(layer.get('vtiled')), 'frame': 0, 'frames': frames,
                        'speed': per_step if frames > 1 else 0,
                    })
                elif visible:
                    colour = layer['colour']
                    if colour >> 24 == 0:
                        continue  # fully transparent: Studio 2 draws nothing
                    if layer['name'] == 'Compatibility_Colour':
                        # A GM1 room's own background colour, which Studio 2
                        # stores as this layer on import.
                        room['colour'] = colour & 0xffffff
                    room['tiles'].append({'colourLayer': True, 'depth': depth, 'visible': True,
                                          'yellow': True, 'layer': index, 'colour': colour})
            elif kind not in ('GMREffectLayer', 'GMRPathLayer'):
                stop('layer ' + kind + ': ' + layer['name'])
        order = [ref_name(entry) for entry in data['instanceCreationOrder']]
        if len(order) != len(set(order)) or set(order) != set(instances):
            raise GMS2Error(f'{name}: creation order does not match room instances')
        room['instances'] = [instances[n] for n in order]
        self.counts['instances'] += len(order)
        self.counts['drawables'] += len(room['tiles'])
        self.counts['layers'] += len(room['layers'])
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
                    counts=dict(self.counts), unsupported=self.stops,
                    animated_tilesets={name: record for name, record in sorted(self.animations.items()) if record})
