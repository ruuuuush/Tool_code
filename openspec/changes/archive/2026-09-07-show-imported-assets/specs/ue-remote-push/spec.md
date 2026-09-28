# ue-remote-push · delta（show-imported-assets）

## ADDED Requirements

### Requirement: 推送成功后呈现导入结果

推送成功后，系统 SHALL 回读本次 manifest 的 `result` 字段，并以其为准在交付卡片呈现导入结果，而不仅是编辑器回显的一句话。回读失败或结果不可用时 MUST 降级为原有「推送成功」文案，MUST NOT 推翻推送成功的事实。

#### Scenario: 导入全部成功
- **WHEN** 推送成功且 `manifest.result.status` 为 `success`
- **THEN** 交付卡片显示导入完成，并逐条列出 `imported_clips` 中的 AnimSequence
- **AND** 若 `skeleton_path` 非空，列出生成的 Skeleton / SkeletalMesh

#### Scenario: 部分成功
- **WHEN** 推送成功且 `manifest.result.status` 为 `partial`
- **THEN** 交付卡片分别列出已导入与按策略跳过的片段

#### Scenario: 推送成功但导入失败
- **WHEN** 推送成功但 `manifest.result.status` 为 `failed`
- **THEN** 交付卡片按失败呈现，列出 `result.errors`
- **AND** 卡片保持摊开，手动路径（代码与复制按钮）保持可用

#### Scenario: 结果不可用
- **WHEN** 推送成功但 manifest 读取失败、损坏，或 `result.status` 仍为 `pending`
- **THEN** 交付卡片显示原有「已在 UE 中导入完成（编辑器名）」文案

### Requirement: 推送成功后手动指引退休

推送成功后，系统 SHALL 隐藏交付卡片中的手动导入指引（交接区代码块），因为系统已经代劳。推送失败或新一轮导出 MUST 让手动路径重新可用。

#### Scenario: 成功后交接区隐藏
- **WHEN** 推送成功
- **THEN** 交接区（代码块与复制/推送按钮）隐藏，即使用户展开卡片详情也不出现

#### Scenario: 失败后手动路径回来
- **WHEN** 推送曾成功而之后某次推送失败
- **THEN** 交接区重新可见，复制与推送按钮可用

#### Scenario: 新一轮导出重置
- **WHEN** 推送成功后用户再次导出
- **THEN** 新交付的交接区照常显示，推送成功前不隐藏

### Requirement: 导入完成后在 Content Browser 中定位资产

导入流程的人读收尾（`report()`）SHALL 让 UE Content Browser 定位并选中本次生成的资产。该行为 MUST NOT 影响导入结果：定位失败或不支持时静默跳过。

#### Scenario: 有生成的资产
- **WHEN** 导入产生了 AnimSequence / Skeleton / SkeletalMesh
- **THEN** Content Browser 定位并选中这些资产

#### Scenario: 定位能力不可用
- **WHEN** 当前引擎版本无对应 API，或处于无界面环境
- **THEN** 跳过定位，导入报告照常输出，不抛出异常

#### Scenario: 推送与手动一致
- **WHEN** 通过推送或手动粘贴执行同一段导入代码
- **THEN** 两种路径都触发定位，因为定位内置于 `report()`
