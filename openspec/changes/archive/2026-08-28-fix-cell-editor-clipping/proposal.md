> **事后补档**：代码与测试在本变更立项前已完成并验证（260 测试全绿）。
> 建档目的是把约束写进 spec、把排查过程中的教训留下，而不是驱动实现。

## Why

双击片段名进入编辑时，文字被拦腰切掉，只露出上半截。

根因是样式泄漏：全局 `QLineEdit` 规则带着表单输入框的内边距（上下各 6px），而表格内嵌的编辑器同样是 `QLineEdit`，于是原样继承。编辑器因此索要 34px 高度，表格行只有 28px，Qt 硬压进去，18px 的字只剩几个像素可见。`QTableView::item` 的 `padding: 5px 4px` 又从编辑器可用矩形里再削 10px。

这不是孤立疏忽，而是一个**会复发的类别**。片段表将来若增加下拉列（根运动改三态、加循环枚举等），`QComboBox` 会原样再踩一遍。缺少约束的话，下次调配色或清理样式时，那条给 item view 编辑器写的规则很容易被当成冗余删掉。

## What Changes

- **单元格编辑器不再继承表单内边距**：为 `QAbstractItemView` 下的 `QLineEdit` / `QComboBox` / `QSpinBox` / `QDoubleSpinBox` 单独设定紧凑度量，一次覆盖当前和将来可能出现的编辑器类型。
- **行距改由行高承担**：`QTreeView::item` / `QTableView::item` 的垂直内边距从 5px 降到 2px——内边距会缩小编辑器拿到的矩形，正是它把编辑框压扁的。
- **片段表行高 28 → 30**，给编辑器留出余量。
- **检查树补 `min-height`**：树是只读的，用 min-height 恢复被降低的行距，不走内边距。
- **新增回归测试**：断言编辑器的内边距开销不超过阈值。

## Capabilities

### New Capabilities
<!-- 无新增能力，属于既有 export-ui 的视觉契约补充 -->

### Modified Capabilities
- `export-ui`: 新增可编辑单元格的显示约束。

## Impact

- `mtu_maya/ui/style.py`：新增 item view 编辑器样式规则；调整 item 内边距；检查树 min-height
- `mtu_maya/ui/main_window.py`：片段表行高、检查树 `setUniformRowHeights`
- `tests/test_ui.py`：新增 `TestCellEditorFits`（5 个用例）
- 检查项、导出器、manifest 与任何数据逻辑均未触及
