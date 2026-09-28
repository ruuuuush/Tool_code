## 1. 步骤索引常量化

- [x] 1.1 `main_window.py` 定义 `STEP_CLIPS = 0` / `STEP_EXPORT = 1` / `STEP_CHECK = 2`
- [x] 1.2 把 `_go_to_step()` / `_update_gate()` 里所有硬编码索引与 `count() - 1` 换成常量

## 2. 调整顺序

- [x] 2.1 `strings.py` 的 `STEP_TITLES` 改为 `("动画片段", "导出设置", "检查")`
- [x] 2.2 `_build_ui()` 中三页装配顺序改为 片段 → 导出 → 检查
- [x] 2.3 确认 `_connect_signals()` 与面板构造顺序不受影响
- [x] 2.4 `tests/test_ui.py` 的导航测试改用常量并断言初始停在片段步

## 3. 检查步的导出入口

- [x] 3.1 底部导航条在检查步显示主操作按钮，转发 `run_export_requested`
- [x] 3.2 该按钮与导出面板内按钮共用门禁状态（`set_export_enabled` 同步两处）
- [x] 3.3 非检查步时隐藏该按钮
- [x] 3.4 `tests/test_ui.py` 覆盖：检查步可见、其他步隐藏、门禁联动

## 4. 门禁与步骤完成度

- [x] 4.1 `_update_gate()` 的显示条件改为 `currentIndex() == STEP_CHECK`
- [x] 4.2 门禁文案改为「先运行检查」措辞（`strings.py`）
- [x] 4.3 新增 `_update_step_progress()`：片段非空标记第①步完成，三个必填路径齐备标记第②步完成
- [x] 4.4 片段表变动与导出表单编辑时触发 `_update_step_progress()`
- [x] 4.5 `tests/test_ui.py` 覆盖 spec 的三个完成度场景与「前两步不显示门禁理由」

## 5. 场景信息实时刷新

- [x] 5.1 `MainWindow` 新增 `QTimer`（1000ms，parent 为窗口），触发 `_refresh_scene_info_safe()`
- [x] 5.2 `_refresh_scene_info_safe()` 缓存上次文本，值未变时不调用 `setText`
- [x] 5.3 `closeEvent()` 中停止定时器
- [x] 5.4 `tests/test_ui.py` 覆盖：手动触发刷新不抛异常、值未变不重绘、关闭后定时器停止

## 6. 目测与收尾

- [x] 6.1 离屏渲染三步，确认顺序与步骤条完成态正确
- [x] 6.2 渲染检查步的门禁态与导出按钮
- [x] 6.3 `mayapy` 跑全量测试，确认全绿
- [x] 6.4 README 操作流程按新顺序改写
