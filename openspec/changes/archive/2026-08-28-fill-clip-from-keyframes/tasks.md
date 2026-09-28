## 1. 关键帧读取

- [x] 1.1 `maya_utils.py` 新增 `keyframe_range(nodes)`：返回 `(min, max)` 整数帧，无关键帧时返回 `None`
- [x] 1.2 新增 `subtree_joints(root)`：展开根关节及其全部子孙关节
- [x] 1.3 两个函数都在无 Maya 环境下安全失败

## 2. 降级链

- [x] 2.1 `main_window.py` 把 `_timeline_range_from_maya()` 改名为 `_animation_range_from_maya()`，实现 hips → 骨架根子树 → 全场景 joint → 时间轴 的候选序列
- [x] 2.2 hips 定位：`preset.bone_map.get("pelvis")` + `maya_utils.resolve_joint()`
- [x] 2.3 每一级用 try/except 包住，单级失败只跳到下一级
- [x] 2.4 `ClipTablePanel` 的构造参数名同步更新（回调签名不变）

## 3. 文案

- [x] 3.1 `strings.py` 的 `BTN_FILL_TIMELINE` 改为 `BTN_FILL_RANGE`，文案改为「填充动画范围」
- [x] 3.2 更新引用处

## 4. 测试

- [x] 4.1 `tests/test_maya_utils.py` 覆盖 `keyframe_range` 的取值、单帧、取整、空输入（新建，15 个用例）
- [x] 4.2 覆盖降级链四级：hips 命中 / 骨架根命中 / 全场景命中 / 退回时间轴
- [x] 4.3 覆盖无 Maya 环境不抛异常
- [x] 4.4 确认既有 `ClipTablePanel` 填充测试仍通过

## 5. 收尾

- [x] 5.1 `mayapy` 跑全量测试，确认全绿（255 个）
- [x] 5.2 README 更新填充按钮的描述
