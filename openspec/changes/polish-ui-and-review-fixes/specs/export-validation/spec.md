## ADDED Requirements

### Requirement: 导出重检沿用会话内跳过选择

UI 发起导出时 SHALL 把本次会话的跳过检查 ID 集合传入 ExportRequest。导出器 MUST 重新读取实时场景并执行未跳过的检查，MUST NOT 复用过期检查结果。被跳过项 SHALL 出现在导出验证摘要和交付报告中。不提供跳过集合的调用 SHALL 运行全部检查。

#### Scenario: UI 选择传到导出器
- **WHEN** 用户取消勾选某项、运行检查并确认继续导出
- **THEN** 实际导出重检仍不执行该项
- **AND** manifest 的 validation 记录该项 ID 和严重级别

#### Scenario: 未跳过的错误阻断
- **WHEN** 导出重检发现未跳过的错误级检查失败
- **THEN** 不写入 FBX，与既有门禁规则一致

#### Scenario: 默认全量检查
- **WHEN** 直接调用导出器且没有设置跳过集合
- **THEN** 全部检查照常运行

#### Scenario: 请求集合互不污染
- **WHEN** 创建多个导出请求并修改其中一个的跳过集合
- **THEN** 其他请求的跳过集合保持不变
