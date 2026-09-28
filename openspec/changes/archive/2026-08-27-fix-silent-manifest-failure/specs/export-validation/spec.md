## ADDED Requirements

### Requirement: UE 目标路径必须在导出前校验

导出检查项 SHALL 在 Maya 端校验 UE 目标路径，任何会让 `Manifest.validate()` 失败的路径组合 MUST 在导出前以 Error 级检查项阻断，且失败信息 MUST 指明具体是哪一项、该怎么改。

#### Scenario: UE 目标路径不以 /Game 开头
- **WHEN** 用户把 UE 目标路径填成 `Game/Animations` 或 `/Content/Anim` 并运行检查
- **THEN** `export.ue_path_valid` 返回 Error 级未通过，消息指出目标路径必须以 `/Game` 开头
- **AND** 导出按钮被阻断

#### Scenario: Skeleton 路径留空且未勾选同时导出模型
- **WHEN** UE Skeleton 路径为空、【同时导出模型】未勾选，用户运行检查
- **THEN** `export.ue_path_valid` 返回 Error 级未通过，消息说明要么填 Skeleton 路径、要么勾选【同时导出模型】让 UE 建骨架

#### Scenario: Skeleton 路径留空但勾选了同时导出模型
- **WHEN** UE Skeleton 路径为空、【同时导出模型】已勾选
- **THEN** `export.ue_path_valid` 通过（首次交付由 UE 端创建 Skeleton）

#### Scenario: Skeleton 路径非空但不是 UE 包路径
- **WHEN** UE Skeleton 路径填成 `Hero_Skeleton`（缺 `/Game` 前缀）
- **THEN** `export.ue_path_valid` 返回 Error 级未通过

#### Scenario: 合法的路径组合
- **WHEN** UE 目标路径为 `/Game/Animations/Hero`、Skeleton 路径为 `/Game/Animations/Hero/Hero_Skeleton`
- **THEN** `export.ue_path_valid` 通过

### Requirement: 检查上下文承载 UE 目标路径

`CheckContext` SHALL 携带 `ue_content_root`、`ue_skeleton_path`、`create_skeleton_if_missing` 三个字段，使 UE 路径检查项与其他检查项一样，`check()` 中不触碰 `maya.cmds`、可在无 Maya 环境下单测。

#### Scenario: 无 Maya 环境下运行检查项
- **WHEN** 在纯 Python 环境构造 `CheckContext` 并调用 `export.ue_path_valid` 的 `check()`
- **THEN** 返回 `CheckResult`，全程不导入 `maya.cmds`

#### Scenario: 上下文由导出请求填充
- **WHEN** `build_context()` 收到带 UE 路径字段的 `ExportRequest`
- **THEN** 生成的 `CheckContext` 中三个字段与请求一致
