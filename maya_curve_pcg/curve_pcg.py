# -*- coding: utf-8 -*-
from __future__ import division

import math
import random

WINDOW = 'curvePCGWindow'


def sample_distances(length, spacing, closed=False, limit=2000):
    if spacing <= 0 or length <= 0:
        raise ValueError('Curve length and spacing must be positive.')
    count = int(math.floor(length / spacing + 1e-8)) + 1
    if closed and abs((count - 1) * spacing - length) < 1e-7:
        count -= 1
    if count > limit:
        raise ValueError('Too many instances. Increase spacing (maximum %d).' % limit)
    return [min(index * spacing, length) for index in range(count)]


def _maya():
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    return cmds, om


def curve_metrics(curve):
    cmds, om = _maya()
    shapes = cmds.listRelatives(curve, shapes=True, noIntermediate=True,
                               fullPath=True, type='nurbsCurve') or []
    if not shapes:
        raise ValueError(u'请选择包含 NURBS 曲线的对象。')
    info = cmds.createNode('curveInfo', name='PCG_measure#')
    try:
        cmds.connectAttr(shapes[0] + '.worldSpace[0]', info + '.inputCurve')
        return cmds.getAttr(info + '.arcLength'), cmds.getAttr(shapes[0] + '.form') != 0
    finally:
        cmds.delete(info)


def independent_result(group):
    cmds, om = _maya()
    cmds.undoInfo(openChunk=True, chunkName='Curve PCG Independent')
    result = None
    try:
        result = cmds.group(empty=True, name='PCG_independent#')
        cmds.xform(result, worldSpace=True, matrix=cmds.xform(group, query=True, worldSpace=True, matrix=True))
        for child in cmds.listRelatives(group, children=True, fullPath=True, type='transform') or []:
            copy = cmds.duplicate(child, renameChildren=True)[0]
            cmds.parent(copy, result)
        cmds.select(result)
        return result
    except Exception:
        if result and cmds.objExists(result):
            cmds.delete(result)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)


