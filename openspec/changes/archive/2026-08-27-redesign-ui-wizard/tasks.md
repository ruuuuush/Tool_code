## 1. 视觉底座

- [x] 1.1 `style.py` 调色板：`ACCENT` 改 `#4f8cff`，`ACCENT_TEXT` 改白，新增 `ACCENT_SOFT` / `ACCENT_HOVER` / `ACCENT_PRESSED`，原近白色保留为 `SURFACE_BRIGHT`
- [x] 1.2 重写 QSS 的按钮样式：主按钮用主色实底，次级按钮描边，flat 按钮无边框
- [x] 1.3 重写 QSS 的输入控件（QLineEdit / QComboBox / QSpinBox）：统一圆角、聚焦时主色描边
- [x] 1.4 重写 QSS 的树与表格：行高加大、选中行用 `ACCENT_SOFT`、表头去重色
- [x] 1.5 新增无标题卡片容器样式 `QFrame[panel="true"]`，替代带标题的 QGroupBox

## 2. 步骤条组件

- [x] 2.1 `style.py` 新增 `StepDot`：三态圆点（done 实心带勾 / current 主色描边 / todo 灰描边）
- [x] 2.2 `style.py` 新增 `StepBar`：圆点 + 标题 + 连接线横向排列，暴露 `step_clicked(int)` 信号与 `set_current(i)` / `set_step_state(i, state)`
- [x] 2.3 步骤条支持点击跳转，当前步高亮
- [x] 2.4 `tests/test_ui.py` 覆盖 `StepBar` 的状态设置与点击信号

## 3. 去重复标题与说明文字

- [x] 3.1 `CheckListPanel` 移除内部标题标签（`main_window.py:79`）
- [x] 3.2 `ClipTablePanel` 移除内部标题标签（`main_window.py:434`）
- [x] 3.3 `strings.py` 删除 `STEP1_HINT` / `STEP2_HINT` / `STEP3_HINT` / `APP_SUBTITLE`
- [x] 3.4 输入控件补齐 placeholder，确保删掉说明文字后仍知道该填什么
- [x] 3.5 `tests/test_ui.py` 断言三个面板不再渲染自带标题

## 4. 向导式主窗口

- [x] 4.1 `_build_ui()` 重构：顶部 `StepBar` + 中部 `QStackedWidget`（检查 / 片段 / 导出三页）+ 底部操作条
- [x] 4.2 三页内容用无标题卡片包裹，移除所有 `QGroupBox` 标题
- [x] 4.3 底部操作条：上一步 / 下一步 + 右侧主操作按钮，首尾步禁用对应方向
- [x] 4.4 移除外层 `QScrollArea` 与 `central.setMinimumHeight(1040)`，窗口最小尺寸调为 `860x600`
- [x] 4.5 场景信息条移到步骤条上方，作为常驻状态栏
- [x] 4.6 `tests/test_ui.py` 覆盖初始步、点击跳转、上一步/下一步、首尾按钮状态

## 5. 门禁

- [x] 5.1 新增 `MainWindow._update_gate()`：按 `_last_report` 统一更新导出按钮可用性、门禁提示文案、步骤条第一步状态
- [x] 5.2 跑完检查 / 修复完成 / 切换预设 / 切换步骤时都调用它
- [x] 5.3 `strings.py` 新增门禁文案（未检查 / 有 N 项阻断 / 可以导出）
- [x] 5.4 `tests/test_ui.py` 覆盖 spec 的四个门禁场景

## 6. 交付卡片重绘

- [x] 6.1 `DeliveryCard` 按新调色板调整（主色状态条、行样式），行为不变
- [x] 6.2 确认既有交付卡片测试全部仍通过

## 7. 目测与收尾

- [x] 7.1 离屏渲染三步各出一张图，逐版目测调整间距/字号/对齐
- [x] 7.2 渲染门禁态与交付完成态，确认状态色可读
- [x] 7.3 `mayapy` 跑全量测试，确认全绿
- [x] 7.4 README 的界面描述与特性表同步更新
