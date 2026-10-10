## ADDED Requirements

### Requirement: 正式发布严格且不可覆盖
系统 SHALL 在正式发布时要求项目、资产和正整数版本，MUST 拒绝跳过检查、首次骨架创建和无有效时长的片段。发布版本目录 MUST 独占创建，存在时不得覆盖。

#### Scenario: 旧版本保护
- **WHEN** 用户发布已存在的版本
- **THEN** 导出在修改文件前失败，旧版本不变

#### Scenario: 硬门禁
- **WHEN** 正式发布请求包含跳过项或未通过实时检查
- **THEN** 不生成就绪发布包

### Requirement: 发布文件身份和就绪可验证
发布 manifest SHALL 记录发布身份、规则和参数指纹、FBX SHA-256 和大小。所有必要文件成功写入后才 SHALL 生成 ready 标识绑定 manifest 哈希；JSON 写入 MUST 避免截断原文件。

#### Scenario: 文件替换
- **WHEN** FBX 或 manifest 在发布后改变
- **THEN** 消费者在修改 UE 资产前拒绝

#### Scenario: 写入中断
- **WHEN** 写入清单或报告失败
- **THEN** 不生成 ready，旧 JSON 保留且错误可见

### Requirement: 正式发布结果独立可追踪
正式导入 MUST 不修改原 manifest，SHALL 生成绑定发布 ID、执行 ID、manifest 哈希及实际引擎项目的独立回执。写入回执失败 MUST 上浮，不得显示完整成功。

#### Scenario: 回执失败
- **WHEN** 资产已导入但回执写入失败
- **THEN** 执行结果包含记录失败原因，manifest 字节不变
