# smart-key-reduction · 任务

## 1. 纯算法（无 Maya 依赖）

- [x] 1.1 新建 `mtu_maya/core/curve_thinning.py`：`thin_samples(times, values, tolerance) -> List[int]`，误差有界贪心删 key，端点必留
- [x] 1.2 档位表 `THINNING_LEVELS`：off/low/medium/high → (translate_cm, rotate_deg, scale_ratio) 容差
- [x] 1.3 `ThinningResult` dataclass：level / curves_touched / keys_before / keys_after / max_error / panels（减量前 3 通道的降采样折线，≤240 点/条）
- [x] 1.4 测试：直线抽干、误差 ≤ ε、端点保留、全平零误差、档位容差单调

## 2. Maya 适配层

- [x] 2.1 `thin_skeleton_curves(root, frame_range, level) -> ThinningResult`：枚举层级 animCurve → 读 keys → 纯函数 → 删 key
- [x] 2.2 跳过规则：非 animCurveTU/TA 整条跳过；含 stepped 出切线整条跳过
- [x] 2.3 角单位换算：读 `currentUnit`，非度时旋转值先换成度再进算法
- [x] 2.4 全部删除包在一个 `undoInfo` chunk
- [x] 2.5 测试（假 cmds 桩）：跳过规则、undo chunk 成对调用、统计正确

## 3. 导出串接

- [x] 3.1 `ExportRequest.thinning_level: str = "off"`；`ExportResult.thinning: Optional[ThinningResult]`
- [x] 3.2 `export_animation()`：检查通过且档位非关闭时，`_export_fbx` 之前调 `thin_skeleton_curves`
- [x] 3.3 `bridge/schema.py`：`Manifest.thinning` 可选 dict，`from_dict` 用 `data.get`
- [x] 3.4 测试：档位 off 不调抽稀；非 off 时 result.thinning 有值；manifest 往返保留 thinning

## 4. 报告与 SVG

- [x] 4.1 新建 `mtu_maya/export/curve_svg.py`：`render_curve_panels(panels) -> str`，纯 Python，红/蓝双折线 + 轴极值 + 图例
- [x] 4.2 `write_markdown_report`：有 `result.thinning` 时写「关键帧抽稀」一节 + SVG 落盘 `<fbx>_thinning.svg` + 相对路径引用；无则不出现该节
- [x] 4.3 测试：SVG 合法 XML（`xml.etree` 解析）且含两条 polyline；报告有/无抽稀两态差异；SVG 与报告同目录

## 5. 检查项 anim.keys_dense

- [x] 5.1 `CheckContext` 加 `dense_curves: List[str]`；`build_context` 统计 key 数 ≥ 帧跨度 90% 的曲线
- [x] 5.2 `anim_checks.py` 新增 validator：稠密且抽稀关闭 → warning，点名最稠密曲线；启用抽稀 → 通过
- [x] 5.3 `check_info.py` 补三问文案，how_to_fix 指向抽稀档位
- [x] 5.4 测试：稠密未开抽稀报 warning、开了通过、稀疏通过

## 6. UI 与配置

- [x] 6.1 `strings.py`：档位标签与悬浮提示（说明可 Ctrl+Z 撤销）
- [x] 6.2 导出设置加抽稀档位下拉，默认关闭；`_on_export` 读进 `ExportRequest`
- [x] 6.3 `PipelineSettings.key_thinning: str = "off"` + 校验 + `default_settings.json` 补键；`_apply_export_defaults` 回填
- [x] 6.4 测试：默认关闭、档位进 ExportRequest、配置回填

## 7. 验证

- [x] 7.1 变异检查：误差判定改为恒不删，红 2 条（误差界 + 零容差），改回全绿
- [x] 7.2 `D:\Maya2022\bin\mayapy.exe -m unittest discover -s tests` 全绿（400 条）
- [x] 7.3 Maya 内实测：对 walk.fbx 场景开「中」档导出 → 报告有抽稀节 + SVG；Ctrl+Z 一次 key 全回来
- [x] 7.4 出图确认：SVG 在浏览器/GitHub 渲染正常，红蓝可辨
- [x] 7.5 实测暴露：FBX 行写死「见下方原因」，但原因框在第②步、人站在第③步，承诺永远兑现不了——失败原因内联进卡片 FBX 行（红字 + tooltip），文案不再指虚空（回归测试：原因随行显示）
- [x] 7.6 实测暴露：`keyframe` 没有 `clear` 旗标，删 key 的正确 API 是 `cutKey(clear=True)`。假 cmds 桩把不存在的旗标实现出来导致测试空绿——教训：假桩必须镜像真实 API 表面。已修代码 + 修桩

## 8. 卡片内嵌曲线预览

- [x] 8.1 新建 `mtu_maya/ui/curve_plot.py`：`CurveCompareWidget`，QPainter 画紧凑面板（标题 + 红/蓝折线），消费 `CurvePanel`，零新依赖
- [x] 8.2 `DeliveryCard.set_thinning_panels()`：有面板显示、无则隐藏；收拢不收预览；`clear()` 复位
- [x] 8.3 `show_delivery` 把 `result.thinning.panels` 传进卡片
- [x] 8.4 测试：离屏渲到 QImage 断言红/蓝像素都画上；无抽稀不显示；收拢后仍可见
