## ADDED Requirements

### Requirement: 片段填充取自骨骼关键帧

一键填充片段区间 SHALL 取自骨骼上实际存在的关键帧范围，MUST NOT 使用 Maya 时间轴的播放范围——播放范围是视图设置，与动画数据的实际长度无关。

#### Scenario: 关键帧范围与时间轴不一致
- **WHEN** 骨骼上的关键帧覆盖 0–35 帧，而时间轴范围是 1–120
- **THEN** 填充出的片段起止帧是 0 和 35

#### Scenario: 关键帧起点不是第一帧
- **WHEN** 骨骼上的关键帧从第 10 帧开始、到第 60 帧结束
- **THEN** 填充出的片段起止帧是 10 和 60

#### Scenario: 单帧动画
- **WHEN** 骨骼上只有一个关键帧
- **THEN** 起止帧相同，不产生倒置区间

### Requirement: 关键帧来源按 hips 优先逐级降级

关键帧范围 SHALL 优先取自当前骨骼预设映射的 hips/pelvis 骨骼。该骨骼不可用或无关键帧时，MUST 依次退到用户选定的骨架根、场景中全部关节，最终退回时间轴范围。

#### Scenario: 按预设定位 hips
- **WHEN** 当前预设是 Mixamo，其 `bone_map["pelvis"]` 指向 `Hips`
- **THEN** 填充读取 `Hips` 骨骼的关键帧范围

#### Scenario: 自定义预设没有 hips 映射
- **WHEN** 当前预设没有 pelvis 映射，但用户已选定骨架根
- **THEN** 填充读取该骨架根层级下的关键帧范围

#### Scenario: 既无映射也未选根
- **WHEN** 没有 hips 映射且未选定骨架根
- **THEN** 填充读取场景中所有关节的关键帧范围

#### Scenario: 骨骼上没有任何关键帧
- **WHEN** 场景里的关节都没有关键帧
- **THEN** 填充退回时间轴范围，不报错

#### Scenario: 无 Maya 环境不报错
- **WHEN** 在没有 Maya 的解释器中触发填充
- **THEN** 返回一个兜底区间，不抛出异常
