## Context

已有 425 项测试，调试导出可跳过检查、首次创建骨架、重命名或覆盖；正式发布必须独立于这些便利。运行环境 Python 3.7/PySide2，UE 官方 AnimationLibrary 暴露帧间隔、采样数、时长和轨道查询。

## Goals / Non-Goals

**Goals:** 已有 Skeleton 动画的可信发布包、严格规则、引擎实际验收、不可变清单、非覆盖版本和可追踪回执。

**Non-Goals:** Max、部署平台、骨架首次发布、更新已有生产引用、全批次引擎事务、运动姿势误差比较、远程恶意篡改防护。

## Decisions

- 正式请求以可选 PublicationRequest 识别；保留调试路径，不用隐式严格规则破坏现有用户。项目/资产标识只允许 ASCII 字母数字下划线，版本为正整数。
- 发布目录 `<export-dir>/<project>/<asset>/vNNN` 通过 mkdir 独占预留，已存在即拒绝；失败目录保留诊断，换版本重试，不自动删除用户资产。不是文件系统多文件事务。
- 正式发布使用 manifest 1.1 及可选 publication 字典，旧导入器不支持 1.1 会明确拒绝；调试仍为 1.0。发布清单包含发布 ID、项目、资产、版本、规则指纹、参数指纹、FBX 哈希/大小、必要骨骼。
- 临时文件+fsync+os.replace 加固 JSON 写入；FBX/report/manifest 完整后才写 ready.json，包含 manifest 字节哈希。消费者先核验 ready 与两份哈希。哈希是完整性而非签名。
- 正式模式拒绝任何跳过检查、首次骨架创建、单帧片段；重新执行全部实时检查，冻结规则/参数指纹。规则指纹覆盖 checks/config/preset 代码及配置内容；记录工具版本。
- UE 正式发布进入 `<content-root>/<project>/<asset>/vNNN`，预检所有目标冲突，不删除旧资产。所有片段验收通过才写 success 回执；失败时已导入的版本可能保留，但回执明确失败，不能宣称事务回滚。
- 独立 import_receipt.json 包含执行 ID、发布 ID、manifest 哈希、引擎项目/版本、逐片段 expected/actual/errors 及结果。回执写入失败上浮为错误。成功回执重复执行先复验实际资产，不重新导入；不允许仅凭回执跳过检查。
- UE 验收使用 AnimationLibrary 的 get_num_frames/get_num_keys/get_sequence_length/get_animation_track_names 与 AnimSequence.get_data_model().get_frame_rate()；帧间隔=end-start，采样数=end-start+1，时长=(end-start)/fps，率比较 rational。先保存，再从资产库重新取得资产验收，不宣称强制从磁盘卸载重载。
- 项目名称由 UE SystemLibrary.get_project_name 比对；Skeleton 必须为实际 Skeleton。验收 API 不可用即失败，不隐式放行。
- Maya UI 增加可折叠正式发布字段，切正式后禁止跳过及同时导模型，正式结果读取独立回执；缺回执不当成导入成功。

## Risks / Trade-offs

- UE API 行为需宿主验证 → 增加 mocked 失败回归，提供真实宿主手动验证入口；未实测明确标记。
- 原版本引用不自动更新 → 正式版本可选用且可追踪，本轮不做生产引用迁移。
- 网络盘及并发引擎实例不是事务 → 发布目录独占、UE 全目标预检；本轮不宣称分布式锁。
- 规则指纹跨机器必须稳定 → 使用相对路径排序与原始文件内容哈希，不把绝对路径加入指纹。

## Migration Plan

新正式流程为可选，旧调试清单与 UI 保留。发布清单不得被旧导入器误当作可信验收，文档记录双方需同版本。未就绪包拒绝导入。无需自动转换旧发布。

## Open Questions

真实 UE 版本与项目将由使用者实测，当前不能承诺真实 Maya→UE 已通过。本轮只实现限定能力，不预设可修改的目标项目。
