## Context

管线的契约是 manifest：Maya 端写、UE 端读。现在有一条路径能让 FBX 写成而 manifest 写不成，且两端都不知情。

失效链条：
1. `export_checks.py` 的四个检查项只管 FBX 侧（插件/路径/命名/骨架根），没有任何检查项碰 UE 目标路径。
2. `fbx_exporter.export_animation()` 把 UI 里的 `ue_content_root` / `ue_skeleton_path` 原样塞进 `Manifest`。
3. `bridge/schema.py:432,445` 的 `validate()` 要求 `content_root` 以 `/Game` 开头、`skeleton_path` 非空（除非 `create_if_missing`）。
4. `manifest_writer.write_all_artifacts()` 用 `try/except` 包住 `write_export_manifest()`，失败只 `append_log`，返回 `paths["manifest"] = None`。
5. `main_window._on_export()` 只看 `result.fbx_written`，为真就弹「导出完成」。

既有约束：检查项 `check()` 不得触碰 `maya.cmds`（这是全部检查项能在无 Maya 环境单测的前提）；`ExportResult` 的既有字段被 `manifest_writer` 和 `tests/test_export.py` 依赖，不能破坏。

## Goals / Non-Goals

**Goals:**
- 无效的 UE 路径在 Maya 端就被 Error 级检查项拦住，用户在 UI 上看到具体是哪一项、怎么改。
- manifest / 报告写入失败必须进入 `ExportResult` 并被 UI 展示。
- 「导出完成」的判定包含 manifest。
- 三个失败测试转绿，且修的是产品代码的默认值问题，不是把断言改成迁就代码。

**Non-Goals:**
- 不改 `Manifest.validate()` 的既有规则（`/Game` 前缀、`skeleton_path` 必填）——那些规则是对的，缺的是提前校验。
- 不动 UE 端 importer。
- 不引入 manifest schema 版本迁移。
- 不重构检查项框架。

## Decisions

### 决策 1：新增一个检查项 `export.ue_path_valid`，而不是拆成三个

`ue_content_root` 与 `ue_skeleton_path` 的合法性是耦合的——Skeleton 路径能不能为空，取决于是否勾了【同时导出模型】。拆成三个检查项会让用户看到三行互相矛盾的提示。一个检查项、按优先级返回第一条具体错误信息，配 `details` 列出全部问题。

*备选*：直接在 `export_animation()` 里预跑一次 `manifest.validate()`。否决——错误信息是给开发者看的英文 schema 报错，且绕过了检查项框架，UI 上不显示、不可单测、不可扩展。

### 决策 2：`CheckContext` 加三个字段，而不是让检查项读 `ExportRequest`

检查项的契约是"只吃 `CheckContext`"。让它拿到 `ExportRequest` 会开一个口子，往后检查项就会开始依赖 Maya 侧对象。新增 `ue_content_root: str = ""`、`ue_skeleton_path: str = ""`、`create_skeleton_if_missing: bool = False`，都给默认值，既有构造 `CheckContext` 的测试不受影响。

### 决策 3：产物写入结果用一个 `ArtifactWriteResult` 数据类，不改 `write_all_artifacts()` 返回 dict 的形状语义

`write_all_artifacts()` 现在返回 `{"manifest": path|None, "report": path|None, "log": path}`。改成返回一个数据类，同时挂上 `manifest_error` / `report_error`。调用方只有 UI 和测试，改动面可控；保留 `manifest` / `report` / `log` 三个属性名，读取代码不变。

*备选*：让 `write_export_manifest()` 直接抛出去。否决——那会让报告和日志也写不成，用户连失败记录都拿不到。

### 决策 4：`ExportResult` 加 `manifest_path` / `report_path` 字段，写入失败原因并入 `errors`

UI 现有的错误展示已经在读 `result.errors`（`_on_export` 的 else 分支、`show_errors()`）。把 manifest 失败原因并进去，UI 那条链路自然复用。判定改成 `result.fbx_written and result.manifest_path`。

`ExportResult` 的 `errors` 字段是 `List[str] = None` + `__post_init__` 兜底，新字段跟着这个模式给默认值，`tests/test_export.py` 的既有构造不受影响。

### 决策 5：默认值修正，不是改断言

- `Convention.up_axis` 默认 `""` → `"z"`：schema 自己的 `validate()` 只接受 `y`/`z`，默认构造出一个必然非法的对象是缺陷。选 `z` 因为它是 UE 的朝上轴，也是本工具面向的目标。
- `SkeletonPreset.root_bone` 默认 `""`：`custom` 预设本来就是空 root，`from_dict()` 也是 `data.get("root_bone", "")`，dataclass 上缺默认值纯属遗漏。
- `test_preset_loader` 里 `pelvis_extra` 的断言：正则 `^[a-z]+(_[a-z0-9]+)*(_l|_r)?$` 按设计就该接受 `pelvis_extra`（UE 骨骼名如 `index_01_l` 正是这个形状）。这里是**断言写错**，改成真正非法的样本（如 `pelvis extra`、`Pelvis_01`）。

### 决策 6：测试用 `mayapy` 跑

本机只有 Python 2.7 + `D:\Maya2022\bin\mayapy.exe`（Python 3.7）。README 写的 3.10+ 与实际可用环境不符，在 README 补一行 mayapy 跑法。代码不得使用 3.8+ 语法（walrus 在 3.8、`match` 在 3.10）——现有代码符合。

## Risks / Trade-offs

- **新增 Error 级检查项会让既有场景"突然导不出来"** → 这正是目的：以前是导出后静默失败。信息里必须写清怎么改，不能只说"非法"。
- **`Convention.up_axis` 默认值从 `""` 变 `"z"`** → 有代码依赖"默认为空"来判断"未设置"的话会受影响。已确认唯一构造方 `fbx_exporter.export_animation()` 总是显式传 `ctx.scene_up_axis`，无隐式依赖。
- **`write_all_artifacts()` 返回类型变化** → 调用方仅 `main_window` 与测试；保留同名属性降低破坏面。
- **mayapy 跑测试比独立 Python 慢且绑定 Maya 安装** → 只影响本机开发，CI 层面不作要求。
