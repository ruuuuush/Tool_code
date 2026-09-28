## Why

有些检查在特定场景下就是不适用：只交动画不带模型时「骨架实际尺寸」没意义，用别人的 rig 时「骨骼命名」永远红。现在唯一的出路是硬着头皮看红叉，或者被 error 挡在导出之外——工具变成了障碍而不是助手。

同时这是给质量门禁开口子。口子必须留痕：跳过了什么，交付物里得看得见，否则下游拿到一个"通过"的 manifest，却不知道有三项压根没跑。

## What Changes

- 检查列表每一行前加勾选框，默认全勾。取消勾选即**不执行**该检查。
- 跳过对所有级别开放，包括 error 级——但被跳过的 error 项不再阻断导出。
- 被跳过的项在列表中显示为「已跳过」状态，与"通过""失败"视觉可辨。
- manifest 的验证摘要记录被跳过的检查 id 与其声明级别；导出报告单列一节列出它们。
- 存在被跳过项时，导出前弹一次确认，说明跳过了几项、其中几项是 error 级。
- 跳过选择**仅本次会话有效**，重开工具恢复全勾，不写入配置。
- 「一键修复所有警告」只作用于未被跳过的项。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `export-validation`: 新增"检查项可按需跳过"与"跳过必须留痕"两条要求；导出门禁的判定改为只看未跳过的 error。
- `export-artifacts`: manifest 与导出报告必须记录被跳过的检查。
- `export-ui`: 检查列表新增勾选框与「已跳过」状态；存在跳过项时导出前确认。

## Impact

- `maya_to_ue/mtu_maya/checks/registry.py`：`run_all_checks` 增加 `skipped: Set[str]` 入参；`CheckResult` / `RunReport` 表达跳过态；`errors` 与 `can_export()` 不计跳过项；`fix_all_warnings` 排除跳过项。
- `maya_to_ue/bridge/schema.py`：`ValidationSummary` 增加 `skipped` 字段（检查 id + 级别），`from_dict` 兼容旧 manifest 缺该键。
- `maya_to_ue/mtu_maya/export/manifest_writer.py`：报告中增加"已跳过的检查"一节。
- `maya_to_ue/mtu_maya/ui/main_window.py`：`CheckListPanel` 每行勾选框、跳过态渲染、`skipped_ids()`；`_on_run_checks` / `_on_export` 传入跳过集合；导出前确认。
- `maya_to_ue/mtu_maya/ui/strings.py`：跳过相关文案。
- 测试：`tests/test_checks.py`、`tests/test_schema.py`、`tests/test_export.py`、`tests/test_ui.py`。
- 不改动 UE 侧导入逻辑与远程推送。
