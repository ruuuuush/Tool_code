## Context

检查层：`run_all_checks(ctx, registry)` 遍历注册表全部 validator，逐个 `v.check(ctx)`，结果塞进 `RunReport.results`（`checks/registry.py:376`）。`RunReport.errors` 过滤 `level == "error" and not passed`，`can_export()` 就是 `not self.errors`。门禁、步骤条、导出弹窗全部读这一个属性。

界面层：`CheckListPanel` 是 `QTreeWidget`，两列（检查 / 状态），按 category 分组，`_items_by_id` 建 id → item 的索引（`ui/main_window.py:61`）。已有 `CenteredCheckDelegate`，说明这套树里加勾选框有先例可循。

交付层：`RunReport.to_summary()` 转成 `bridge.ValidationSummary` 写进 manifest；报告由 `manifest_writer` 渲染。UE 侧只读 manifest，不读 UI 状态。

跳过是给质量门禁开口子，因此设计的重心不在"怎么不跑"，而在"跳了必须让人看见"。

## Goals / Non-Goals

**Goals:**
- 用户能按项关掉检查，被关掉的检查**不执行**。
- 被跳过的 error 不再阻断导出。
- 跳过留痕：界面、manifest、导出报告三处都能看出跳了什么。
- 跳过是临时决定：仅本次会话有效。

**Non-Goals:**
- 不做"跳过原因"填写。留痕到 id + 级别即可，逼人写理由只会得到"aaa"。
- 不做预设方案（如"只交动画"一键跳一组）。等真出现重复操作再说。
- 不改 UE 侧导入逻辑：manifest 多一个字段，UE 侧不读也不会坏。
- 不写入配置文件，不跨会话记忆。

## Decisions

### 跳过集合由界面持有，检查层只接收参数

`run_all_checks(ctx, skipped=None)` 增加一个 `Set[str]` 入参，被跳过的 id 直接 `continue`，并追加一条 `passed=None` 的跳过态结果。检查层不知道"谁"决定跳过，也不持有状态——它只是执行。界面是唯一真值来源，会话结束即消失，天然满足"不跨会话"。

**备选**：validator 自带 `enabled` 标志 —— 否决。注册表是进程级单例（Maya 会话长驻），改它等于隐式跨会话记忆，还会污染另一个窗口。

### 跳过态是第三种结果，不是 `passed=True`

把跳过伪装成通过最省事，但那是**说谎**：manifest 会写着"全部通过"。`CheckResult` 增加 `skipped: bool`；`passed` 在跳过时保持 `False` 但不计入 `errors`：

- `RunReport.errors` → `level == "error" and not passed and not skipped`
- `warnings` / `infos` 同理
- `status` 因此不会因被跳过的项而变成 `failed`

**备选**：跳过的项干脆不进 `results` —— 否决，manifest 里就看不出它存在过，等于没留痕。

### `ValidationSummary` 增加 `skipped` 列表，旧 manifest 缺键即空

字段形如 `[{"check": "skeleton.naming", "level": "error"}]`。`from_dict` 用 `data.get("skipped", [])`，旧 manifest 照常读。UE 侧不读该字段，不受影响。

报告里单列一节「已跳过的检查」，把 error 级的排在最前——最该被看见的先看见。

### 导出前确认：只在有跳过项时弹，且点名 error 数量

已有的 warning 确认弹窗是"有 N 个警告，仍要导出吗"。跳过确认走同一位置但独立一条：**先**确认跳过（更重），再确认警告。文案必须写清"其中 N 项是会阻断导出的错误"，否则用户不会意识到自己拆的是哪道门。

**备选**：合并成一个弹窗 —— 否决，两件事性质不同，合起来会让人整体点"是"。

### 「一键修复所有警告」排除跳过项

修一个用户明确说"别管它"的检查，是越权。`fix_all_warnings(ctx, skipped=...)` 同样接收跳过集合。

### 勾选框放在树的第 0 列，父节点（分类）跟着联动

分类行的勾选框控制整组，三态显示（全勾/全不勾/部分）。这是用户真正想要的操作粒度——"骨架那一组我都不看"。

## Risks / Trade-offs

- **[跳过变成绕过：用户一路取消勾选直到能导出]** → 留痕是唯一的抑制手段：界面显示已跳过、导出前点名 error 数、manifest 与报告白纸黑字。工具不做家长，但也不做帮凶。
- **[被跳过的检查其实是别的检查的前提，跳了导致导出崩在半路]** → 导出本身有 try/except 与失败原因回显；跳过不改变这条兜底。
- **[勾选状态与检查结果分属两套状态，容易不同步]** → 勾选框状态由面板持有并在 `update_results()` 后重建 item 时回填；`skipped_ids()` 是唯一读取口。
- **[旧 manifest 没有 `skipped` 字段]** → `from_dict` 给默认空列表，读旧文件不报错。
