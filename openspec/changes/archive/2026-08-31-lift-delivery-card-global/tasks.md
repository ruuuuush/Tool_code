## 1. 搬迁卡片

- [x] 1.1 `ExportPanel` 移除 `DeliveryCard` 的创建、信号接线与 `_delivery` 引用
- [x] 1.2 `MainWindow._build_ui()` 创建卡片，插在 `QStackedWidget` 与导航条之间
- [x] 1.3 卡片默认隐藏，未导出时不占位

## 2. 方法上移

- [x] 2.1 `show_delivery()` 从 `ExportPanel` 移到 `MainWindow`
- [x] 2.2 `_copy_to_clipboard()` / `_reveal_path()` 随之上移
- [x] 2.3 `_push_to_ue()` / `_on_push_finished()` / `stop_push()` 上移，`closeEvent` 直接调用自身的 `stop_push()`
- [x] 2.4 推送与复制的状态文本经新增的 `ExportPanel.set_status()` 写回原有反馈位置

## 3. 清理

- [x] 3.1 删除 `_export_scroll.ensureWidgetVisible(...)` 那行跨页滚动
- [x] 3.2 `_export_scroll` 已无其他用途，一并移除
- [x] 3.3 `set_busy()` / `reset_progress()` 不再触碰卡片；清空改由 `_on_export()` 在开始导出时调用

## 4. 测试

- [x] 4.1 `TestDeliveryCard` 改为经主窗口取卡片
- [x] 4.2 `TestUEHandoff` 同上，并保留 `stop_push` 清理
- [x] 4.3 新增 `TestDeliveryCardIsGlobal`：在检查步导出后卡片可见
- [x] 4.4 新增：切换步骤后卡片保持可见
- [x] 4.5 新增：卡片不在任何步骤页的子树内；`ExportPanel` 不再持有卡片

## 5. 验证与收尾

- [x] 5.1 离屏渲染：停在检查步时导出按钮、交付清单、推送入口同屏可见
- [x] 5.2 `mayapy` 跑全量测试，299 个全绿
- [x] 5.3 README 更新交付清单的位置描述
