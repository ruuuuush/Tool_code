> 本变更为事后补档，以下任务在立项前均已完成并验证。

## 1. 编辑器样式

- [x] 1.1 `style.py` 新增 `QAbstractItemView QLineEdit/QComboBox/QSpinBox/QDoubleSpinBox` 规则，内边距设为 `0 4px`
- [x] 1.2 保留主色边框，让编辑态仍然醒目

## 2. 行距解耦

- [x] 2.1 `QTreeView::item, QTableView::item` 垂直内边距 5px → 2px
- [x] 2.2 `QTreeView::item` 补 `min-height: 24px`，恢复检查树行距
- [x] 2.3 片段表 `setDefaultSectionSize(28)` → `30`
- [x] 2.4 检查树 `setUniformRowHeights(True)`

## 3. 回归测试

- [x] 3.1 `tests/test_ui.py` 新增 `TestCellEditorFits`，setUp 中 `apply_theme` 后再断言
- [x] 3.2 断言改用「内边距开销 = sizeHint 高 − 字体高」，不受字体与 DPI 影响
- [x] 3.3 覆盖名称列与帧号列两种编辑器
- [x] 3.4 把内边距改回缺陷值，确认测试变红（18 > 10）
- [x] 3.5 装回修复，确认测试转绿

## 4. 验证

- [x] 4.1 离屏渲染编辑态，确认文字完整
- [x] 4.2 渲染检查树，确认行距未因内边距下调而变紧
- [x] 4.3 `mayapy` 跑全量测试，260 个全绿
