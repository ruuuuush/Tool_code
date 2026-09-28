# export-validation

## Purpose

Maya 端导出前的检查项契约：哪些条件阻断导出、分级如何、失败信息给到什么粒度。

管线的单一事实源是 manifest。任何会让 manifest 写不出去的条件，都必须在 FBX 落盘之前以 Error 级检查项拦住——否则用户会拿到一个 UE 读不了的孤立 FBX。

## Requirements

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

### Requirement: 检查项可按需跳过

系统 SHALL 允许用户逐项关闭检查。被关闭的检查 MUST NOT 执行，其结果 MUST 标记为已跳过，MUST NOT 被记为通过。跳过对所有严重级别开放。

#### Scenario: 关闭的检查不执行

- **WHEN** 用户取消勾选某个检查项并运行检查
- **THEN** 该检查的执行逻辑不被调用，结果中该项标记为已跳过

#### Scenario: 跳过不等于通过

- **WHEN** 一次检查运行中有项被跳过
- **THEN** 该项既不计入通过数，也不计入失败数，状态可与通过、失败区分

#### Scenario: 未勾选的错误级检查不阻断导出

- **WHEN** 某个 error 级检查被跳过
- **THEN** 导出门禁不因该项而关闭

#### Scenario: 仍在执行的错误级检查照常阻断

- **WHEN** 某个 error 级检查未被跳过且未通过
- **THEN** 导出门禁关闭，与跳过功能引入前一致

#### Scenario: 跳过仅在本次会话有效

- **WHEN** 用户跳过若干项后重新打开工具
- **THEN** 所有检查项恢复为勾选状态，跳过选择不被保留

#### Scenario: 自动修复不触碰跳过项

- **WHEN** 用户点击一键修复所有警告，且某警告项已被跳过
- **THEN** 该项不被修复

### Requirement: 跳过检查必须留痕

跳过 MUST 在交付物中可追溯。系统 SHALL 在验证摘要中记录每个被跳过检查的标识与其声明级别；存在被跳过项时，导出前 MUST 向用户确认，并 MUST 说明其中有多少项属于会阻断导出的错误级。

#### Scenario: 验证摘要记录被跳过的项

- **WHEN** 一次导出中有检查被跳过
- **THEN** 写出的验证摘要包含这些检查的标识与级别

#### Scenario: 没有跳过时不留冗余记录

- **WHEN** 所有检查都执行了
- **THEN** 验证摘要中被跳过项的记录为空

#### Scenario: 导出前确认跳过

- **WHEN** 用户在存在被跳过项的情况下发起导出
- **THEN** 界面先行确认，说明跳过项总数与其中错误级的数量

#### Scenario: 取消确认即不导出

- **WHEN** 用户在跳过确认中选择否
- **THEN** 导出不执行，不产生任何交付物

#### Scenario: 无跳过项时不打扰

- **WHEN** 用户在没有任何跳过项的情况下发起导出
- **THEN** 不出现跳过确认

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
