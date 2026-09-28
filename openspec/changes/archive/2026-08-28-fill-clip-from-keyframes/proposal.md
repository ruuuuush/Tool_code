## Why

【从时间轴填充】填的是播放范围，不是动画范围。`_timeline_range_from_maya()` 读 `playbackOptions` 的 `animationStartTime` / `animationEndTime`（`maya_utils.py:135-140`），那是 Maya 时间轴滑块的两端，跟骨骼上到底有没有 K 帧无关。

从网上下的动作资源，时间轴常常是默认的 1–120 或被人随手拖过，而骨骼上的 K 帧可能只有 0–35。用户点了填充，拿到一段两头都是空气的区间，还得自己去 Graph Editor 查真实范围再手改。

片段区间要的是「这段动画从哪帧到哪帧」，答案在骨骼的关键帧上，不在时间轴滑块上。

## What Changes

- **填充改为读骨骼关键帧范围**：取骨架上关键帧的最小/最大帧，作为新片段的起止帧。
- **优先读 hips/pelvis**：按当前骨骼预设的 `bone_map["pelvis"]` 定位（Mixamo 是 `Hips`，UE Mannequin 是 `pelvis`）。root 骨骼在原地动画里常常没有 K 帧，hips 则必然有。
- **逐级降级**：hips 找不到或没 K 帧 → 用户在导出设置里选的骨架根 → 场景里所有 joint → 都没有 K 帧时退回时间轴范围。
- **按钮文案随之改动**：不再叫「从时间轴填充」。
- 保留时间轴读取函数——场景信息栏仍要显示时间轴范围。

## Capabilities

### New Capabilities
<!-- 无新增能力，属于既有 export-ui 的行为修正 -->

### Modified Capabilities
- `export-ui`: 新增片段填充的取值来源要求（属于「动画片段」这一步的行为契约）。

## Impact

- `mtu_maya/core/maya_utils.py`：新增读取节点集合关键帧范围的函数
- `mtu_maya/ui/main_window.py`：`_timeline_range_from_maya()` 改为按骨骼关键帧取值并逐级降级
- `mtu_maya/ui/strings.py`：填充按钮文案
- `tests/test_checks.py` / `tests/test_ui.py`：新增关键帧范围取值与降级链的测试
- `README.md`：操作流程里对填充按钮的描述
- 检查项、导出器、manifest 均不受影响
