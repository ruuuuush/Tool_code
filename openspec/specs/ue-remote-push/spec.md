# ue-remote-push

## Purpose

Maya 端把导入命令推送给正在运行的 UE 编辑器的能力：如何发现编辑器、如何执行、失败如何降级。

管线跨两个进程，Maya 端无法直接创建 UE 资产。UE 官方的 Python Remote Execution 提供了通道，但它默认关闭、依赖多播、由编辑器反向连接——每一环都可能不满足。因此这条捷径必须是**可选的加速**，而不是交付的必要条件。

## Requirements

### Requirement: 发现运行中的 UE 编辑器

系统 SHALL 通过 UE 的 Python Remote Execution 多播协议发现同机运行的编辑器，并在限定时间内给出结果，MUST NOT 无限期等待。

#### Scenario: 编辑器可达
- **WHEN** UE 编辑器正在运行且已启用远程执行
- **THEN** 发现过程返回该编辑器的节点标识与工程信息

#### Scenario: 编辑器未运行
- **WHEN** 没有任何编辑器在监听
- **THEN** 发现过程在超时后返回"未找到"，不抛出异常

#### Scenario: 逐个网络接口尝试
- **WHEN** 本机存在多个 IPv4 接口
- **THEN** 发现过程逐个接口尝试，任一接口收到应答即成功

#### Scenario: 忽略自己发出的包
- **WHEN** 多播套接字收到自己发出的 ping
- **THEN** 该消息被忽略，不被误认为编辑器应答

### Requirement: 在编辑器中执行导入命令

发现编辑器后，系统 SHALL 建立命令通道并执行多行 Python 代码，且 MUST 回传执行结果与输出。

#### Scenario: 执行成功
- **WHEN** 推送一段合法的导入代码
- **THEN** 返回结果标记为成功，并携带编辑器侧的输出文本

#### Scenario: 代码在编辑器侧报错
- **WHEN** 推送的代码在编辑器中抛出异常
- **THEN** 返回结果标记为失败，并携带错误信息，本地不抛出异常

#### Scenario: 编辑器未回连
- **WHEN** 发出连接请求后编辑器没有在超时内建立连接
- **THEN** 返回失败并说明连接未建立，套接字被释放

#### Scenario: 多行代码整体执行
- **WHEN** 推送的代码包含多条语句
- **THEN** 全部语句按顺序执行，不因单表达式限制而报语法错误

### Requirement: 协议消息格式正确

系统 SHALL 按 UE 远程执行协议构造消息：包含协议版本、魔数、来源标识，需要定向时包含目标标识。

#### Scenario: 消息包含必需字段
- **WHEN** 构造任意一条协议消息
- **THEN** 消息含 `version`、`magic`、`source`、`type` 四个字段

#### Scenario: 定向消息带目标
- **WHEN** 构造发往特定编辑器的消息
- **THEN** 消息含 `dest` 字段，值为该编辑器的节点标识

#### Scenario: 拒绝异种消息
- **WHEN** 收到魔数或版本不匹配的数据
- **THEN** 该数据被丢弃，不参与后续处理

### Requirement: 远程推送失败必须安静降级

远程推送 MUST NOT 成为交付的必要条件。任何失败 MUST 保留手动方式，并说明失败原因。当推送由导出流程自动发起时，失败 MUST NOT 改变导出成功的判定，且 MUST NOT 弹出打断性对话框——用户没有主动请求推送，不应为其失败买单。

#### Scenario: 未启用远程执行
- **WHEN** 编辑器运行但未开启远程执行
- **THEN** 界面提示未发现编辑器并保留复制代码入口

#### Scenario: 推送失败后仍可手动
- **WHEN** 推送因任何原因失败
- **THEN** 交接区的代码与复制按钮依然可用

#### Scenario: 推送不阻塞界面
- **WHEN** 推送过程正在进行
- **THEN** 等待有明确上限，界面不会无响应

#### Scenario: 自动推送失败不推翻导出结果
- **WHEN** 导出成功后自动发起的推送失败
- **THEN** 本次导出仍被判定为成功，失败信息只出现在交付卡片中，不弹出对话框

### Requirement: 在途推送不得活过其宿主

推送在后台线程执行并回调界面。宿主面板或窗口关闭时，系统 MUST 等待在途推送结束后再销毁，MUST NOT 让线程持有已销毁控件。

#### Scenario: 关闭窗口时有推送在途
- **WHEN** 推送尚未完成而用户关闭工具
- **THEN** 关闭流程等待该推送结束或超时后再继续

### Requirement: 推送成功后呈现导入结果

推送成功后，系统 SHALL 回读本次 manifest 的 `result` 字段，并以其为准在交付卡片呈现导入结果，而不仅是编辑器回显的一句话。回读失败或结果不可用时 MUST 降级为原有「推送成功」文案，MUST NOT 推翻推送成功的事实。

#### Scenario: 导入全部成功
- **WHEN** 推送成功且 `manifest.result.status` 为 `success`
- **THEN** 交付卡片显示导入完成，并逐条列出 `imported_clips` 中的 AnimSequence
- **AND** 若 `skeleton_path` 非空，列出生成的 Skeleton / SkeletalMesh

#### Scenario: 部分成功
- **WHEN** 推送成功且 `manifest.result.status` 为 `partial`
- **THEN** 交付卡片分别列出已导入与按策略跳过的片段

#### Scenario: 推送成功但导入失败
- **WHEN** 推送成功但 `manifest.result.status` 为 `failed`
- **THEN** 交付卡片按失败呈现，列出 `result.errors`
- **AND** 卡片保持摊开，手动路径（代码与复制按钮）保持可用

#### Scenario: 结果不可用
- **WHEN** 推送成功但 manifest 读取失败、损坏，或 `result.status` 仍为 `pending`
- **THEN** 交付卡片显示原有「已在 UE 中导入完成（编辑器名）」文案

### Requirement: 导入完成后在 Content Browser 中定位资产

导入流程的人读收尾（`report()`）SHALL 让 UE Content Browser 定位并选中本次生成的资产。该行为 MUST NOT 影响导入结果：定位失败或不支持时静默跳过。

#### Scenario: 有生成的资产
- **WHEN** 导入产生了 AnimSequence / Skeleton / SkeletalMesh
- **THEN** Content Browser 定位并选中这些资产

#### Scenario: 定位能力不可用
- **WHEN** 当前引擎版本无对应 API，或处于无界面环境
- **THEN** 跳过定位，导入报告照常输出，不抛出异常

#### Scenario: 推送与手动一致
- **WHEN** 通过推送或手动粘贴执行同一段导入代码
- **THEN** 两种路径都触发定位，因为定位内置于 `report()`

### Requirement: 推送成功后手动指引退休

推送成功后，系统 SHALL 隐藏交付卡片中的手动导入指引（交接区代码块），因为系统已经代劳。推送失败或新一轮导出 MUST 让手动路径重新可用。

#### Scenario: 成功后交接区隐藏
- **WHEN** 推送成功
- **THEN** 交接区（代码块与复制/推送按钮）隐藏，即使用户展开卡片详情也不出现

#### Scenario: 失败后手动路径回来
- **WHEN** 推送曾成功而之后某次推送失败
- **THEN** 交接区重新可见，复制与推送按钮可用

#### Scenario: 新一轮导出重置
- **WHEN** 推送成功后用户再次导出
- **THEN** 新交付的交接区照常显示，推送成功前不隐藏
