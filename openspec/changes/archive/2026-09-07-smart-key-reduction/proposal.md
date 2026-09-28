# smart-key-reduction

## Why

管线是管道工活：干得好的时候恰恰 invisible。导出报告现在全是文字表格，招聘方不装任何软件就看不到任何"功夫"。同时烘焙动画（每帧一个 key）是真实的资产冗余问题——FBX 体积大、曲线编辑器里没法手改。

给工具加一条"算法 + 证据"的纵深感：**导出前可按档抽稀关键帧，报告里留下量化数字和曲线对比图**。

## What Changes

- 导出设置新增「关键帧抽稀」档位：关闭（默认）/ 低 / 中 / 高，持久化到配置
- 抽稀作用于**场景动画曲线**、导出前执行：FBX 插件内部 bake，不存在可处理的"bake 副本"，唯一真实挂点是源曲线。整段删除包在一个 undo chunk 里，Ctrl+Z 一次全恢复；默认关闭，不动「不做破坏性自动修复」的定调
- 误差有界的贪心抽稀算法（纯 Python，可单测）：删除的 key 在线性插值下偏差不超过档位容差；平移/旋转/缩放通道各有容差；stepped 通道整条跳过；首尾 key 永远保留
- 导出报告新增「关键帧抽稀」一节：档位、key 数前后对比、减量百分比、最大误差，并链接一张 **SVG 曲线叠加图**（纯 Python 生成，零依赖，GitHub 直接渲染；红色原始 / 蓝色抽稀后，取减量最多的 3 条通道）
- manifest 增加可选 `thinning` 摘要（档位 + key 计数），交付可复现性留痕；旧 manifest 缺键即无
- 交付卡片内嵌「抽稀对比」预览带：QPainter 手画红蓝曲线（与 SVG 同一份 `CurvePanel` 数据，两个渲染器），收拢态也保留——证据就地可见，不用开任何文件
- 新增检查项 `anim.keys_dense`（warning）：曲线 key 密度接近逐帧且抽稀关闭时提示——「检查发现 → 同界面处理 → 报告留证」的完整 loop

## Capabilities

### New Capabilities

- `curve-thinning`: 误差有界的关键帧抽稀：档位定义、算法契约、场景执行与 undo、统计产出

### Modified Capabilities

- `export-artifacts`: 导出报告新增抽稀一节与 SVG 图链接；manifest 可选 `thinning` 摘要
- `export-ui`: 导出设置新增「关键帧抽稀」档位控件，选择持久化
- `export-validation`: 新增 `anim.keys_dense` 检查项

## Impact

- 新增 `mtu_maya/core/curve_thinning.py`：纯算法 + Maya 适配层（cmds 隔离）
- 新增 `mtu_maya/export/curve_svg.py`：纯 Python SVG 生成器
- `mtu_maya/export/fbx_exporter.py`：`ExportRequest.thinning_level`、`ExportResult.thinning`、导出前调用抽稀
- `mtu_maya/export/manifest_writer.py`：报告抽稀节 + SVG 落盘
- `bridge/schema.py`：`Manifest.thinning` 可选字段
- `mtu_maya/checks/anim_checks.py` + `check_info.py`：`anim.keys_dense`
- `mtu_maya/core/config.py` + `config/default_settings.json`：`key_thinning` 档位持久化
- `mtu_maya/ui/main_window.py` / `strings.py`：档位控件
- 测试：算法误差界/端点/stepped 跳过、SVG 合法性、报告差异、UI 持久化
