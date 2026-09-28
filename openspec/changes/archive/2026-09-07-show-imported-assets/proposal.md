# show-imported-assets

## Why

推送成功后 Maya 侧只显示「推送成功 + 编辑器名」，UE 里实际生成了哪些资产不可见——闭环终点没有证据，演示与日常使用都只能靠信任。UE 端早已把 `ImportResult` 写回 manifest（`unreal/importer.py` 的 `_write_back_result`），但 Maya 侧没有任何代码读它。写都写了，不读是浪费。

## What Changes

- 推送成功后，Maya 端回读本次 manifest 的 `result` 字段，在交付卡片呈现导入结果：成功逐条列出生成的 AnimSequence（首次交付含 Skeleton/SkeletalMesh），部分成功列出 skipped，失败列出 errors
- 推送成功后交接区（「下一步：在 UE 里导入」+ 代码块）退休隐藏——系统已办完，不再摆手动指引；推送失败或新一轮导出时自动恢复
- 推送的导入代码执行完让 UE Content Browser 定位到本次生成的资产，切到 UE 窗口即可看见资产就位（手动粘贴路径同样受益）
- 回读失败（manifest 缺失 / 损坏 / `result` 仍为 `pending`）MUST NOT 推翻推送成功的事实，降级为现有「推送成功」文案

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `ue-remote-push`: 推送成功的呈现从「编辑器回显一句话」升级为「回读 manifest.result 的资产清单」；推送的导入代码携带 Content Browser 定位

## Impact

- `mtu_maya/ui/main_window.py`：`_on_push_finished` 成功分支回读 manifest
- `mtu_maya/ui/strings.py`：新增结果清单文案
- `launch_ue_importer.py` 或 `unreal/importer.py`：导入完成后 Content Browser 同步（手动与推送两条路共用同一入口）
- `tests/test_ui.py` / `tests/test_ue_importer.py`：回读呈现与降级路径测试
- 无 schema 变更：`ImportResult` 字段已存在，纯消费方新增
