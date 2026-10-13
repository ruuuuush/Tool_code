# -*- coding: utf-8 -*-
try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance
import maya.cmds as cmds
import maya.OpenMayaUI as omui


class PCGWindow(QtWidgets.QDialog):
    def __init__(self, curve, surface, parent):
        super(PCGWindow, self).__init__(parent)
        self.curve = curve
        self.surface = surface
        self.setObjectName('mayaPCGQtWindow')
        self.setWindowTitle('Maya PCG · 0.6.1')
        self.resize(580, 720)
        self.setMinimumWidth(520)
        self.setStyleSheet('''
            QDialog { background: #292c31; color: #d6d9de; }
            QLabel { color: #c5cbd3; }
            QTabWidget::pane { border: 1px solid #444951; border-radius: 4px; }
            QTabBar::tab { background: #30343a; color: #9fa8b4; padding: 10px 28px; }
            QTabBar::tab:selected { background: #414b57; color: #eef1f5; }
            QGroupBox { border: 1px solid #444951; border-radius: 4px; margin-top: 12px; padding: 12px; color: #afb9c6; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QPushButton { background: #3a3f47; color: #d6d9de; border: 1px solid #505761; border-radius: 3px; padding: 6px 12px; min-height: 20px; }
            QPushButton:hover { background: #48515d; }
            QPushButton:disabled { color: #737b86; border-color: #3d424a; }
            QPushButton#primary { background: #4b687f; border-color: #6b869b; font-weight: 600; min-height: 30px; }
            QListWidget, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #202328; color: #dce1e7; border: 1px solid #484e58; border-radius: 3px; padding: 5px; }
            QListWidget::item { padding: 5px; }
            QListWidget::item:selected { background: #42566a; }
            QCheckBox { color: #bec7d1; spacing: 7px; }
        ''')
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        self.pages = []
        for scatter, label in ((False, '沿曲线'), (True, '表面散布')):
            self.pages.append(self.build_page(scatter, label))
        self.status = QtWidgets.QLabel('添加模型，指定目标，然后生成。')
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(30)
        layout.addWidget(self.status)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.auto_update)
        self.busy = False
        self.jobs = []
        self.destroyed.connect(self.cleanup)
        for page in self.pages:
            self.reload_results(page)

    def button(self, text, callback, layout):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def number(self, value, minimum, maximum, integer=False):
        field = QtWidgets.QSpinBox() if integer else QtWidgets.QDoubleSpinBox()
        field.setRange(minimum, maximum)
        if not integer:
            field.setDecimals(2)
        field.setValue(value)
        field.setKeyboardTracking(False)
        return field

    def build_page(self, scatter, label):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        widget = QtWidgets.QWidget()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, label)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        page = {'scatter': scatter, 'result': None, 'target_path': '', 'widget': widget}
        assets = QtWidgets.QGroupBox('模型池')
        asset_layout = QtWidgets.QVBoxLayout(assets)
        page['models'] = QtWidgets.QListWidget()
        page['models'].setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        page['models'].setFixedHeight(94)
        asset_layout.addWidget(page['models'])
        row = QtWidgets.QHBoxLayout()
        self.button('添加选择', lambda: self.capture(page), row)
        self.button('移除', lambda: self.remove_models(page), row)
        presets = QtWidgets.QComboBox()
        presets.addItems(['创建示例…', '围栏', '路灯', '石块'])
        presets.currentIndexChanged.connect(lambda index: self.preset(page, presets, index))
        row.addWidget(presets)
        asset_layout.addLayout(row)
        layout.addWidget(assets)
        target_row = QtWidgets.QHBoxLayout()
        target_row.addWidget(QtWidgets.QLabel('地面' if scatter else '路线'))
        page['target'] = QtWidgets.QLineEdit()
        page['target'].setReadOnly(True)
        page['target'].setPlaceholderText('选择地面网格' if scatter else '选择曲线')
        target_row.addWidget(page['target'], 1)
        self.button('读取选择', lambda: self.read_target(page), target_row)
        if not scatter:
            self.button('绘制', lambda: self.draw(page), target_row)
        layout.addLayout(target_row)
        params = QtWidgets.QGroupBox('排列设置')
        form = QtWidgets.QFormLayout(params)
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        form.setHorizontalSpacing(16)
        page['amount'] = self.number(100 if scatter else 200, 1 if scatter else 0.01, 2000 if scatter else 1000000, scatter)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(page['amount'])
        if not scatter:
            self.button('按模型尺寸', lambda: self.auto_spacing(page), row)
        form.addRow('数量' if scatter else '间距', row)
        if scatter:
            page['slope'] = self.number(45, 0, 90)
            form.addRow('最大坡度 °', page['slope'])
        else:
            page['axis'] = QtWidgets.QComboBox()
            page['axis'].addItems(['X', 'Z'])
            form.addRow('前进轴', page['axis'])
        layout.addWidget(params)
        toggle = QtWidgets.QToolButton()
        toggle.setText('随机变化')
        toggle.setCheckable(True)
        toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        toggle.setArrowType(QtCore.Qt.RightArrow)
        layout.addWidget(toggle)
        random_widget = QtWidgets.QWidget()
        random_form = QtWidgets.QFormLayout(random_widget)
        random_form.setContentsMargins(12, 0, 12, 4)
        page['seed'] = self.number(1, 0, 2147483647, True)
        random_form.addRow('随机种子', page['seed'])
        page['min'] = self.number(0.8 if scatter else 1, 0.01, 100)
        page['max'] = self.number(1.2 if scatter else 1, 0.01, 100)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(page['min'])
        row.addWidget(QtWidgets.QLabel('至'))
        row.addWidget(page['max'])
        random_form.addRow('缩放范围', row)
        if not scatter:
            page['yaw'] = self.number(0, 0, 180)
            random_form.addRow('朝向偏移 ±°', page['yaw'])
        random_widget.setVisible(False)
        toggle.toggled.connect(random_widget.setVisible)
        toggle.toggled.connect(lambda checked: toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow))
        layout.addWidget(random_widget)
        page['info'] = QtWidgets.QLabel('未指定目标')
        layout.addWidget(page['info'])
        if not scatter:
            page['live'] = QtWidgets.QCheckBox('自动更新当前结果（最多 300 个实例）')
            page['live'].setChecked(True)
            layout.addWidget(page['live'])
        primary = self.button('生成', lambda: self.run(page), layout)
        primary.setObjectName('primary')
        page['primary'] = primary
        row = QtWidgets.QHBoxLayout()
        page['results'] = QtWidgets.QComboBox()
        row.addWidget(page['results'], 1)
        self.button('刷新列表', lambda: self.reload_results(page), row)
        self.button('新建', lambda: self.new_result(page), row)
        layout.addLayout(row)
        row = QtWidgets.QHBoxLayout()
        self.button('聚焦', lambda: self.focus(page), row)
        self.button('独立副本', lambda: self.copy(page), row)
        self.button('清除结果', lambda: self.clear(page), row)
        self.button('演示', lambda: self.demo(page), row)
        layout.addLayout(row)
        note = QtWidgets.QLabel('按面积散布，不避让，可能重叠。' if scatter else '刚性排列不弯曲模型，急弯可能留缝。')
        note.setStyleSheet('color: #8793a1; font-size: 11px;')
        layout.addWidget(note)
        layout.addStretch()
        for key in ('amount', 'seed', 'min', 'max', 'slope', 'yaw'):
            if key in page:
                page[key].valueChanged.connect(lambda value, p=page: self.changed(p))
        if not scatter:
            page['axis'].currentTextChanged.connect(lambda value: self.changed(page))
        page['results'].currentIndexChanged.connect(lambda index: self.load_result(page))
        return page

    def error(self, error):
        self.status.setText('操作失败：' + str(error))
        self.status.setStyleSheet('color: #e4a59c;')
        cmds.warning(str(error))

    def message(self, text):
        self.status.setStyleSheet('color: #aeb9c7;')
        self.status.setText(text)

    def models(self, page):
        return [page['models'].item(index).data(QtCore.Qt.UserRole) for index in range(page['models'].count())]

    def add_model(self, page, node):
        if node in self.models(page):
            return
        item = QtWidgets.QListWidgetItem(node.rsplit('|', 1)[-1])
        item.setData(QtCore.Qt.UserRole, node)
        item.setToolTip(node)
        page['models'].addItem(item)

    def selected(self):
        nodes = []
        for node in cmds.ls(selection=True, long=True, objectsOnly=True) or []:
            if cmds.nodeType(node) in ('mesh', 'nurbsCurve'):
                node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
            if node not in nodes:
                nodes.append(node)
        return nodes

    def capture(self, page):
        try:
            for node in self.selected():
                if not page['scatter'] and cmds.listRelatives(node, shapes=True, type='nurbsCurve'):
                    self.set_target(page, node)
                elif cmds.listRelatives(node, allDescendents=True, type='mesh'):
                    self.add_model(page, node)
            self.changed(page)
        except Exception as error:
            self.error(error)

    def remove_models(self, page):
        for item in page['models'].selectedItems():
            page['models'].takeItem(page['models'].row(item))
        self.changed(page)

    def set_target(self, page, node):
        page['target_path'] = node
        page['target'].setText(node.rsplit('|', 1)[-1])
        page['target'].setToolTip(node)
        self.watch()

    def read_target(self, page):
        try:
            nodes = self.selected()
            kind = 'mesh' if page['scatter'] else 'nurbsCurve'
            if len(nodes) != 1 or not cmds.listRelatives(nodes[0], shapes=True, noIntermediate=True, type=kind):
                raise ValueError('请选择一个地面网格。' if page['scatter'] else '请选择一条曲线。')
            self.set_target(page, nodes[0])
            self.changed(page)
        except Exception as error:
            self.error(error)

    def draw(self, page):
        context = 'PCG_drawCurveContext'
        if not cmds.contextInfo(context, exists=True):
            cmds.curveEPCtx(context)
        cmds.setToolTo(context)
        self.message('点击绘制路线，回车完成，再点读取选择。')

    def preset(self, page, combo, index):
        if index == 0:
            return
        try:
            node = self.curve.create_example(('fence', 'lamp', 'rock')[index - 1])
            self.add_model(page, node)
            combo.setCurrentIndex(0)
            self.changed(page)
        except Exception as error:
            self.error(error)

    def auto_spacing(self, page):
        try:
            nodes = self.models(page)
            if not nodes:
                raise ValueError('请先添加模型。')
            index = 0 if page['axis'].currentText() == 'X' else 2
            bounds = cmds.xform(nodes[0], query=True, objectSpace=True, boundingBox=True)
            value = (bounds[index + 3] - bounds[index]) * abs(cmds.getAttr(nodes[0] + '.scale')[0][index])
            if value <= 0:
                raise ValueError('模型在前进轴上的尺寸为 0。')
            page['amount'].setValue(value)
        except Exception as error:
            self.error(error)

    def changed(self, page):
        if self.busy:
            return
        try:
            if page['scatter']:
                page['info'].setText('预计 %d 个实例 · 固定种子 %d' % (page['amount'].value(), page['seed'].value()))
            elif page['target_path'] and cmds.objExists(page['target_path']):
                length, closed = self.curve.curve_metrics(page['target_path'])
                count = len(self.curve.sample_distances(length, page['amount'].value(), closed))
                page['info'].setText('长度 %.2f · 预计 %d 个实例' % (length, count))
            else:
                page['info'].setText('未指定路线')
            if not page['scatter'] and page['result'] and page['live'].isChecked():
                self.timer.start()
        except Exception as error:
            page['info'].setText(str(error))

    def auto_update(self):
        page = self.pages[0]
        if not page['live'].isChecked() or not page['result'] or not cmds.objExists(page['result']):
            return
        try:
            length, closed = self.curve.curve_metrics(page['target_path'])
            if len(self.curve.sample_distances(length, page['amount'].value(), closed)) > 300:
                self.message('超过 300 个实例，请手动点击更新。')
                return
            selected = cmds.ls(selection=True, long=True) or []
            self.run(page)
            remaining = [node for node in selected if cmds.objExists(node)]
            if remaining:
                cmds.select(remaining, replace=True)
        except Exception as error:
            self.error(error)

    def run(self, page):
        if self.busy:
            return
        self.timer.stop()
        self.busy = True
        try:
            previous = page['result'] if page['result'] and cmds.objExists(page['result']) else None
            args = (self.models(page), page['target_path'])
            if page['scatter']:
                group = self.surface.scatter(*args, count=page['amount'].value(), seed=page['seed'].value(), scale_min=page['min'].value(), scale_max=page['max'].value(), slope=page['slope'].value(), previous=previous)
                count = page['amount'].value()
            else:
                group, count = self.curve.generate(*args, spacing=page['amount'].value(), axis=page['axis'].currentText(), previous=previous, seed=page['seed'].value(), scale_min=page['min'].value(), scale_max=page['max'].value(), yaw=page['yaw'].value())
            page['result'] = group
            self.reload_results(page)
            self.message('完成：%d 个实例。源模型和目标保留。' % count)
        except Exception as error:
            self.error(error)
        finally:
            self.busy = False

    def reload_results(self, page):
        combo = page['results']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem('新排列', None)
        attr = 'pcgScatter' if page['scatter'] else 'pcgResult'
        for node in cmds.ls('*.' + attr, objectsOnly=True, long=True) or []:
            if cmds.getAttr(node + '.' + attr):
                combo.addItem(node.rsplit('|', 1)[-1], node)
        index = combo.findData(page['result'])
        combo.setCurrentIndex(max(index, 0))
        combo.blockSignals(False)
        if index < 0:
            page['result'] = None
        page['primary'].setText('更新当前结果' if page['result'] else '生成')

    def load_result(self, page):
        group = page['results'].currentData()
        page['result'] = group
        page['primary'].setText('更新当前结果' if group else '生成')
        if not group or not cmds.objExists(group):
            return
        self.timer.stop()
        self.busy = True
        try:
            page['models'].clear()
            attr = 'pcgSources' if cmds.attributeQuery('pcgSources', node=group, exists=True) else 'pcgSource'
            nodes = cmds.listConnections(group + '.' + attr, source=True, destination=False) or []
            for node in cmds.ls(nodes, long=True) if nodes else []:
                self.add_model(page, node)
            target_attr = 'pcgSurface' if page['scatter'] else 'pcgCurve'
            targets = cmds.listConnections(group + '.' + target_attr, source=True, destination=False) or []
            self.set_target(page, cmds.ls(targets[0], long=True)[0] if targets else '')
            mapping = [('amount', 'pcgCount' if page['scatter'] else 'pcgSpacing'), ('seed', 'pcgSeed'), ('min', 'pcgScaleMin'), ('max', 'pcgScaleMax'), ('slope' if page['scatter'] else 'yaw', 'pcgSlope' if page['scatter'] else 'pcgYaw')]
            for key, attr in mapping:
                if cmds.attributeQuery(attr, node=group, exists=True):
                    value = cmds.getAttr(group + '.' + attr)
                    page[key].setValue(int(value) if key == 'seed' or (key == 'amount' and page['scatter']) else value)
            if not page['scatter']:
                page['axis'].setCurrentText(cmds.getAttr(group + '.pcgAxis'))
        except Exception as error:
            self.error(error)
        finally:
            self.busy = False
        self.changed(page)
        self.timer.stop()

    def new_result(self, page):
        self.timer.stop()
        page['results'].setCurrentIndex(0)
        page['result'] = None
        page['primary'].setText('生成')

    def focus(self, page):
        if page['result'] and cmds.objExists(page['result']):
            cmds.select(page['result'])
            cmds.viewFit()

    def copy(self, page):
        try:
            if not page['result'] or not cmds.objExists(page['result']):
                raise ValueError('请先生成或选择结果。')
            node = self.curve.independent_result(page['result'])
            self.message('已创建独立副本：' + node)
        except Exception as error:
            self.error(error)

    def clear(self, page):
        group = page['result']
        if not group or not cmds.objExists(group):
            return
        answer = QtWidgets.QMessageBox.question(self, '清除结果', '仅删除当前结果组及其中实例。\n源模型、目标和独立副本保留。\n\n' + group, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if answer == QtWidgets.QMessageBox.Yes:
            self.timer.stop()
            cmds.delete(group)
            page['result'] = None
            self.reload_results(page)
            self.message('已清除当前结果。')

    def demo(self, page):
        try:
            self.new_result(page)
            page['models'].clear()
            node = self.curve.create_example('rock' if page['scatter'] else 'fence')
            self.add_model(page, node)
            if page['scatter']:
                target = cmds.polyPlane(name='PCG_demo_ground#', width=1600, height=1200, subdivisionsX=12, subdivisionsY=12, constructionHistory=False)[0]
            else:
                target = self.curve.create_demo_curve()
                page['amount'].setValue(200)
            self.set_target(page, cmds.ls(target, long=True)[0])
            self.run(page)
            self.focus(page)
        except Exception as error:
            self.error(error)

    def watch(self):
        self.cleanup()
        page = self.pages[0] if self.pages else None
        if not page or not page['target_path'] or not cmds.objExists(page['target_path']):
            return
        shapes = cmds.listRelatives(page['target_path'], shapes=True, noIntermediate=True, fullPath=True, type='nurbsCurve') or []
        if shapes:
            self.jobs.append(cmds.scriptJob(attributeChange=[shapes[0] + '.worldSpace[0]', lambda: self.changed(page)]))

    def cleanup(self, *unused):
        for job in self.jobs:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job)
        self.jobs = []

    def closeEvent(self, event):
        self.timer.stop()
        self.cleanup()
        super(PCGWindow, self).closeEvent(event)


def show(curve, surface):
    parent = wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    for child in parent.findChildren(QtWidgets.QDialog, 'mayaPCGQtWindow'):
        child.close()
        child.deleteLater()
    window = PCGWindow(curve, surface, parent)
    window.show()
    window.raise_()
    return window
