# show-imported-assets · 设计

## Context

推送链路现状：`_PushWorker` 在线程里跑 `ue_remote.push()` → UE 同步执行 `HANDOFF_CODE`（`run()` + `report()`）→ `run()` 内部 `_write_back_result()` 把 `ImportResult` 写回 manifest → 协议在执行结束后才返回 `PushResult`。

也就是说：**推送返回成功的那个时刻，manifest.result 已经是最终态**。Maya 侧 `_on_push_finished` 却只显示 `PUSH_OK`（"已在 UE 中导入完成（编辑器名）"），结构化结果躺在磁盘上没人读。

另一侧，`report()` 只往 Output Log 打印文本，UE 的 Content Browser 没有任何动静——演示时要切到 UE 手动找资产。

约束：
- 远程执行是同步语义，无并发时序问题
- `ImportResult` 现有字段：`status` / `imported_clips` / `errors`，无任何 spec 钉死字段集
- 手动粘贴与自动推送共用同一段 `HANDOFF_CODE`，改动一处两路受益

## Goals / Non-Goals

**Goals:**
- 推送成功后，交付卡片呈现本次导入的资产清单（clips、首次交付的 Skeleton/SkeletalMesh）、skipped、errors
- 推送成功但 `manifest.result.status == "failed"` 时按导入失败呈现，不再显示「推送成功」
- UE 侧导入完成后 Content Browser 定位到生成的资产
- 回读任何一步失败都降级为现有 `PUSH_OK` 文案，不推翻推送成功的事实

**Non-Goals:**
- 不改推送协议、发现机制、线程模型
- 不解析 `PushResult.output` 的打印文本（那是给人看的，不是接口）
- `ImportResult` 不加 per-clip 资产路径（卡片只报名字；路径能由 `content_root + clip 名` 推出，但界面不需要）
- 不做推送进度条

## Decisions

### D1: 数据源用 manifest.result，不解析输出文本

`PushResult.output` 是 `report()` 的 print 文本，格式随时会变；`manifest.result` 是 schema 化的契约数据。呈现层只消费契约。

时序安全性来自协议本身：`ue_remote.push()` 在编辑器执行完代码、发回结果后才返回（`ue_remote.py:355`），而 `_write_back_result()` 在 `run()` 返回前已落盘。无竞态。

### D2: `ImportResult` 加两个可选字段，不新建 spec

`to_result_dict()` 目前丢弃了 `skeleton_created` / `skeletal_mesh_path`，首次交付的骨架信息到不了卡片。给 `ImportResult` 加可选的 `skeleton_path` / `skeletal_mesh_path`（空串 = 未创建）：

- `from_dict` 用 `data.get(..., "")`，旧 manifest 缺键即空——与 skip-selected-checks 处理 `validation.skipped` 的兼容模式一致
- `validate()` 不动（status 枚举不变）
- 无 spec 钉死 `ImportResult` 字段集，属实现层演进，delta 不进 export-artifacts

备选：卡片不报骨架信息。否决——首次交付恰恰是演示价值最高的场景（从零到有），不能没有。

### D3: Content Browser 同步放进 `report()`

`HANDOFF_CODE` 是 `run()` + `report()` 两行，手动路径（README 方式二）也是这两行。把同步放进 `report()` 末尾，一处改动两条路同时受益，模板不用变、README 不用改。

实现为 `unreal/importer.py` 的独立函数 `reveal_assets(outcome)`，`report()` 调用它：

- 收集路径：成功 clip 的 `asset_path` +（首次交付时）`skeletal_mesh_path` 与 `skeleton_asset_path`
- 调 `EditorAssetLibrary.sync_browser_to_assets()`，`try/except` 全包——旧引擎没有该 API、headless 跑批时静默跳过，绝不能让"定位资产"这种锦上添花弄砸导入报告

备选：放 `run()` 里。否决——`run()` 是批量/脚本入口，浏览器跳动是纯 UI 副作用，不该藏在数据层调用里。

### D4: Maya 侧呈现逻辑收在一个纯函数里

新增 `format_import_outcome(manifest_result) -> Optional[str]`（放 `bridge/` 或 UI 的纯逻辑区，不碰 Qt）：

- 输入 `ImportResult`，输出卡片多行文案；`pending` 或异常返回 `None`
- `_on_push_finished` 成功分支：`read_manifest(manifest_path)` → `format_import_outcome()` → 非空则用之，空则退回 `PUSH_OK`
- manifest 路径从窗口持有的交付结果取（`show_delivery` 的入参已含 `manifest_path`，推送与交付同一份数据）

纯函数化的理由沿用项目既定模式（检查层不碰 `maya.cmds`）：四态分支（success/partial/failed/pending）全部纯 Python 可测。

呈现规则：
- `success`：`已在 UE 中导入完成（{editor}）` + 逐行列资产
- `partial`：列出 imported 与 skipped 两组
- `failed`：头部改按失败呈现，列出 errors；卡片保持摊开（失败时收拢等于藏起手动路径，沿用现有失败分支的行为）

## Risks / Trade-offs

- [manifest 被占用或损坏，读取抛异常] → 整段回读包 `try/except`，任何异常降级为 `PUSH_OK`，推送成功事实不变
- [旧引擎没有 `sync_browser_to_assets`] → `reveal_assets` 全 try/except，失败静默
- [`ImportResult` 加字段后老 UE 代码写出的 manifest 缺键] → `from_dict` 缺键即空串，呈现层对空串不显示该行
- [卡片文案变长] → 资产逐行是结果证据，属交付卡片的本职；不截断，靠 `WordWrap` 已有行为

## Open Questions

（无——四态文案措辞在 tasks 落地时定稿）
