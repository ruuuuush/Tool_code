## Why

导出与推送之间还断着一步。交付卡片摊开产物、给出推送按钮，然后停住等人点。但 99% 的情况下用户点导出的意图就是"把这段动画送进 UE"——多出来的那一次点击不表达任何决策，只是把已经确定的事再确认一遍。

## What Changes

- 导出设置中新增开关：**导出后自动推送到 UE**，默认开启，值写入配置文件，跨会话记住。
- 开关开启且本次交付齐全（FBX + manifest 都写出）时，导出流程完成后自动发起推送，无需点击。
- 自动推送复用现有推送通道与状态回显：交付卡片就地显示"正在推送 / 成功 / 失败"。
- 推送失败（UE 未开、未启用远程执行、编辑器报错）时安静降级：卡片显示原因，代码块、复制按钮、手动推送按钮全部保留，导出本身仍算成功。
- 交付不完整时不自动推送——UE 侧读不到 manifest，推过去只会拿一个更难懂的报错。
- 自动推送不弹额外对话框；结果只在交付卡片与状态栏呈现。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `export-ui`: 新增"导出完成后按用户设置自动推送"要求；推送入口从"仅手动触发"扩展为"自动触发 + 手动重试"。
- `ue-remote-push`: "失败必须安静降级"扩展到自动触发场景——自动推送失败 MUST NOT 使导出被判为失败，也 MUST NOT 打断用户。

## Impact

- `maya_to_ue/mtu_maya/core/config.py`：`PipelineSettings` 增加 `auto_push_after_export: bool = True`，`from_dict` 解析。
- `maya_to_ue/config/default_settings.json`：新增同名字段。
- `maya_to_ue/mtu_maya/ui/export_panel.py`（或导出设置所在模块）：新增勾选框与读取方法。
- `maya_to_ue/mtu_maya/ui/main_window.py`：`_on_export()` 成功分支触发 `_push_to_ue()`；`_apply_export_defaults()` 回填开关。
- `maya_to_ue/mtu_maya/ui/strings.py`：开关文案与自动推送状态文案。
- 测试：`tests/test_ui.py`、`tests/test_config.py`。
- 不改动 `bridge/`、`unreal/`、导出与 manifest 写入逻辑。
