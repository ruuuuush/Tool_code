# show-imported-assets · 任务

## 1. Schema 层（可选字段）

- [x] 1.1 `bridge/schema.py`：`ImportResult` 增加 `skeleton_path: str = ""`、`skeletal_mesh_path: str = ""`（实施中补了 `skipped_clips`：partial 场景要列跳过名单，原字段给不出）
- [x] 1.2 `from_dict` 用 `data.get(..., "")`，旧 manifest 缺键即空串；`to_dict` 带上两字段
- [x] 1.3 测试：旧 manifest（无两键）解析不报错、往返保留两字段

## 2. UE 侧

- [x] 2.1 `unreal/importer.py`：`to_result_dict()` 填 `skeleton_path`（创建时）与 `skeletal_mesh_path`
- [x] 2.2 `unreal/importer.py`：新增 `reveal_assets(outcome)`——收集成功 clip 的 `asset_path` + 首次交付的 `skeletal_mesh_path`/`skeleton_asset_path`，调 `sync_browser_to_assets`，全 try/except 静默
- [x] 2.3 `launch_ue_importer.py`：`report()` 末尾调用 `reveal_assets(outcome)`
- [x] 2.4 测试：`to_result_dict` 在创建/复用骨架两种情形下的字段值；`reveal_assets` 在无 `unreal` 模块环境下不抛异常

## 3. Maya 侧呈现

- [x] 3.1 新增纯函数 `format_import_outcome(result) -> Optional[str]`（不碰 Qt）：success / partial / failed 三态组文案，`pending` 返回 `None`
- [x] 3.2 `strings.py`：资产清单、skipped 分组、导入失败三处文案
- [x] 3.3 `main_window.py`：窗口持有本次交付的 `manifest_path`（`show_delivery` 入参已有）
- [x] 3.4 `_on_push_finished` 成功分支：回读 manifest → `format_import_outcome()` → 非空用之（failed 态头部按失败呈现、卡片保持摊开），空或异常退回 `PUSH_OK`
- [x] 3.5 测试：success / partial / failed / pending / manifest 损坏 五种输入的呈现分支

## 4. 验证

- [x] 4.1 变异检查：把 `_on_push_finished` 的回读调用去掉，确认 3.5 相关测试变红，再改回（红了 3 条，降级用例不受影响）
- [x] 4.2 `D:\Maya2022\bin\mayapy.exe -m unittest discover -s tests` 全绿（368 条）
- [x] 4.3 真机实测：导出 → 自动推送 → 卡片列出 AnimSequence 清单；切到 UE 确认 Content Browser 选中了新资产（截图确认：清单与骨架行均出现）
- [x] 4.4 真机实测：首次交付（勾「同时导出模型」）→ 卡片含 Skeleton/SkeletalMesh 行
- [x] 4.5 README「方式一」一节补一句：推送成功后卡片列出导入资产
- [x] 4.6 真机暴露：UE 长驻进程缓存旧 `mtu_unreal.*` 子模块，新 `__init__` 撞上旧 `importer` 报 ImportError——`_load_package` 驱逐缓存 + `HANDOFF_CODE` 加 `importlib.reload`（回归测试：模板含 reload 行）
- [x] 4.7 真机暴露：整段 traceback 塞进卡片标签把页面挤没——失败原因只显示最后一行、全文进 tooltip、整窗加 QScrollArea 兜底（回归测试：截断 + tooltip 留全文）

## 5. 推送成功后交接区退休

- [x] 5.1 `DeliveryCard.retire_handoff()`：置退休标记 + 隐藏；`set_collapsed` 展开分支尊重标记；`set_handoff`/`clear` 复位标记
- [x] 5.2 `_on_push_finished` 成功分支调用 `retire_handoff()`（失败与导入失败分支调 `restore_handoff()`）
- [x] 5.3 测试：成功后交接区隐藏且展开详情也不出现；失败后回来；新一轮导出重置（5 条）
