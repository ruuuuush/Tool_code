## Why

现有工具依靠文件存在与导入 API 返回判断交付，不能绑定 FBX 与契约，也缺少引擎产物验收和不可变版本保护。需要实现限定于已有 Skeleton 的正式动画发布闭环，并保留调试导出。

## What Changes

- 新增可选正式发布：项目、资产、正整数版本；独立版本目录，禁止覆盖、禁止跳过检查，禁止首次创建骨架。
- 标准库计算 FBX SHA-256/大小及规则、参数指纹；完整写入后才生成 ready 标识。
- 正式 manifest 不再回写；独立回执绑定发布 ID、manifest 哈希、执行 ID及预期/实际验收值。
- UE 导入前核验就绪、文件身份、目标项目、现有 Skeleton；导入后核验类型、Skeleton、帧间隔/采样数、时长、采样率、轨道、根运动和保存后读取。
- 非覆盖的版本目录保存产物，整批验收通过才给出发布成功回执；失败目录不得作为成功发布消费。已成功版本重复执行先复验，不重复导入。
- 移除普通导入路径仅凭资产存在的成功兜底。

## Capabilities

### New Capabilities
- `trusted-publication`: 不可变发布包、身份与规则约束、ready 标识及独立回执。
- `ue-animation-verification`: 实际动画属性验收、非覆盖发布与重复执行复验。

### Modified Capabilities
- `export-ui`: 正式发布入口、身份字段及可信回执显示。

## Impact

涉及 bridge schema/I/O、新增发布契约模块、Maya 导出与 UI、UE 导入/验收及测试。无新增依赖，Python 3.7/PySide2 继续支持。旧调试流程保留；正式发布通过可选字段识别，不将旧 manifest 宣称为可信发布。真实宿主联调不能由单元测试替代。
