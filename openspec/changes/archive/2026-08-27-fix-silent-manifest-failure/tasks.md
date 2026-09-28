## 1. 默认值修正（先做，解绑失败测试）

- [x] 1.1 `bridge/schema.py` 的 `Convention.up_axis` 默认值改为 `"z"`，确认 `from_dict()` 行为不变
- [x] 1.2 `mtu_maya/core/preset_loader.py` 的 `SkeletonPreset.root_bone` 加默认值 `""`
- [x] 1.3 修正 `tests/test_preset_loader.py:106` 的错误断言，换成真正非法的样本（`pelvis extra` / `Pelvis_01`）
- [x] 1.4 用 `D:\Maya2022\bin\mayapy.exe -m unittest discover -s tests` 确认 3 个失败测试转绿、总数不减

## 2. UE 路径检查项

- [x] 2.1 `mtu_maya/checks/registry.py` 的 `CheckContext` 新增 `ue_content_root: str = ""`、`ue_skeleton_path: str = ""`、`create_skeleton_if_missing: bool = False`
- [x] 2.2 `mtu_maya/export/fbx_exporter.py` 的 `build_context()` 从 `ExportRequest` 填充这三个字段
- [x] 2.3 `mtu_maya/checks/export_checks.py` 新增 `ExportUEPathValidator`（id `export.ue_path_valid`，category `export`，level `error`，不可自动修复），按 `/Game` 前缀 → Skeleton 路径空且未勾选 → Skeleton 路径格式 的顺序返回首条错误，`details` 列全部问题
- [x] 2.4 `mtu_maya/checks/check_info.py` 补 `export.ue_path_valid` 的中文标题 / 为什么 / 怎么改
- [x] 2.5 `tests/test_checks.py` 覆盖 spec 里 `export-validation` 的 5 个场景

## 3. 产物写入结果上报

- [x] 3.1 `mtu_maya/export/manifest_writer.py` 定义 `ArtifactWriteResult`（`manifest` / `report` / `log` / `manifest_error` / `report_error`），`write_all_artifacts()` 返回它
- [x] 3.2 `mtu_maya/export/fbx_exporter.py` 的 `ExportResult` 增加 `manifest_path: str = ""`、`report_path: str = ""`，沿用 `__post_init__` 的默认值兜底模式
- [x] 3.3 `write_all_artifacts()` 把写入结果回填进 `ExportResult`，失败原因追加进 `ExportResult.errors`
- [x] 3.4 `tests/test_export.py` 覆盖 spec 里 `export-artifacts` 前 3 个场景（manifest 失败 / 报告失败 / 全成功）

## 4. UI 如实汇报

- [x] 4.1 `mtu_maya/ui/main_window.py` 的 `_on_export()` 判定改为 `result.fbx_written and result.manifest_path`
- [x] 4.2 未完成分支复用现有 `show_errors()` 展示 manifest 失败原因
- [x] 4.3 `_format_export_summary()` 成功时带上 manifest 路径；`mtu_maya/ui/strings.py` 补对应文案
- [x] 4.4 `tests/test_ui.py` 覆盖「FBX 成功但 manifest 失败 → 按未完成处理」

## 5. 收尾

- [x] 5.1 `mayapy` 跑全量测试，确认全绿
- [x] 5.2 `mayapy demo_e2e.py` 确认端到端模拟未被破坏
- [x] 5.3 README 补 mayapy 跑测试的说明，修正 Python 版本描述
- [x] 5.4 清理 `demo_e2e.py:93` 的 `__wrapped__` 死代码