def generate(source, curve, spacing=200.0, axis='X', previous=None,
             seed=1, scale_min=1.0, scale_max=1.0, yaw=0.0):
    cmds, om = _maya()
    if axis not in ('X', 'Z'):
        raise ValueError('Forward axis must be X or Z.')
    if spacing <= 0:
        raise ValueError(u'间距必须大于 0，当前值：%s' % spacing)
    sources = source if isinstance(source, (list, tuple)) else [source]
    if scale_min <= 0 or scale_max < scale_min or yaw < 0:
        raise ValueError(u'缩放范围必须为正且从小到大，朝向随机范围不能为负。')
    rng = random.Random(seed)
    if not sources or not cmds.objExists(curve) or any(not cmds.objExists(node) for node in sources):
        raise ValueError(u'模型或目标不存在。')
    sources = [cmds.ls(node, long=True)[0] for node in sources]
    source = sources[0]
    curve = cmds.ls(curve, long=True)[0]
    for node in sources:
        if not cmds.listRelatives(node, allDescendents=True, type='mesh'):
            raise ValueError(u'请选择多边形模型或模型组。')
    shapes = cmds.listRelatives(curve, shapes=True, noIntermediate=True,
                               fullPath=True, type='nurbsCurve') or []
    if not shapes:
        raise ValueError(u'请选择包含 NURBS 曲线的对象。')
    shape = shapes[0]
    if previous and cmds.objExists(previous):
        if any(node == previous or node.startswith(previous + '|') for node in sources) or curve == previous or curve.startswith(previous + '|'):
            raise ValueError('Source and curve cannot be inside the generated group.')
    cmds.undoInfo(openChunk=True, chunkName='Curve PCG Generate')
    group = None
    temporary = []
    try:
        info = cmds.createNode('curveInfo', name='PCG_curveInfo#')
        temporary.append(info)
        cmds.connectAttr(shape + '.worldSpace[0]', info + '.inputCurve')
        length = cmds.getAttr(info + '.arcLength')
        if length <= 0:
            raise ValueError(u'曲线世界长度为 %s，请检查曲线控制点和缩放。' % length)
        distances = sample_distances(length, spacing, cmds.getAttr(shape + '.form') != 0)
        path = cmds.createNode('motionPath', name='PCG_motionPath#')
        temporary.append(path)
        cmds.connectAttr(shape + '.worldSpace[0]', path + '.geometryPath')
        cmds.setAttr(path + '.fractionMode', True)
        cmds.setAttr(path + '.follow', True)
        cmds.setAttr(path + '.frontAxis', 0 if axis == 'X' else 2)
        cmds.setAttr(path + '.upAxis', 1)
        cmds.setAttr(path + '.worldUpType', 3)
        cmds.setAttr(path + '.worldUpVector', 0, 1, 0, type='double3')
        group = cmds.group(empty=True, name='PCG_result#')
        group = cmds.ls(group, long=True)[0]
        cmds.addAttr(group, longName='pcgResult', attributeType='bool', defaultValue=True)
        for name, node in (('pcgSource', source), ('pcgCurve', curve)):
            cmds.addAttr(group, longName=name, attributeType='message')
            cmds.connectAttr(node + '.message', group + '.' + name)
        cmds.addAttr(group, longName='pcgSpacing', attributeType='double', defaultValue=spacing)
        cmds.addAttr(group, longName='pcgAxis', dataType='string')
        cmds.setAttr(group + '.pcgAxis', axis, type='string')
        cmds.addAttr(group, longName='pcgSources', attributeType='message', multi=True)
        for index, node in enumerate(sources):
            cmds.connectAttr(node + '.message', '%s.pcgSources[%d]' % (group, index))
        for attr, value in (('pcgSeed', seed), ('pcgScaleMin', scale_min), ('pcgScaleMax', scale_max), ('pcgYaw', yaw)):
            cmds.addAttr(group, longName=attr, attributeType='double', defaultValue=value)
        for index, distance in enumerate(distances):
            cmds.setAttr(path + '.uValue', distance / length)
            point = cmds.getAttr(path + '.allCoordinates')[0]
            rotation = cmds.getAttr(path + '.rotate')[0]
            name = '%s_item_%03d#' % (group.rsplit('|', 1)[-1], index)
            chosen = rng.choice(sources)
            instance = cmds.instance(chosen, name=name)[0]
            instance = cmds.ls(instance, long=True)[0]
            parented = cmds.parent(instance, group)[0]
            instance = group + '|' + parented.rsplit('|', 1)[-1]
            cmds.xform(instance, worldSpace=True, translation=point)
            cmds.xform(instance, worldSpace=True, rotation=rotation)
            cmds.rotate(0, rng.uniform(-yaw, yaw), 0, instance, relative=True, objectSpace=True)
            factor = rng.uniform(scale_min, scale_max)
            base_scale = cmds.getAttr(instance + '.scale')[0]
            cmds.setAttr(instance + '.scale', *[value * factor for value in base_scale])
            pivot = cmds.xform(instance, query=True, worldSpace=True, rotatePivot=True)
            cmds.move(point[0] - pivot[0], point[1] - pivot[1], point[2] - pivot[2],
                      instance, relative=True, worldSpace=True)
            cmds.setAttr(instance + '.visibility', True)
        if previous and cmds.objExists(previous):
            cmds.delete(previous)
        cmds.select(group)
        return cmds.ls(group, long=True)[0], len(distances)
    except Exception:
        if group and cmds.objExists(group):
            cmds.delete(group)
        raise
    finally:
        for node in temporary:
            if cmds.objExists(node):
                cmds.delete(node)
        cmds.undoInfo(closeChunk=True)


