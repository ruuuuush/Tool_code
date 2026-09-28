## 1. 检查层

- [x] 1.1 `CheckResult` 增加 `skipped: bool = False`，`to_entry()` 带上该状态
- [x] 1.2 `run_all_checks(ctx, skipped=None)`：命中集合的 validator 不调用 `check()`，追加一条跳过态结果
- [x] 1.3 `RunReport.errors` / `warnings` / `infos` 排除跳过项；`skipped` 属性返回被跳过的结果
- [x] 1.4 `RunReport.status` 与 `can_export()` 不因跳过项而失败
- [x] 1.5 `fix_all_warnings(ctx, skipped=None)` 不修跳过项
- [x] 1.6 测试：跳过的 validator 的 `check()` 一次都没被调用（用计数桩）
- [x] 1.7 测试：跳过 error 级后 `can_export()` 为真；未跳过时照旧为假
- [x] 1.8 测试：跳过项既不计入 `passed_count` 也不计入 `errors`

## 2. 交付物记录

- [x] 2.1 `ValidationSummary` 增加 `skipped: List[SkippedCheck]`（check + level）
- [x] 2.2 `from_dict` 用 `data.get("skipped", [])`，旧 manifest 缺键即空
- [x] 2.3 `RunReport.to_summary()` 填充该字段
- [x] 2.4 导出报告新增「已跳过的检查」一节，error 级排最前；无跳过项时不出现该节
- [x] 2.5 测试：manifest 往返保留跳过记录；旧 manifest（无该键）解析不报错
- [x] 2.6 测试：报告在有/无跳过项两种情况下的差异

## 3. 检查列表界面

- [x] 3.1 `strings.py` 增加跳过相关文案（状态文本、统计、确认弹窗）
- [x] 3.2 树的第 0 列加勾选框，默认全勾
- [x] 3.3 分类行三态开关，联动组内各项
- [x] 3.4 `skipped_ids()` 作为唯一读取口
- [x] 3.5 `update_results()` 重建 item 后回填勾选状态，不被结果刷新覆盖
- [x] 3.6 跳过项渲染为「已跳过」，不显示通过图标；统计徽章点出跳过数量
- [x] 3.7 详情区对跳过项说明"因未勾选而未执行"
- [x] 3.8 测试：默认全勾、取消后重跑仍保持、分类联动、三态、跳过项不显示通过图标

## 4. 串起来

- [x] 4.1 `_on_run_checks()` 把 `skipped_ids()` 传给 `run_all_checks`
- [x] 4.2 一键修复所有警告同样传入跳过集合
- [x] 4.3 `_on_export()` 在存在跳过项时先弹跳过确认（早于警告确认），文案点名 error 数量
- [x] 4.4 确认选否即中止，不产生任何交付物
- [x] 4.5 无跳过项时不出现该确认
- [x] 4.6 测试：确认顺序、取消即中止、无跳过不打扰

## 5. 验证

- [x] 5.1 把「跳过项排除出 errors」改回原式，确认相关测试变红
- [x] 5.2 `D:\Maya2022\bin\mayapy.exe -m unittest discover -s tests` 全绿
- [x] 5.3 出图确认：勾选框列宽足够、三态可辨、「已跳过」文字不被裁、行距未变形
- [x] 5.4 Maya 内实测：跳过一个 error 级检查后能导出，manifest 里查得到该记录
- [x] 5.5 README 补一节说明跳过与其留痕
