# -*- coding: utf-8 -*-
from __future__ import division
import random
import json

DEFAULTS = dict(nx=3, nz=3, block_x=8000, block_z=8000, road=1400,
                sidewalk=300, lots_x=3, lots_z=3, gap=350,
                density=0.85, height_min=1200, height_max=6000, seed=1)


def validate(c):
    for key in ('nx', 'nz', 'lots_x', 'lots_z'):
        if int(c[key]) != c[key] or c[key] < 1:
            raise ValueError('Block and lot counts must be positive integers.')
    if c['nx'] * c['nz'] * c['lots_x'] * c['lots_z'] > 2000:
        raise ValueError('Maximum 2000 building lots. Reduce block or lot counts.')
    if min(c[k] for k in ('block_x', 'block_z', 'road', 'height_min')) <= 0:
        raise ValueError('Dimensions must be positive.')
    if c['height_max'] < c['height_min'] or not 0 <= c['density'] <= 1 or min(c['sidewalk'], c['gap']) < 0:
        raise ValueError('Check height range, density and spacing.')
    for axis in ('x', 'z'):
        cell = (c['block_' + axis] - 2 * c['sidewalk']) / c['lots_' + axis]
        if cell <= c['gap']:
            raise ValueError('Sidewalk or building spacing too large for the lots.')


def block_plan(c, ix, iz, variant=0):
    validate(c)
    if not 0 <= ix < c['nx'] or not 0 <= iz < c['nz']:
        raise ValueError('Block index outside city.')
    rng = random.Random(int(c['seed']) + ix * 73856093 + iz * 19349663 + variant * 83492791)
    cell_x = (c['block_x'] - 2 * c['sidewalk']) / c['lots_x']
    cell_z = (c['block_z'] - 2 * c['sidewalk']) / c['lots_z']
    result = []
    for x in range(c['lots_x']):
        for z in range(c['lots_z']):
            occupied = rng.random() <= c['density']
            width = (cell_x - c['gap']) * rng.uniform(0.75, 1)
            depth = (cell_z - c['gap']) * rng.uniform(0.75, 1)
            height = rng.uniform(c['height_min'], c['height_max'])
            if occupied:
                result.append(('building_%d_%d' % (x, z),
                               (c['sidewalk'] + (x + 0.5) * cell_x, height / 2 + 20,
                                c['sidewalk'] + (z + 0.5) * cell_z, width, height, depth)))
    return result


def road_plan(c):
    validate(c)
    total_x = c['nx'] * c['block_x'] + (c['nx'] + 1) * c['road']
    total_z = c['nz'] * c['block_z'] + (c['nz'] + 1) * c['road']
    result = []
    for x in range(c['nx'] + 1):
        result.append(('road_z_%d' % x, (x * (c['block_x'] + c['road']) + c['road'] / 2,
                       -10, total_z / 2, c['road'], 20, total_z)))
    for z in range(c['nz'] + 1):
        for x in range(c['nx']):
            result.append(('road_x_%d_%d' % (x, z),
                           (c['road'] + x * (c['block_x'] + c['road']) + c['block_x'] / 2,
                            -10, z * (c['block_z'] + c['road']) + c['road'] / 2,
                            c['block_x'], 20, c['road'])))
    return result, (total_x, total_z)


def _group(cmds, name, parent=None):
    node = cmds.group(empty=True, name=name, **({'parent': parent} if parent else {}))
    return cmds.ls(node, long=True)[0]


def _box(cmds, parent, name, box, color):
    node = cmds.polyCube(name=parent.rsplit('|', 1)[-1] + '_' + name + '#',
                         width=box[3], height=box[4], depth=box[5], constructionHistory=False)[0]
    node = cmds.ls(node, long=True)[0]
    child = cmds.parent(node, parent)[0]
    node = parent + '|' + child.rsplit('|', 1)[-1]
    cmds.setAttr(node + '.translate', *box[:3])
    shape = cmds.listRelatives(node, shapes=True, fullPath=True)[0]
    cmds.setAttr(shape + '.overrideEnabled', True)
    cmds.setAttr(shape + '.overrideRGBColors', True)
    cmds.setAttr(shape + '.overrideColorRGB', *color)
    return node


