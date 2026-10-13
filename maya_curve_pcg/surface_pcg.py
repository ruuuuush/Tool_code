# -*- coding: utf-8 -*-
from __future__ import division

import bisect
import math
import random


def scatter(sources, surface, count=100, seed=1, scale_min=0.8, scale_max=1.2,
            slope=45, previous=None):
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    if not sources or count < 1 or count > 2000:
        raise ValueError(u'请选择模型，数量范围为 1–2000。')
    if scale_min <= 0 or scale_max < scale_min or not 0 <= slope <= 90:
        raise ValueError(u'请检查缩放范围和坡度（0–90°）。')
    sources = [cmds.ls(node, long=True)[0] for node in sources]
    surface = cmds.ls(surface, long=True)[0]
    for node in sources:
        if not cmds.listRelatives(node, allDescendents=True, type='mesh'):
            raise ValueError(u'源模型必须包含多边形网格。')
    if previous and any(node == previous or node.startswith(previous + '|') for node in sources + [surface]):
        raise ValueError(u'模型和地面不能放在待更新结果内。')
    shapes = cmds.listRelatives(surface, shapes=True, noIntermediate=True, fullPath=True, type='mesh') or []
    if len(shapes) != 1:
        raise ValueError(u'请选择包含一个网格的地面对象。')
    selection = om.MSelectionList()
    selection.add(shapes[0])
    fn = om.MFnMesh(selection.getDagPath(0))
    points = fn.getPoints(om.MSpace.kWorld)
    counts, indices = fn.getTriangles()
    triangles = []
    weights = []
    total = 0
    threshold = math.cos(math.radians(slope))
    for index in range(0, len(indices), 3):
        a, b, c = [points[indices[index + offset]] for offset in range(3)]
        normal = (b - a) ^ (c - a)
        area = normal.length() / 2
        if area <= 1e-10:
            continue
        normal.normalize()
        if normal.y < threshold - 1e-8:
            continue
        total += area
        weights.append(total)
        triangles.append((a, b, c, normal))
    if not triangles:
        raise ValueError(u'没有满足坡度条件的朝上三角面；检查地面法线或增大坡度。')
    rng = random.Random(seed)
    cmds.undoInfo(openChunk=True, chunkName='PCG Surface Scatter')
    group = None
    try:
        group = cmds.group(empty=True, name='PCG_scatter#')
        group = cmds.ls(group, long=True)[0]
        cmds.addAttr(group, longName='pcgScatter', attributeType='bool', defaultValue=True)
        cmds.addAttr(group, longName='pcgSurface', attributeType='message')
        cmds.connectAttr(surface + '.message', group + '.pcgSurface')
        cmds.addAttr(group, longName='pcgSources', attributeType='message', multi=True)
        for index, node in enumerate(sources):
            cmds.connectAttr(node + '.message', '%s.pcgSources[%d]' % (group, index))
        for attr, value in (('pcgCount', count), ('pcgSeed', seed), ('pcgScaleMin', scale_min), ('pcgScaleMax', scale_max), ('pcgSlope', slope)):
            cmds.addAttr(group, longName=attr, attributeType='double', defaultValue=value)
        for index in range(count):
            a, b, c, normal = triangles[bisect.bisect_right(weights, rng.random() * total)]
            u = math.sqrt(rng.random())
            v = rng.random()
            point = a + (b - a) * (u * (1 - v)) + (c - a) * (u * v)
            name = '%s_item_%03d#' % (group.rsplit('|', 1)[-1], index)
            item = cmds.instance(rng.choice(sources), name=name)[0]
            item = cmds.ls(item, long=True)[0]
            parented = cmds.parent(item, group)[0]
            item = group + '|' + parented.rsplit('|', 1)[-1]
            align = om.MVector(0, 1, 0).rotateTo(normal)
            spin = om.MQuaternion(rng.uniform(0, math.pi * 2), om.MVector(0, 1, 0))
            rotation = (spin * align).asEulerRotation()
            cmds.xform(item, worldSpace=True, rotation=[math.degrees(value) for value in (rotation.x, rotation.y, rotation.z)])
            factor = rng.uniform(scale_min, scale_max)
            base = cmds.getAttr(item + '.scale')[0]
            cmds.setAttr(item + '.scale', *[value * factor for value in base])
            pivot = cmds.xform(item, query=True, worldSpace=True, rotatePivot=True)
            cmds.move(point.x - pivot[0], point.y - pivot[1], point.z - pivot[2], item, relative=True, worldSpace=True)
            cmds.setAttr(item + '.visibility', True)
        if previous and cmds.objExists(previous):
            cmds.delete(previous)
        cmds.select(group)
        return group
    except Exception:
        if group and cmds.objExists(group):
            cmds.delete(group)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)


