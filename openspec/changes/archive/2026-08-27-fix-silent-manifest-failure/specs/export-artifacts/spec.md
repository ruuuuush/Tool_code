## ADDED Requirements

### Requirement: 交付产物写入结果必须可见

一次导出产出 FBX、manifest、Markdown 报告与日志。任一产物写入失败 MUST 出现在导出结果中，MUST NOT 被静默吞掉只留日志。

#### Scenario: manifest 写入失败
- **WHEN** `write_all_artifacts()` 写 manifest 时抛异常
- **THEN** 返回结果中 manifest 路径为空且携带失败原因
- **AND** 该原因追加进 `ExportResult.errors`

#### Scenario: 报告写入失败不影响 manifest
- **WHEN** manifest 写入成功但 Markdown 报告写入失败
- **THEN** 返回结果中 manifest 路径有效、报告路径为空并带失败原因

#### Scenario: 全部写入成功
- **WHEN** 三个产物都写入成功
- **THEN** 返回结果中各路径均有效、无失败原因、`ExportResult.errors` 不新增内容

### Requirement: 导出成功的判定包含 manifest

UI SHALL 只在 FBX 与 manifest 都写入成功时报告「导出完成」。FBX 写成但 manifest 未写成 MUST 按未完成处理并列出具体原因。

#### Scenario: FBX 成功但 manifest 失败
- **WHEN** 导出后 `fbx_written` 为真但 manifest 写入失败
- **THEN** UI 显示未完成，并在导出面板与弹窗中列出 manifest 的失败原因

#### Scenario: 两者都成功
- **WHEN** FBX 与 manifest 都写入成功
- **THEN** UI 显示导出完成，摘要中包含 manifest 路径

### Requirement: 默认值不得产出自身校验不通过的对象

数据类的默认构造结果 MUST 能通过自身的校验逻辑；缺省即非法的字段 MUST 给出合法默认值或改由构造方显式提供。

#### Scenario: 默认 Convention 通过 Manifest 校验
- **WHEN** 用 `Convention()` 默认值组装一份其余字段合法的 `Manifest` 并调用 `validate()`
- **THEN** 校验通过

#### Scenario: SkeletonPreset 只给必填标识即可构造
- **WHEN** 以 `SkeletonPreset(id=..., display_name=..., skeleton_type=...)` 构造预设
- **THEN** 构造成功，`root_bone` 取空字符串默认值