def _block(cmds, root, c, ix, iz, variant=0):
    group = _group(cmds, 'block_%02d_%02d#' % (ix, iz), root)
    cmds.setAttr(group + '.translate', c['road'] + ix * (c['block_x'] + c['road']), 0,
                 c['road'] + iz * (c['block_z'] + c['road']))
    for name, value in (('cityBlockX', ix), ('cityBlockZ', iz), ('cityVariant', variant)):
        cmds.addAttr(group, longName=name, attributeType='long', defaultValue=value)
    walk = _group(cmds, 'sidewalk#', group)
    _box(cmds, walk, 'front', (c['block_x']/2, 10, c['sidewalk']/2, c['block_x'], 20, c['sidewalk']), (0.5, 0.51, 0.53)) if c['sidewalk'] else None
    if c['sidewalk']:
        s = c['sidewalk']
        _box(cmds, walk, 'back', (c['block_x']/2, 10, c['block_z']-s/2, c['block_x'], 20, s), (0.5,0.51,0.53))
        for x in (s/2, c['block_x']-s/2):
            _box(cmds, walk, 'side', (x,10,c['block_z']/2,s,20,c['block_z']-2*s), (0.5,0.51,0.53))
    buildings = _group(cmds, 'buildings#', group)
    for name, box in block_plan(c, ix, iz, variant):
        _box(cmds, buildings, name, box, (0.7, 0.73, 0.77))
    return group


def build(c, previous=None):
    import maya.cmds as cmds
    validate(c)
    if previous and cmds.objExists(previous) and not cmds.attributeQuery('cityConfig', node=previous, exists=True):
        raise ValueError('Select a generated city group.')
    cmds.undoInfo(openChunk=True, chunkName='City PCG Generate')
    root = None
    try:
        matrix = cmds.xform(previous, query=True, worldSpace=True, matrix=True) if previous and cmds.objExists(previous) else None
        root = _group(cmds, 'City_whitebox#')
        cmds.addAttr(root, longName='cityConfig', dataType='string')
        cmds.setAttr(root + '.cityConfig', json.dumps(c), type='string')
        roads = _group(cmds, 'roads#', root)
        boxes, extent = road_plan(c)
        for name, box in boxes:
            _box(cmds, roads, name, box, (0.22,0.24,0.27))
        blocks = _group(cmds, 'blocks#', root)
        for x in range(c['nx']):
            for z in range(c['nz']):
                _block(cmds, blocks, c, x, z)
        if matrix:
            cmds.xform(root, worldSpace=True, matrix=matrix)
        if previous and cmds.objExists(previous):
            cmds.delete(previous)
        cmds.select(root)
        return root
    except Exception:
        if root and cmds.objExists(root):
            cmds.delete(root)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)


def find_city(node):
    import maya.cmds as cmds
    node = cmds.ls(node, long=True)[0]
    while node:
        if cmds.attributeQuery('cityConfig', node=node, exists=True):
            return node
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        node = parents[0] if parents else None
    raise ValueError('Select a city or an object inside it.')


def update_block(node, c):
    import maya.cmds as cmds
    node = cmds.ls(node, long=True)[0]
    while not cmds.attributeQuery('cityBlockX', node=node, exists=True):
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        if not parents:
            raise ValueError('Select a block or a building within a block.')
        node = parents[0]
    root = find_city(node)
    old = json.loads(cmds.getAttr(root + '.cityConfig'))
    for key in ('nx','nz','block_x','block_z','road','sidewalk'):
        if c[key] != old[key]:
            raise ValueError('Road or block layout changed. Update the whole city first.')
    ix, iz = [cmds.getAttr(node + '.' + key) for key in ('cityBlockX','cityBlockZ')]
    variant = cmds.getAttr(node + '.cityVariant') + 1
    block_plan(c, ix, iz, variant)
    parent = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    cmds.undoInfo(openChunk=True, chunkName='City PCG Update Block')
    result = None
    try:
        result = _block(cmds, parent, c, ix, iz, variant)
        cmds.delete(node)
        cmds.select(result)
        return result
    except Exception:
        if result and cmds.objExists(result):
            cmds.delete(result)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
