## Why

导出可以"成功"却不产出 manifest。当 ③ 里的 **UE Skeleton 路径**留空且未勾【同时导出模型】，或 **UE 目标路径**不以 `/Game` 开头时：所有检查项通过 → FBX 正常写盘 → `Manifest.validate()` 在写入前抛错 → `write_all_artifacts()` 吞掉异常只记进 `pipeline.log` → UI 弹「导出完成」。

动画师拿到一个孤立的 FBX，UE 端没有 manifest 可读，整条交付链断在一个没人看的日志行上。工具的核心承诺是"有校验、可复现"，而这里恰恰是校验失效的地方。

## What Changes

- **新增 UE 目标路径检查项**（`export.*`，Error 级）：在导出前就拦住无效的 `ue_content_root` / `ue_skeleton_path` 组合，让用户在 UI 上看到具体原因，而不是导出后才在日志里失败。
  - `ue_content_root` 必须以 `/Game` 开头
  - `ue_skeleton_path` 为空时，必须勾选【同时导出模型】（否则 UE 无法从纯动画 FBX 建骨架）
  - `ue_skeleton_path` 非空时必须以 `/Game` 开头
- **交付产物写入结果纳入导出结果**：`ExportResult` 携带 manifest/report 的写入结果，`write_all_artifacts()` 不再静默吞错。
- **UI 如实汇报**：manifest 写失败时，导出面板与弹窗按"未完成"处理并列出原因，不再只凭 `fbx_written` 判定成功。
- 顺带修复 3 个失败单元测试（`SkeletonPreset.root_bone` 无默认值、`Convention()` 默认 `up_axis` 过不了自身校验、命名正则断言与正则语义不符）。

## Capabilities

### New Capabilities
- `export-validation`: Maya 端导出前的检查项契约——哪些条件阻断导出、分级如何、失败信息给到什么粒度。本次覆盖 UE 目标路径这一类。
- `export-artifacts`: 一次导出应产出哪些交付物（FBX / manifest / report / log）、各自失败时如何上报，以及"导出成功"的判定标准。

### Modified Capabilities
<!-- openspec/specs/ 目前为空，无既有 spec 需要改动 -->

## Impact

- `mtu_maya/checks/export_checks.py`：新增检查项类
- `mtu_maya/checks/registry.py`：`CheckContext` 需要携带 UE 目标路径字段
- `mtu_maya/checks/check_info.py`：新检查项的中文标题/原因/怎么改
- `mtu_maya/export/fbx_exporter.py`：`build_context()` 填充新字段；`ExportResult` 增加产物写入结果
- `mtu_maya/export/manifest_writer.py`：`write_all_artifacts()` 返回结构化结果而非吞错
- `mtu_maya/ui/main_window.py`：导出成功/失败判定与错误展示
- `mtu_maya/ui/strings.py`：新增文案
- `bridge/schema.py`、`mtu_maya/core/preset_loader.py`：默认值修正（配套测试修复）
- `tests/`：新增检查项测试 + 修复 3 个失败断言
- 运行测试需用 `D:\Maya2022\bin\mayapy.exe`（本机无独立 Python 3）
