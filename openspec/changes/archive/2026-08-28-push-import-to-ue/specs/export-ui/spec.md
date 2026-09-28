## ADDED Requirements

### Requirement: 交接区提供直推 UE 的入口

交付完整时，交接区 SHALL 在复制代码之外提供一个直接推送到运行中 UE 编辑器的按钮，并 MUST 就地回显推送结果。

#### Scenario: 交付完整时可推送
- **WHEN** FBX 与 manifest 都写入成功
- **THEN** 交接区显示推送按钮，可点击

#### Scenario: 推送成功回显结果
- **WHEN** 推送成功完成
- **THEN** 交接区显示成功状态与编辑器返回的关键输出

#### Scenario: 推送失败保留手动路径
- **WHEN** 推送失败
- **THEN** 交接区显示失败原因，代码块与复制按钮保持可用

#### Scenario: 交付不完整时无推送入口
- **WHEN** manifest 未写出
- **THEN** 交接区整体不显示，推送入口也不存在
