# smart-key-reduction · 设计

## Context

烘焙动画 = 每帧一个 key。导出链路里 FBX 插件内部 bake（`FBXExportBakeComplexAnimation`），**场景中不存在可处理的 bake 副本**——这排除了"抽稀导出副本"的原设想。唯一真实挂点是源动画曲线。

约束：
- 工具定调「不做破坏性自动修复」——历史、冻结、缩放、蒙皮只提示
- 但 `fix_check` 已有先例：**用户明确点头的**场景修改不违例
- 报告是 `.md`，GitHub 渲染；SVG 必须是独立文件相对链接（GitHub 不支持 data URI）
- mayapy 无第三方库，SVG 生成器必须纯 Python

## Goals / Non-Goals

**Goals:**
- 导出设置提供抽稀档位（关闭/低/中/高），选择持久化
- 抽稀在导出前作用于场景曲线，单 undo chunk 可整体撤销
- 算法误差有界：被删 key 的位置在线性插值下偏差 ≤ 档位容差
- 报告留下证据：数字（前后 key 数、减量%、最大误差）+ SVG 曲线叠加图
- 新检查项把「密度过高」变成可发现的问题，闭环：检查发现 → 设置处理 → 报告留证

**Non-Goals:**
- 不动 FBX 文件本身（无 FBX SDK 依赖）
- 不做切线优化——baked 数据段间近似线性，删 key 后按线性处理即可
- UE 侧零改动（压缩是引擎的事）
- 不做预览对话框——报告里的 SVG 就是证据，导出前预览属过度设计

## Decisions

### D1: 挂点 = 导出前、场景曲线上、opt-in

`export_animation()` 里检查通过之后、`_export_fbx()` 之前调用抽稀。场景被改，但：档位默认「关闭」+ 整个删除包在一个 `undoInfo` chunk（Ctrl+Z 一次恢复）+ 报告白纸黑字记录做了什么。与 `fix_check` 同一哲学：自动 destructive 才违例，用户显式选择的不违例。

备选 A：post-process FBX。否决——`import fbx` SDK 在 mayapy 的可用性不确定，引入二进制依赖风险。
备选 B：bake 到场景临时曲线再导出。否决——`FBXExport` 自己会 bake，重复 bake 无意义且碰场景更狠。

### D2: 算法 = 误差有界贪心删 key，不用 RDP

RDP 在 (t, v) 空间做垂距，时间轴和值轴单位不可比（帧 vs 厘米），需要先归一化——麻烦且语义模糊。用标准 key reduction：锚点向候选点拉弦，检查中间各点相对弦的**值偏差**；超过容差则在候选前一点落 key。O(n)、确定性、端点必留。纯函数：

```
thin_samples(times, values, tolerance) -> List[int]  # 保留的索引
```

通道容差按属性类型分：rotate 用角度、translate 用厘米、scale 用比率。档位表：

| 档位 | translate (cm) | rotate (°) | scale |
|---|---|---|---|
| 低 | 0.01 | 0.05 | 0.0001 |
| 中 | 0.05 | 0.25 | 0.0005 |
| 高 | 0.20 | 1.00 | 0.0020 |

### D3: Maya 适配层与纯算法分离

沿用检查层哲学（不直接调 cmds）：

- 纯算法 `thin_samples` 无 Maya 依赖，全单测
- 适配层 `thin_skeleton_curves(root, frame_range, level)` 干四件事：枚举层级下 animCurve → 读 keys → 调纯函数 → 删被去掉的 key
- 跳过规则：非 TU/TA 曲线（TL=stepped/bool）整条跳过；含 stepped 出切线的曲线整条跳过（布尔/枚举通道抽稀会变行为）
- 删除包在 `cmds.undoInfo(openChunk=True/closeChunk=True)`

### D4: 统计与 SVG 数据同源

`ThinningResult`  dataclass：`level / curves_touched / keys_before / keys_after / max_error / panels`。`panels` = 减量最多的 3 条通道的降采样折线（≤240 点/条，降采样在纯 Python 侧做）。SVG 生成器只消费 panels，不认识 Maya：

```
render_curve_panels(panels) -> str  # svg 文本
```

红 = 原始，蓝 = 抽稀后，带坐标轴极值标注与图例。一张 SVG 最多 3 个纵向排列面板，文件落在报告旁边 `<fbx>_thinning.svg`，报告里相对路径 `![]()` 引用。

### D5: manifest 只记摘要，报告记全部

manifest 加可选字段 `thinning = {"level": ..., "keys_before": ..., "keys_after": ...}`——交付可复现性留痕（这份 FBX 的数据被处理过、用的什么档）。`from_dict` 用 `data.get("thinning")`，旧 manifest 缺键即 `None`。per-curve 细节和 SVG 不进 manifest——那是给人看的，报告承载。

### D6: 检查项 `anim.keys_dense`（warning）

判定：层级内存在「key 数 ≥ 帧跨度 × 0.9」的曲线（即逐帧 baked）且本次抽稀档位为关闭。消息点名密度最高的曲线。需要 `CheckContext` 新增 `dense_curves: List[str]`（build_context 里统计，纯数据）。`check_info.py` 补三问文案，how_to_fix 指向导出设置的抽稀档位。

备选：做成 auto_fixable 一键抽稀。否决——fix 接口没有档位概念，且 destructive 操作藏在「修复警告」按钮里语义不对；指路比代劳诚实。

## Risks / Trade-offs

- [用户忘了场景被抽稀] → 默认关闭 + 报告记录 + 单 chunk 可撤销 + manifest 留痕，四重留证
- [抽稀误伤 stepped/开关通道] → 整条跳过，只动连续数值曲线
- [贪心算法的误差界在旋转通道上单位混淆（弧度 vs 度）] → cmds keyframe 查询返回值对 rotate 是度（角度单位跟随场景 UI 单位），适配层读 `currentUnit` 角单位，非度时先换算
- [SVG 在 GitHub 不渲染] → 独立文件 + 相对路径是 GitHub 支持的姿势；测试里校验 XML 合法性与 path 数量
- [undo chunk 与 FBX 导出之间用户 Ctrl+Z] → 时序上导出已完成，FBX 内容是抽稀后的；报告/manifest 已记录，可追溯

## Open Questions

（无）