def create_example(kind='fence'):
    cmds, om = _maya()
    cmds.undoInfo(openChunk=True, chunkName='Curve PCG Example')
    try:
        parts = []
        if kind == 'fence':
            for x in (0, 200):
                part = cmds.polyCube(width=12, height=130, depth=12, constructionHistory=False)[0]
                cmds.move(x, 65, 0, part, absolute=True)
                parts.append(part)
            for x in (30, 65, 100, 135, 170):
                part = cmds.polyCube(width=8, height=110, depth=8, constructionHistory=False)[0]
                cmds.move(x, 58, 0, part, absolute=True)
                parts.append(part)
            for y in (40, 95):
                part = cmds.polyCube(width=200, height=10, depth=8, constructionHistory=False)[0]
                cmds.move(100, y, 0, part, absolute=True)
                parts.append(part)
        elif kind == 'lamp':
            part = cmds.polyCylinder(radius=5, height=300, subdivisionsX=10, constructionHistory=False)[0]
            cmds.move(0, 150, 0, part, absolute=True)
            parts.append(part)
            part = cmds.polyCube(width=65, height=6, depth=6, constructionHistory=False)[0]
            cmds.move(28, 300, 0, part, absolute=True)
            parts.append(part)
            part = cmds.polyCube(width=32, height=10, depth=20, constructionHistory=False)[0]
            cmds.move(55, 292, 0, part, absolute=True)
            parts.append(part)
            part = cmds.polyCylinder(radius=15, height=8, subdivisionsX=10, constructionHistory=False)[0]
            cmds.move(0, 4, 0, part, absolute=True)
            parts.append(part)
        elif kind == 'rock':
            part = cmds.polySphere(radius=45, subdivisionsX=8, subdivisionsY=5, constructionHistory=False)[0]
            cmds.scale(1.3, 0.65, 0.9, part, absolute=True)
            cmds.move(0, 29, 0, part, absolute=True)
            parts.append(part)
        else:
            raise ValueError('Unknown example model.')
        if len(parts) > 1:
            model = cmds.polyUnite(parts, constructionHistory=False, name='PCG_%s_source#' % kind)[0]
        else:
            model = cmds.rename(parts[0], 'PCG_%s_source#' % kind)
        cmds.makeIdentity(model, apply=True, translate=True, rotate=True, scale=True)
        cmds.xform(model, worldSpace=True, pivots=(0, 0, 0))
        colors = {'fence': (0.32, 0.22, 0.14), 'lamp': (0.22, 0.26, 0.3), 'rock': (0.4, 0.43, 0.46)}
        for shape in cmds.listRelatives(model, shapes=True, fullPath=True) or []:
            cmds.setAttr(shape + '.overrideEnabled', True)
            cmds.setAttr(shape + '.overrideRGBColors', True)
            cmds.setAttr(shape + '.overrideColorRGB', *colors[kind])
        cmds.select(model)
        return cmds.ls(model, long=True)[0]
    finally:
        cmds.undoInfo(closeChunk=True)


def create_demo_curve():
    cmds, om = _maya()
    return cmds.curve(name='PCG_demo_curve#', degree=3,
                      point=[(0, 0, 0), (350, 0, 0), (650, 0, 300),
                             (1000, 0, 400), (1400, 0, 100), (1800, 0, 100)])


