## ADDED Requirements

### Requirement: 导出完成后给出 UE 侧交接指引

Maya 端导出只产出 FBX 与 manifest，不会在 UE 工程中创建任何资产。交付完整时，界面 MUST 明确指出还需要在 UE 侧执行导入，并 MUST 提供可直接执行的命令，其中 manifest 路径已填为本次导出的实际路径。

#### Scenario: 交付完整时出现交接指引
- **WHEN** 一次导出的 FBX 与 manifest 都写入成功
- **THEN** 交付清单下方显示前往 UE 导入的指引与命令

#### Scenario: 命令带本次的 manifest 路径
- **WHEN** 用户查看交接指引中的命令
- **THEN** 命令中的 manifest 路径是本次导出实际写出的路径，不是占位符

#### Scenario: 一键复制
- **WHEN** 用户点击复制按钮
- **THEN** 完整命令被写入系统剪贴板，可直接粘贴到 UE 的 Python 控制台

#### Scenario: 交付不完整时不显示
- **WHEN** FBX 写出但 manifest 写入失败
- **THEN** 不显示 UE 交接指引，界面仍然只报告交付不完整

#### Scenario: 导出被检查阻断时不显示
- **WHEN** 导出因检查未通过而未执行
- **THEN** 不显示 UE 交接指引

### Requirement: UE 目标路径标明其归属

导出设置中的 UE 相关字段 MUST 让用户看出它们是写给 UE 侧的约定，而不是 Maya 端会代为执行的动作。

#### Scenario: 字段归属可辨识
- **WHEN** 用户在导出设置里看到 UE 目标路径与 UE Skeleton 路径
- **THEN** 界面表明这些值将写入 manifest 供 UE 侧导入时使用
