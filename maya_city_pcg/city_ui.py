# -*- coding: utf-8 -*-
import json
import maya.cmds as cmds
import maya.OpenMayaUI as omui
try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance


class CityWindow(QtWidgets.QDialog):
    def __init__(self, core, parent):
        super(CityWindow, self).__init__(parent)
        self.core = core
        self.result = None
        self.setObjectName('mayaCityPCGWindow')
        self.setWindowTitle('城市街区 · 0.2')
        self.resize(490, 480)
        self.setMinimumWidth(440)
        self.setStyleSheet('''
            QDialog { background:#25282d; }
            QLabel { color:#c1c8d1; }
            QTabWidget::pane { border:0; background:#2b2f35; }
            QTabBar::tab { color:#929eac; background:#25282d; padding:10px 26px; border-bottom:2px solid transparent; }
            QTabBar::tab:selected { color:#e0e6ed; border-bottom:2px solid #829eb5; }
            QPushButton { background:#383f49; color:#dce4ed; padding:7px 12px; border:1px solid #4e5968; border-radius:3px; }
            QPushButton:hover { background:#454f5c; }
            QPushButton:disabled { color:#74808e; }
            QPushButton#primary { background:#526c81; padding:10px; border-color:#728da3; }
            QSpinBox,QDoubleSpinBox { background:#20242a; color:#dce4ed; padding:6px; border:1px solid #46515f; border-radius:3px; }
        ''')
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)
        self.info = QtWidgets.QLabel()
        self.info.setStyleSheet('color:#a8b7c6; padding:7px 0;')
        self.info.setToolTip('尺寸采用当前场景单位：%s；示例按厘米设计，Y 向上。' % cmds.currentUnit(query=True,linear=True))
        layout.addWidget(self.info)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs, 1)
        self.fields = {}
        groups = [
            ('布局', [('nx','街区数 X',True),('nz','街区数 Z',True),('block_x','街区长度',False),('block_z','街区宽度',False),('road','道路宽度',False),('sidewalk','人行道宽度',False)]),
            ('建筑', [('lots_x','地块数 X',True),('lots_z','地块数 Z',True),('gap','建筑间距',False),('density','占用率',False),('height_min','楼高下限',False),('height_max','楼高上限',False),('seed','随机种子',True)])]
        for title, fields in groups:
            page = QtWidgets.QWidget()
            tabs.addTab(page, title)
            form = QtWidgets.QFormLayout(page)
            form.setContentsMargins(20, 18, 20, 18)
            form.setHorizontalSpacing(24)
            form.setVerticalSpacing(12)
            form.setLabelAlignment(QtCore.Qt.AlignRight)
            for key, label, integer in fields:
                field = QtWidgets.QSpinBox() if integer else QtWidgets.QDoubleSpinBox()
                field.setRange(0 if key in ('seed','sidewalk','gap','density') else 1, 2147483647 if key == 'seed' else 1000000)
                if key == 'density':
                    field.setRange(0,1)
                    field.setSingleStep(0.05)
                    field.setToolTip('建筑地块被占用的比例；0 留空，1 全部填充。')
                if key == 'seed':
                    field.setToolTip('相同参数和种子生成相同建筑布局。')
                if integer and key != 'seed':
                    field.setMaximum(30)
                field.setValue(core.DEFAULTS[key])
                field.setKeyboardTracking(False)
                field.valueChanged.connect(self.preview)
                self.fields[key] = field
                form.addRow(label,field)
        result_page = QtWidgets.QWidget()
        tabs.addTab(result_page, '结果')
        result_layout = QtWidgets.QVBoxLayout(result_page)
        result_layout.setContentsMargins(20, 18, 20, 18)
        result_layout.setSpacing(12)
        self.result_name = QtWidgets.QLabel('未指定城市')
        self.result_name.setWordWrap(True)
        result_layout.addWidget(self.result_name)
        actions = [
            ('读取选择', self.read, '选择城市组或城市内任意对象，恢复参数。'),
            ('重做选中街区', self.local, '选择街区或其中一栋建筑。仅改变该街区；布局参数改变时需整体更新。'),
            ('聚焦城市', self.focus, '在视口聚焦当前城市。'),
            ('复制独立模型', self.copy, '生成可手工编辑的副本，不受后续更新影响。')]
        for label, callback, tip in actions:
            button = QtWidgets.QPushButton(label)
            button.setToolTip(tip)
            button.clicked.connect(callback)
            result_layout.addWidget(button)
        result_layout.addStretch()
        row = QtWidgets.QHBoxLayout()
        self.primary = QtWidgets.QPushButton('生成城市')
        self.primary.setObjectName('primary')
        self.primary.setToolTip('生成或更新当前城市。整体更新会重置局部街区变化。')
        self.primary.clicked.connect(self.generate)
        row.addWidget(self.primary, 1)
        new_button = QtWidgets.QPushButton('新建')
        new_button.setToolTip('保留当前城市，下一次生成另一个城市。')
        new_button.clicked.connect(self.new)
        row.addWidget(new_button)
        layout.addLayout(row)
        self.status = QtWidgets.QLabel('就绪')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#8e9baa; font-size:11px;')
        layout.addWidget(self.status)
        self.preview()

    def config(self):
        return {key:field.value() for key,field in self.fields.items()}

    def preview(self,*unused):
        if not hasattr(self,'info'):
            return
        try:
            config = self.config()
            roads, extent = self.core.road_plan(config)
            count = sum(len(self.core.block_plan(config,x,z)) for x in range(config['nx']) for z in range(config['nz']))
            self.info.setText('%d 街区  /  %d 建筑  /  %.0f × %.0f' % (config['nx']*config['nz'],count,extent[0],extent[1]))
            self.primary.setEnabled(True)
        except Exception as error:
            self.info.setText('参数无效：'+str(error))
            self.primary.setEnabled(False)

    def generate(self):
        try:
            previous = self.result if self.result and cmds.objExists(self.result) else None
            self.result = self.core.build(self.config(),previous)
            self.primary.setText('更新当前城市')
            self.result_name.setText(self.result.rsplit('|',1)[-1])
            self.result_name.setToolTip(self.result)
            self.status.setText('城市已生成')
            self.focus()
        except Exception as error:
            self.status.setText('失败：'+str(error))
            cmds.warning(str(error))

    def read(self):
        try:
            nodes = cmds.ls(selection=True,long=True,objectsOnly=True) or []
            if len(nodes)!=1:
                raise ValueError('请选择一个城市组或其中一个对象。')
            self.result = self.core.find_city(nodes[0])
            config = json.loads(cmds.getAttr(self.result+'.cityConfig'))
            for key,field in self.fields.items():
                field.blockSignals(True)
                field.setValue(config[key])
                field.blockSignals(False)
            self.primary.setText('更新当前城市')
            self.preview()
            self.result_name.setText(self.result.rsplit('|',1)[-1])
            self.result_name.setToolTip(self.result)
            self.status.setText('已读取城市')
        except Exception as error:
            self.status.setText(str(error))

    def local(self):
        try:
            nodes = cmds.ls(selection=True,long=True,objectsOnly=True) or []
            if len(nodes)!=1:
                raise ValueError('请选择一个街区组或其中一栋建筑。')
            result = self.core.update_block(nodes[0],self.config())
            self.result = self.core.find_city(result)
            self.result_name.setText(self.result.rsplit('|',1)[-1])
            self.result_name.setToolTip(self.result)
            self.primary.setText('更新当前城市')
            self.status.setText('街区已更新：'+result.rsplit('|',1)[-1])
        except Exception as error:
            self.status.setText('局部更新失败：'+str(error))
            cmds.warning(str(error))

    def new(self):
        self.result=None
        self.primary.setText('生成城市')
        self.result_name.setText('未指定城市')
        self.result_name.setToolTip('')
        self.status.setText('就绪')

    def focus(self):
        if self.result and cmds.objExists(self.result):
            cmds.select(self.result)
            cmds.viewFit()

    def copy(self):
        if self.result and cmds.objExists(self.result):
            node=cmds.duplicate(self.result,renameChildren=True,name='City_editable#')[0]
            cmds.deleteAttr(node+'.cityConfig')
            cmds.select(node)
            self.status.setText('已复制：'+node.rsplit('|',1)[-1])


def show(core):
    parent=wrapInstance(int(omui.MQtUtil.mainWindow()),QtWidgets.QWidget)
    for child in parent.findChildren(QtWidgets.QDialog,'mayaCityPCGWindow'):
        child.close()
        child.deleteLater()
    window=CityWindow(core,parent)
    window.show()
    window.raise_()
    return window