def show_panel(cmds, create_example, independent_result):
    state = {'result': None}
    cmds.columnLayout(adjustableColumn=True, rowSpacing=9, columnAttach=('both', 14))
    cmds.text(label=u'表面散布', align='left', font='boldLabelFont', height=28)
    sources_field = cmds.textFieldButtonGrp(label=u'模型池', buttonLabel=u'读取多选', columnWidth3=(60, 350, 85))
    surface_field = cmds.textFieldButtonGrp(label=u'地面', buttonLabel=u'读取选择', columnWidth3=(60, 350, 85))
    cmds.text(label=u'模型池支持多个模型；每个实例随机选择一个。', align='left')
    count_field = cmds.intFieldGrp(label=u'数量', value1=100)
    seed_field = cmds.intFieldGrp(label=u'随机种子', value1=1)
    scale_field = cmds.floatFieldGrp(label=u'缩放范围', numberOfFields=2, value1=0.8, value2=1.2, precision=2)
    slope_field = cmds.floatFieldGrp(label=u'最大坡度', value1=45, precision=1)
    message = cmds.text(label=u'按三角面面积均匀采样，模型 Y 轴贴合表面法线。', align='left', wordWrap=True, height=40)
    generate_button = cmds.button(label=u'生成 / 更新散布', height=36, backgroundColor=(0.28, 0.39, 0.46))
    result_menu = cmds.optionMenu(label=u'场景散布')
    cmds.menuItem(label=u'新散布')
    cmds.rowLayout(numberOfColumns=4, adjustableColumn=4)
    new_button = cmds.button(label=u'新散布')
    focus_button = cmds.button(label=u'聚焦')
    clear_button = cmds.button(label=u'清除')
    copy_button = cmds.button(label=u'独立副本')
    cmds.setParent('..')
    demo_button = cmds.button(label=u'演示：石块 + 地面 + 散布')
    cmds.text(label=u'固定种子可复现结果。不会自动避让，石块可能重叠。\n修改参数后手动更新；更新替换选中散布，源模型和地面保留。', align='left', wordWrap=True)

    def rebuild():
        for item in cmds.optionMenu(result_menu, query=True, itemListLong=True) or []:
            cmds.deleteUI(item)
        cmds.menuItem(label=u'新散布', parent=result_menu)
        groups = cmds.ls('*.pcgScatter', objectsOnly=True, long=True) or []
        for group in groups:
            cmds.menuItem(label=group, parent=result_menu)
        if state['result'] in groups:
            cmds.optionMenu(result_menu, edit=True, value=state['result'])

    def read(field, multiple):
        nodes = cmds.ls(selection=True, long=True, type='transform') or []
        if not nodes or (not multiple and len(nodes) != 1):
            cmds.warning(u'请选择模型，或一个地面对象。')
            return
        cmds.textFieldButtonGrp(field, edit=True, text=';'.join(nodes))

    def run(*unused):
        try:
            sources = [node.strip() for node in cmds.textFieldButtonGrp(sources_field, query=True, text=True).split(';') if node.strip()]
            group = scatter(sources, cmds.textFieldButtonGrp(surface_field, query=True, text=True),
                            cmds.intFieldGrp(count_field, query=True, value1=True),
                            cmds.intFieldGrp(seed_field, query=True, value1=True),
                            cmds.floatFieldGrp(scale_field, query=True, value1=True),
                            cmds.floatFieldGrp(scale_field, query=True, value2=True),
                            cmds.floatFieldGrp(slope_field, query=True, value1=True), state['result'])
            state['result'] = group
            rebuild()
            cmds.text(message, edit=True, label=u'已生成散布：' + group)
        except Exception as error:
            cmds.text(message, edit=True, label=u'失败：' + str(error))
            cmds.warning(str(error))

    def load(*unused):
        group = cmds.optionMenu(result_menu, query=True, value=True)
        state['result'] = None if group == u'新散布' else group
        if not state['result']:
            return
        sources = cmds.listConnections(group + '.pcgSources', source=True, destination=False) or []
        target = cmds.listConnections(group + '.pcgSurface', source=True, destination=False) or []
        cmds.textFieldButtonGrp(sources_field, edit=True, text=';'.join(cmds.ls(sources, long=True) if sources else []))
        cmds.textFieldButtonGrp(surface_field, edit=True, text=cmds.ls(target[0], long=True)[0] if target else '')
        for field, attr in ((count_field, 'pcgCount'), (seed_field, 'pcgSeed')):
            cmds.intFieldGrp(field, edit=True, value1=int(cmds.getAttr(group + '.' + attr)))
        cmds.floatFieldGrp(scale_field, edit=True, value1=cmds.getAttr(group + '.pcgScaleMin'), value2=cmds.getAttr(group + '.pcgScaleMax'))
        cmds.floatFieldGrp(slope_field, edit=True, value1=cmds.getAttr(group + '.pcgSlope'))

    def new(*unused):
        state['result'] = None
        cmds.optionMenu(result_menu, edit=True, value=u'新散布')

    def focus(*unused):
        if state['result'] and cmds.objExists(state['result']):
            cmds.select(state['result'])
            cmds.viewFit()

    def clear(*unused):
        group = state['result']
        if not group or not cmds.objExists(group):
            return
        if cmds.confirmDialog(title=u'清除散布', message=u'仅删除当前散布实例，保留模型和地面。', button=[u'清除', u'取消'], defaultButton=u'取消', cancelButton=u'取消', dismissString=u'取消') == u'清除':
            cmds.delete(group)
            state['result'] = None
            rebuild()

    def copy(*unused):
        if state['result'] and cmds.objExists(state['result']):
            independent_result(state['result'])

    def demo(*unused):
        new()
        model = create_example('rock')
        ground = cmds.polyPlane(name='PCG_demo_ground#', width=1600, height=1200, subdivisionsX=12, subdivisionsY=12, constructionHistory=False)[0]
        cmds.textFieldButtonGrp(sources_field, edit=True, text=model)
        cmds.textFieldButtonGrp(surface_field, edit=True, text=cmds.ls(ground, long=True)[0])
        run()
        focus()

    cmds.textFieldButtonGrp(sources_field, edit=True, buttonCommand=lambda *a: read(sources_field, True))
    cmds.textFieldButtonGrp(surface_field, edit=True, buttonCommand=lambda *a: read(surface_field, False))
    for button, callback in ((generate_button, run), (new_button, new), (focus_button, focus), (clear_button, clear), (copy_button, copy), (demo_button, demo)):
        cmds.button(button, edit=True, command=callback)
    cmds.optionMenu(result_menu, edit=True, changeCommand=load)
    rebuild()
