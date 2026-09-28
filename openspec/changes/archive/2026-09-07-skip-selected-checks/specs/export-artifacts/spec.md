## ADDED Requirements

### Requirement: 交付物记录被跳过的检查

manifest 与导出报告 MUST 让下游看出哪些检查没有执行。验证摘要 SHALL 携带被跳过检查的标识与级别；导出报告 SHALL 单列一节列出它们，错误级的排在最前。读取不含该记录的旧 manifest MUST NOT 报错。

#### Scenario: manifest 携带跳过记录

- **WHEN** 一次导出中跳过了若干检查
- **THEN** manifest 的验证摘要中可读出这些检查的标识与级别

#### Scenario: 报告单列跳过一节

- **WHEN** 导出报告被写出且本次存在跳过项
- **THEN** 报告中有一节列出被跳过的检查，错误级的排在最前

#### Scenario: 无跳过时报告不出现该节

- **WHEN** 本次导出没有跳过任何检查
- **THEN** 报告中不出现被跳过检查的小节

#### Scenario: 旧 manifest 仍可读取

- **WHEN** 读取一个不含跳过记录字段的既有 manifest
- **THEN** 解析成功，跳过记录视为空
