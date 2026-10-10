## ADDED Requirements

### Requirement: UE 发布前核验身份和冲突
UE SHALL 在正式发布前核验 ready、manifest/FBX 哈希、目标项目、既有 Skeleton 类型及所有片段目标冲突。正式发布 MUST 不删除或覆盖旧版本资产。

#### Scenario: 错项目或骨架
- **WHEN** 当前 UE 项目不匹配或指定资产不是 Skeleton
- **THEN** 不执行动画导入，回执指出失败原因

#### Scenario: 冲突
- **WHEN** 某目标资产已存在且没有匹配的成功发布记录
- **THEN** 整次正式导入在修改资产前阻断

### Requirement: 正式动画必须经过实际属性验收
每个正式片段 SHALL 验收类型、Skeleton、帧间隔、采样数量、采样率、时长、必要轨道和根运动。保存失败或必要 API 不可用 MUST 失败；回执 SHALL 携带预期、实际和错误。普通导入也 MUST NOT 仅凭目标存在判定本次成功。

#### Scenario: 验收失败
- **WHEN** 时长、骨架或轨道不符合契约
- **THEN** 发布结果失败，回执保留实际值

#### Scenario: API 不可用
- **WHEN** 宿主缺少必要验收 API
- **THEN** 发布不能被标记成功

### Requirement: 重复执行必须复验
已成功的同一发布 SHALL 在回执身份匹配且全部资产复验通过后返回成功，不重新导入。不得仅凭回执或路径存在复用成功。

#### Scenario: 已发布资产被修改
- **WHEN** 重复执行时资产关键属性发生改变
- **THEN** 复验失败，不覆盖已有资产
