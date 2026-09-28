# export-validation · delta（smart-key-reduction）

## ADDED Requirements

### Requirement: 逐帧烘焙的稠密曲线应被点名

当骨架层级内存在 key 密度接近逐帧的动画曲线、且本次导出未启用抽稀时，系统 SHALL 给出 warning 级检查项 `anim.keys_dense`，点名最稠密的曲线并指路到导出设置的抽稀档位。启用抽稀后该检查 MUST 通过。

#### Scenario: 稠密曲线且未启用抽稀
- **WHEN** 层级内存在 key 数不低于帧跨度 90% 的曲线，且抽稀档位为关闭
- **THEN** `anim.keys_dense` 报 warning，消息点名密度最高的曲线

#### Scenario: 启用抽稀后通过
- **WHEN** 存在稠密曲线但抽稀档位非关闭
- **THEN** `anim.keys_dense` 通过

#### Scenario: 手 key 稀疏曲线不报
- **WHEN** 所有曲线的 key 密度都低于逐帧的 90%
- **THEN** `anim.keys_dense` 通过
