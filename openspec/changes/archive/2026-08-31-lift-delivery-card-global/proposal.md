## Why

导出的**动作**和导出的**结果**被拆到了两个页面上。

`DeliveryCard` 是 `ExportPanel` 的一部分，随它落在第②步「导出设置」。而导出按钮在第③步「检查」的导航条上——检查通过才允许导出，按钮自然放在那里。于是用户在第③步点导出，人留在第③步，交付清单和【推送到 UE】却在第②步渲染出来，看不见。

`main_window.py:1541` 更是明证：那行 `ensureWidgetVisible` 写于调整步骤顺序之前，当时动作和结果同页，滚一下就到眼前；现在它在用户看不见的另一页上默默滚动。导出完成后界面等于毫无反馈，得自己切回上一步才发现产物在那儿。

根因是归属判断过时了：把交付卡片做成导出表单的一部分，在"设置和动作同页"时说得通，页面一拆就散架。**交付结果不属于任何一步，它是这次会话的产出。**

## What Changes

- **交付卡片提升为全局区域**：从 `ExportPanel` 中拆出，固定在内容区下方、底部导航条上方，任何步骤都可见。
- **导出后就地看到结果**：不论用户当时停在哪一步，交付清单与推送入口都在同一屏出现。
- **删除那行跨页滚动**：卡片不再藏在滚动区里，`ensureWidgetVisible` 失去意义。
- **推送线程的宿主随之上移**：`stop_push()` 与在途推送的回收改由主窗口负责。
- 卡片自身的行为不变——三行产物、交接区、推送与降级逻辑原样保留。

## Capabilities

### Modified Capabilities
- `export-ui`: 交付结果的呈现位置从"导出设置步骤内"改为"跨步骤常驻区域"。

## Impact

- `mtu_maya/ui/main_window.py`：`DeliveryCard` 的创建与信号接线从 `ExportPanel` 移到 `MainWindow`；`show_delivery` / `_copy_to_clipboard` / `_push_to_ue` / `stop_push` 随之上移；删除 `_export_scroll.ensureWidgetVisible`
- `tests/test_ui.py`：`TestDeliveryCard` / `TestUEHandoff` 改为面向主窗口取卡片
- 导出器、检查项、`ue_remote`、`DeliveryCard` 自身均不改动