def show():
    cmds, om = _maya()
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    state = {'result': None, 'busy': False, 'queued': False, 'jobs': []}
    cmds.window(WINDOW, title=u'Maya PCG · 0.5', widthHeight=(560, 650), sizeable=True)
    tabs = cmds.tabLayout(innerMarginWidth=8, innerMarginHeight=8)
    curve_panel = cmds.columnLayout(adjustableColumn=True, rowSpacing=7, columnAttach=('both', 12))
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1)
    capture_button = cmds.button(label=u'识别选择：模型 + 曲线', height=30)
    draw_button = cmds.button(label=u'画路线')
    new_button = cmds.button(label=u'新建排列')
    cmds.setParent('..')
    model_field = cmds.textFieldButtonGrp(label=u'模型', buttonLabel=u'选中读取', columnWidth3=(45, 330, 85))
    curve_field = cmds.textFieldButtonGrp(label=u'路线', buttonLabel=u'选中读取', columnWidth3=(45, 330, 85))
    cmds.rowLayout(numberOfColumns=4, adjustableColumn=4)
    fence_button = cmds.button(label=u'围栏示例')
    lamp_button = cmds.button(label=u'路灯示例')
    rock_button = cmds.button(label=u'石块示例')
    demo_curve_button = cmds.button(label=u'示例路线')
    cmds.setParent('..')
    axis_field = cmds.optionMenuGrp(label=u'前进轴', columnWidth2=(65, 90))
    cmds.menuItem(label='X')
    cmds.menuItem(label='Z')
    spacing_field = cmds.floatFieldGrp(label=u'间距', value1=200, precision=2, columnWidth2=(65, 100))
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
    auto_button = cmds.button(label=u'按模型尺寸')
    measure_button = cmds.button(label=u'刷新')
    live_field = cmds.checkBox(label=u'自动更新当前结果', value=True)
    cmds.setParent('..')
    cmds.textFieldButtonGrp(model_field, edit=True, label=u'模型池', buttonLabel=u'读取多选')
    seed_field = cmds.intFieldGrp(label=u'随机种子', value1=1)
    random_scale = cmds.floatFieldGrp(label=u'缩放范围', numberOfFields=2, value1=1, value2=1, precision=2)
    random_yaw = cmds.floatFieldGrp(label=u'朝向随机 ±°', value1=0, precision=1)
    cmds.text(label=u'多模型用分号分隔；默认不随机，适合围栏。', align='left')
    metrics = cmds.text(label=u'选模型和曲线，点击识别选择。', align='left', height=32)
    generate_button = cmds.button(label=u'生成排列', height=34, enable=False, backgroundColor=(0.28, 0.39, 0.46))
    result_menu = cmds.optionMenu(label=u'场景排列')
    cmds.menuItem(label=u'新排列')
    result_field = cmds.textFieldButtonGrp(label=u'结果', buttonLabel=u'读取选择', columnWidth3=(45, 330, 85))
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
    select_button = cmds.button(label=u'聚焦结果', enable=False)
    clear_button = cmds.button(label=u'清除结果', enable=False)
    independent_button = cmds.button(label=u'复制独立模型', enable=False)
    cmds.setParent('..')
    message = cmds.text(label=u'支持选择识别、画路线、切换场景排列。', align='left', wordWrap=True, height=34)
    demo_button = cmds.button(label=u'快速演示：围栏 + 路线')
    cmds.text(label=u'Y 向上 · 刚性排列，急弯可能留缝 · 自动更新最多 300 个实例\n大批量请手动更新；自动更新会替换当前结果内的手工调整。', align='left', wordWrap=True)

    def rebuild_menu():
        menu = result_menu
        for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
            cmds.deleteUI(item)
        cmds.menuItem(label=u'新排列', parent=menu)
        groups = [node for node in cmds.ls('*.pcgResult', objectsOnly=True, long=True) or []
                  if cmds.getAttr(node + '.pcgResult')]
        for group in groups:
            cmds.menuItem(label=group, parent=menu)
        if state['result'] in groups:
            cmds.optionMenu(result_menu, edit=True, value=state['result'])

    def schedule(*unused):
        if state['busy'] or state['queued'] or not cmds.checkBox(live_field, query=True, value=True):
            return
        if not result_group():
            refresh()
            return
        state['queued'] = True
        def update():
            state['queued'] = False
            if not cmds.window(WINDOW, exists=True) or state['busy']:
                return
            if not cmds.checkBox(live_field, query=True, value=True) or not result_group():
                return
            try:
                source, curve, spacing, axis = inputs()
                length, closed = curve_metrics(curve)
                if len(sample_distances(length, spacing, closed)) > 300:
                    cmds.text(message, edit=True, label=u'超过 300 个实例，请点击手动更新。')
                    refresh()
                    return
                selection = cmds.ls(selection=True, long=True) or []
                run()
                remaining = [node for node in selection if cmds.objExists(node)]
                if remaining:
                    cmds.select(remaining, replace=True)
            except Exception as error:
                report(error)
        cmds.evalDeferred(update, lowestPriority=True)

    def watch_curve():
        for job in state['jobs']:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job)
        state['jobs'] = []
        curve = cmds.textFieldButtonGrp(curve_field, query=True, text=True)
        if not curve or not cmds.objExists(curve):
            return
        shapes = cmds.listRelatives(curve, shapes=True, noIntermediate=True, fullPath=True, type='nurbsCurve') or []
        if shapes:
            for attribute in (shapes[0] + '.worldSpace[0]',):
                state['jobs'].append(cmds.scriptJob(attributeChange=[attribute, schedule], parent=WINDOW, compressUndo=True))

    def changed(*unused):
        refresh()
        schedule()

    def capture(*unused):
        try:
            nodes = cmds.ls(selection=True, long=True, objectsOnly=True) or []
            models = []
            for node in nodes:
                if cmds.nodeType(node) in ('mesh', 'nurbsCurve'):
                    node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
                if cmds.attributeQuery('pcgResult', node=node, exists=True):
                    cmds.optionMenu(result_menu, edit=True, value=node)
                    load_result()
                elif cmds.listRelatives(node, shapes=True, noIntermediate=True, type='nurbsCurve'):
                    cmds.textFieldButtonGrp(curve_field, edit=True, text=node)
                elif cmds.listRelatives(node, allDescendents=True, type='mesh'):
                    if node not in models:
                        models.append(node)
            if models:
                cmds.textFieldButtonGrp(model_field, edit=True, text=';'.join(models))
            watch_curve()
            changed()
        except Exception as error:
            report(error)

    def load_result(*unused):
        value = cmds.optionMenu(result_menu, query=True, value=True)
        state['result'] = None if value == u'新排列' else value
        cmds.textFieldButtonGrp(result_field, edit=True, text=state['result'] or '')
        group = result_group()
        if group:
            for attribute, field in (('pcgSource', model_field), ('pcgCurve', curve_field)):
                if cmds.attributeQuery(attribute, node=group, exists=True):
                    nodes = cmds.listConnections(group + '.' + attribute, source=True, destination=False) or []
                    cmds.textFieldButtonGrp(field, edit=True, text=cmds.ls(nodes[0], long=True)[0] if nodes else '')
            if cmds.attributeQuery('pcgSources', node=group, exists=True):
                nodes = cmds.listConnections(group + '.pcgSources', source=True, destination=False) or []
                cmds.textFieldButtonGrp(model_field, edit=True, text=';'.join(cmds.ls(nodes, long=True) if nodes else []))
            if cmds.attributeQuery('pcgSeed', node=group, exists=True):
                cmds.intFieldGrp(seed_field, edit=True, value1=int(cmds.getAttr(group + '.pcgSeed')))
                cmds.floatFieldGrp(random_scale, edit=True, value1=cmds.getAttr(group + '.pcgScaleMin'), value2=cmds.getAttr(group + '.pcgScaleMax'))
                cmds.floatFieldGrp(random_yaw, edit=True, value1=cmds.getAttr(group + '.pcgYaw'))
            if cmds.attributeQuery('pcgSpacing', node=group, exists=True):
                cmds.floatFieldGrp(spacing_field, edit=True, value1=cmds.getAttr(group + '.pcgSpacing'))
                cmds.optionMenuGrp(axis_field, edit=True, value=cmds.getAttr(group + '.pcgAxis'))
        watch_curve()
        refresh()

    def new_result(*unused):
        cmds.optionMenu(result_menu, edit=True, value=u'新排列')
        load_result()

    def draw(*unused):
        new_result()
        context = 'PCG_drawCurveContext'
        if not cmds.contextInfo(context, exists=True):
            cmds.curveEPCtx(context)
        cmds.setToolTo(context)
        cmds.text(message, edit=True, label=u'在视口点击绘制路线，回车完成，再点识别选择。')

    def report(error):
        cmds.text(message, edit=True, label=u'操作失败：' + str(error))
        cmds.warning(str(error))

    def inputs():
        return ([node.strip() for node in cmds.textFieldButtonGrp(model_field, query=True, text=True).split(';') if node.strip()],
                cmds.textFieldButtonGrp(curve_field, query=True, text=True),
                cmds.floatFieldGrp(spacing_field, query=True, value1=True),
                cmds.optionMenuGrp(axis_field, query=True, value=True))

    def result_group():
        group = state['result']
        if not group or not cmds.objExists(group):
            return None
        if not cmds.attributeQuery('pcgResult', node=group, exists=True):
            return None
        return group if cmds.getAttr(group + '.pcgResult') else None

    def refresh(*unused):
        group = result_group()
        for button in (select_button, clear_button, independent_button):
            cmds.button(button, edit=True, enable=bool(group))
        cmds.button(generate_button, edit=True, label=u'更新指定结果' if group else u'生成排列')
        try:
            source, curve, spacing, axis = inputs()
            if not source or any(not cmds.objExists(node) or not cmds.listRelatives(node, allDescendents=True, type='mesh') for node in source):
                raise ValueError(u'第 01 步：请选择有效模型。')
            if not curve or not cmds.objExists(curve):
                raise ValueError(u'第 02 步：请选择有效曲线。')
            length, closed = curve_metrics(curve)
            count = len(sample_distances(length, spacing, closed))
            cmds.text(metrics, edit=True, label=u'模型已就绪 · 曲线长度 %.2f · 预计 %d 个实例\n间距 %.2f · %s 前进 · %s曲线' % (length, count, spacing, axis, u'闭合' if closed else u'开放'))
            cmds.button(generate_button, edit=True, enable=True)
            return True
        except Exception as error:
            cmds.text(metrics, edit=True, label=str(error))
            cmds.button(generate_button, edit=True, enable=False)
            return False

    def read_selection(field, kind):
        try:
            selected = cmds.ls(selection=True, long=True, objectsOnly=True) or []
            if kind == 'model' and selected:
                nodes = []
                for node in selected:
                    if cmds.nodeType(node) == 'mesh':
                        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
                    if not cmds.listRelatives(node, allDescendents=True, type='mesh'):
                        raise ValueError(u'模型池只能包含多边形模型。')
                    if node not in nodes:
                        nodes.append(node)
                cmds.textFieldButtonGrp(field, edit=True, text=';'.join(nodes))
                changed()
                return
            if len(selected) != 1:
                raise ValueError(u'请选择一个对象。')
            node = selected[0]
            if cmds.nodeType(node) in ('mesh', 'nurbsCurve'):
                node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
            if kind == 'result':
                if not cmds.attributeQuery('pcgResult', node=node, exists=True) or not cmds.getAttr(node + '.pcgResult'):
                    raise ValueError(u'请选择本工具生成的 PCG_result 组，不能使用普通资产组。')
                state['result'] = node
            elif kind == 'curve':
                curve_metrics(node)
            elif not cmds.listRelatives(node, allDescendents=True, type='mesh'):
                raise ValueError(u'请选择多边形模型或模型组。')
            cmds.textFieldButtonGrp(field, edit=True, text=node)
            watch_curve()
            changed()
        except Exception as error:
            report(error)

    def run(*unused):
        if state['busy'] or not refresh():
            return
        state['busy'] = True
        try:
            source, curve, spacing, axis = inputs()
            group, count = generate(source, curve, spacing, axis, result_group(),
                                    cmds.intFieldGrp(seed_field, query=True, value1=True),
                                    cmds.floatFieldGrp(random_scale, query=True, value1=True),
                                    cmds.floatFieldGrp(random_scale, query=True, value2=True),
                                    cmds.floatFieldGrp(random_yaw, query=True, value1=True))
            state['result'] = group
            cmds.textFieldButtonGrp(result_field, edit=True, text=group)
            cmds.text(message, edit=True, label=u'已更新 %d 个实例。' % count)
            rebuild_menu()
            watch_curve()
            refresh()
        except Exception as error:
            report(error)
        finally:
            state['busy'] = False

    def example(kind):
        try:
            model = create_example(kind)
            cmds.textFieldButtonGrp(model_field, edit=True, text=model)
            cmds.optionMenuGrp(axis_field, edit=True, value='X')
            cmds.floatFieldGrp(spacing_field, edit=True, value1={'fence': 200, 'lamp': 300, 'rock': 120}[kind])
            cmds.text(message, edit=True, label=u'示例模型已切换。')
            changed()
        except Exception as error:
            report(error)

    def demo_curve(*unused):
        curve = create_demo_curve()
        cmds.textFieldButtonGrp(curve_field, edit=True, text=cmds.ls(curve, long=True)[0])
        watch_curve()
        changed()

    def auto_spacing(*unused):
        try:
            source, curve, spacing, axis = inputs()
            if not source or not cmds.objExists(source[0]):
                raise ValueError(u'请先指定源模型。')
            source = source[0]
            bounds = cmds.xform(source, query=True, objectSpace=True, boundingBox=True)
            index = 0 if axis == 'X' else 2
            scale = cmds.getAttr(source + '.scale')[0][index]
            value = (bounds[index + 3] - bounds[index]) * abs(scale)
            if value <= 0:
                raise ValueError(u'模型在所选前进轴上的尺寸为 0。')
            cmds.floatFieldGrp(spacing_field, edit=True, value1=value)
            cmds.text(message, edit=True, label=u'建议间距 %.2f；可继续手动调整。' % value)
            changed()
        except Exception as error:
            report(error)

    def focus(*unused):
        group = result_group()
        if group:
            cmds.select(group)
            cmds.viewFit()

    def clear(*unused):
        group = result_group()
        if not group:
            refresh()
            return
        answer = cmds.confirmDialog(title=u'清除生成结果', message=u'仅删除结果组及其中实例：\n%s\n源模型、曲线和独立副本保留。' % group,
                                    button=[u'清除', u'取消'], defaultButton=u'取消', cancelButton=u'取消', dismissString=u'取消')
        if answer != u'清除':
            return
        cmds.delete(group)
        state['result'] = None
        cmds.textFieldButtonGrp(result_field, edit=True, text='')
        cmds.text(message, edit=True, label=u'已清除生成结果，源模型和曲线保留。')
        rebuild_menu()
        refresh()

    def independent(*unused):
        try:
            group = result_group()
            if not group:
                raise ValueError(u'请先生成或读取结果组。')
            result = independent_result(group)
            cmds.text(message, edit=True, label=u'独立副本：%s。原实例结果保留。' % result)
        except Exception as error:
            report(error)

    def demo(*unused):
        new_result()
        example('fence')
        demo_curve()
        run()
        focus()

    cmds.textFieldButtonGrp(model_field, edit=True, buttonCommand=lambda *a: read_selection(model_field, 'model'), changeCommand=changed)
    cmds.textFieldButtonGrp(curve_field, edit=True, buttonCommand=lambda *a: read_selection(curve_field, 'curve'), changeCommand=lambda *a: (watch_curve(), changed()))
    cmds.textFieldButtonGrp(result_field, edit=True, editable=False, buttonCommand=lambda *a: read_selection(result_field, 'result'))
    cmds.floatFieldGrp(spacing_field, edit=True, changeCommand=changed)
    cmds.optionMenuGrp(axis_field, edit=True, changeCommand=changed)
    cmds.optionMenu(result_menu, edit=True, changeCommand=load_result)
    cmds.checkBox(live_field, edit=True, changeCommand=changed)
    cmds.button(capture_button, edit=True, command=capture)
    cmds.button(draw_button, edit=True, command=draw)
    cmds.button(new_button, edit=True, command=new_result)
    cmds.button(fence_button, edit=True, command=lambda *a: example('fence'))
    cmds.button(lamp_button, edit=True, command=lambda *a: example('lamp'))
    cmds.button(rock_button, edit=True, command=lambda *a: example('rock'))
    for button, callback in ((demo_curve_button, demo_curve), (auto_button, auto_spacing),
                             (measure_button, refresh), (generate_button, run), (select_button, focus),
                             (clear_button, clear), (independent_button, independent), (demo_button, demo)):
        cmds.button(button, edit=True, command=callback)
    cmds.intFieldGrp(seed_field, edit=True, changeCommand=changed)
    cmds.floatFieldGrp(random_scale, edit=True, changeCommand=changed)
    cmds.floatFieldGrp(random_yaw, edit=True, changeCommand=changed)
    cmds.setParent(tabs)
    import surface_pcg
    surface_panel = cmds.columnLayout(adjustableColumn=True)
    surface_pcg.show_panel(cmds, create_example, independent_result)
    cmds.setParent(tabs)
    cmds.tabLayout(tabs, edit=True, tabLabel=[(curve_panel, u'沿曲线'), (surface_panel, u'表面散布')])
    cmds.showWindow(WINDOW)
    rebuild_menu()
    cmds.scriptJob(event=['Undo', lambda: (rebuild_menu(), refresh())], parent=WINDOW)
    cmds.scriptJob(event=['Redo', lambda: (rebuild_menu(), refresh())], parent=WINDOW)


if __name__ == '__main__':
    show()
