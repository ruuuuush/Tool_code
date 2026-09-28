# export-artifacts · delta（smart-key-reduction）

## ADDED Requirements

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
