# export-artifacts

## Purpose

一次导出应产出哪些交付物（FBX / manifest / report / log）、各自失败时如何上报，以及「导出成功」的判定标准。

FBX 是资产，manifest 是契约。只有两者都落盘，UE 端才拿得到可导入的一套东西——所以「成功」的定义必须包含 manifest，产物写入失败也必须浮到界面上，而不是沉在日志里。

## Requirements

### Requirement: 交付产物写入结果必须可见

一次导出产出 FBX、manifest、Markdown 报告与日志。任一产物写入失败 MUST 出现在导出结果中，MUST NOT 被静默吞掉只留日志。

#### Scenario: manifest 写入失败
- **WHEN** `write_all_artifacts()` 写 manifest 时抛异常
- **THEN** 返回结果中 manifest 路径为空且携带失败原因
- **AND** 该原因追加进 `ExportResult.errors`

#### Scenario: 报告写入失败不影响 manifest
- **WHEN** manifest 写入成功但 Markdown 报告写入失败
- **THEN** 返回结果中 manifest 路径有效、报告路径为空并带失败原因

#### Scenario: 全部写入成功
- **WHEN** 三个产物都写入成功
- **THEN** 返回结果中各路径均有效、无失败原因、`ExportResult.errors` 不新增内容

### Requirement: 导出成功的判定包含 manifest

UI SHALL 只在 FBX 与 manifest 都写入成功时报告「导出完成」。FBX 写成但 manifest 未写成 MUST 按未完成处理并列出具体原因。

#### Scenario: FBX 成功但 manifest 失败
- **WHEN** 导出后 `fbx_written` 为真但 manifest 写入失败
- **THEN** UI 显示未完成，并在导出面板与弹窗中列出 manifest 的失败原因

#### Scenario: 两者都成功
- **WHEN** FBX 与 manifest 都写入成功
- **THEN** UI 显示导出完成，摘要中包含 manifest 路径

### Requirement: 默认值不得产出自身校验不通过的对象

数据类的默认构造结果 MUST 能通过自身的校验逻辑；缺省即非法的字段 MUST 给出合法默认值或改由构造方显式提供。

#### Scenario: 默认 Convention 通过 Manifest 校验
- **WHEN** 用 `Convention()` 默认值组装一份其余字段合法的 `Manifest` 并调用 `validate()`
- **THEN** 校验通过

#### Scenario: SkeletonPreset 只给必填标识即可构造
- **WHEN** 以 `SkeletonPreset(id=..., display_name=..., skeleton_type=...)` 构造预设
- **THEN** 构造成功，`root_bone` 取空字符串默认值

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

### Requirement: 抽稀执行必须在交付物中留痕

一次导出若执行了关键帧抽稀，manifest SHALL 携带可选 `thinning` 摘要（档位与前后 key 计数），导出报告 SHALL 包含「关键帧抽稀」一节：档位、前后 key 数、减量百分比、最大误差，以及一张曲线叠加对比图的相对路径链接。未执行抽稀时摘要与该节 MUST NOT 出现。

#### Scenario: 执行抽稀后 manifest 带摘要
- **WHEN** 导出以非关闭档执行了抽稀
- **THEN** manifest 含 `thinning` 字段，记录档位与前后 key 总数

#### Scenario: 报告含数字与图
- **WHEN** 导出以非关闭档执行了抽稀
- **THEN** 报告包含档位、前后 key 数、减量百分比、最大误差
- **AND** 报告链接一张位于报告旁边的 SVG 曲线叠加图，图中同时画出原始（红）与抽稀后（蓝）曲线

#### Scenario: 未抽稀时无痕
- **WHEN** 档位为关闭
- **THEN** manifest 无 `thinning` 字段，报告无抽稀一节

#### Scenario: 旧 manifest 兼容
- **WHEN** 读取一份没有 `thinning` 键的旧 manifest
- **THEN** 解析不报错，该字段为无

### Requirement: SVG 图必须是自包含合法文档

报告引用的曲线对比图 SHALL 为纯文本 SVG 文件，不依赖任何外部资源，与报告位于同一目录并以相对路径引用。

#### Scenario: 图随报告落盘
- **WHEN** 抽稀执行且报告写入成功
- **THEN** SVG 文件与报告位于同一目录，内容为合法 XML，且含原始与抽稀后两条折线
