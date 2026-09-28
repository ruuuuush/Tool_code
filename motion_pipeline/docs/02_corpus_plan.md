# 语料扩充计划（Corpus Plan）

> 目的：把 §9.6 的阈值从「流程验证」（n=8）变成可用数字，并给 Step 4/5 的
> PoseSearch 数据库提供源数据。
> 状态：**等待下载**。本文档是清单和约定，不是结论。

---

## 1. 为什么需要，需要多少

当前语料：2 条真实片段（`Standard Walk`、`walk`），planting-role 样本 n=8。

- 标定的 p95 阈值在 n=8 上毫无统计意义（§10.3 里它拒绝了自己的源）
- 镜像的实际收益取决于**非对称内容占比**（§2.2），2 条对称走路测不出来
- Step 5 建 PoseSearch 数据库需要覆盖速度/方向空间

**目标：25–30 条**。经验上这是单人语料能撑起基本 locomotion MM 的下限。

## 2. 下载清单（Mixamo）

按覆盖优先级排序。**非对称片段优先**——它们镜像后真正翻倍库容量（§2.2 情况 B）。

### P0 · 方向与转向（非对称，镜像收益最大）

| # | Mixamo 搜索词 | 期望内容 |
|---|---|---|
| 1 | Left Turn | 原地左转 90° |
| 2 | Right Turn | 原地右转 90°（与 1 不是镜像对——姿态细节不同，两条都要） |
| 3 | Walking Turn 180 | 行走中掉头 |
| 4 | Left Strafe Walking | 左横移 |
| 5 | Right Strafe Walking | 右横移 |
| 6 | Left Strafe | 左横移（跑） |
| 7 | Right Strafe | 右横移（跑） |
| 8 | Jog Forward Diagonal | 斜向慢跑（左右各一条） |

### P1 · 速度档（填补速度空洞）

| # | 搜索词 | 期望内容 |
|---|---|---|
| 9 | Slow Walk | 慢走 |
| 10 | Walking | 常速走（与已有 Standard Walk 不同源，可交叉验证） |
| 11 | Brisk Walk | 快走 |
| 12 | Jogging | 慢跑 |
| 13 | Running | 跑 |
| 14 | Sprint | 冲刺 |

### P2 · 起停与过渡

| # | 搜索词 | 期望内容 |
|---|---|---|
| 15 | Start Walking | 静止→走 |
| 16 | Stop Walking | 走→静止 |
| 17 | Run To Stop | 跑→急停 |
| 18 | Idle | 站立呼吸（MM 需要 idle 锚点） |
| 19 | Idle Look Around | 带头部动作的 idle（丰富 idle 姿态） |

### P3 · 加分项（有余力再下）

| # | 搜索词 | 期望内容 |
|---|---|---|
| 20 | Walking Backwards | 倒走 |
| 21 | Running Backward | 倒跑 |
| 22 | Crouched Walking | 蹲走（扩姿态空间） |
| 23 | Jump | 跳（测试 airborne 的 unmeasurable 路径） |

## 3. 下载设置（每条都一样）

| 设置 | 值 | 原因 |
|---|---|---|
| Format | FBX Binary | — |
| Skin | **Without Skin** | 采样器只读关节；不带蒙皮文件小一个量级 |
| Frames per Second | **30** | 与 `--fps 30` 对齐；Mixamo 原生 30 |
| Keyframe Reduction | **none** | 密集烘焙。抽稀过的曲线会让滑动度量失真（§10.2 末的插值敏感性） |
| In Place | 勾选（如有该选项） | 与现有两条源一致；root motion 版另存为 `_rm` 后缀 |

## 4. 目录与命名约定

```
motion_pipeline/
└── corpus/
    ├── source/          ← 所有下载的源 FBX，平铺，不分子目录
    └── (augmented/)     ← 扩增产物；--out 指到这里，绝不混进 source
```

命名：`<类别>_<描述>[_rm].fbx`，小写下划线。例：

```
turn_left_90.fbx
strafe_walk_left.fbx
walk_slow.fbx
idle_breathing.fbx
walk_normal_rm.fbx      ← root motion 版本
```

**规则：`source/` 平铺、只放源。** `expand_paths` 故意不递归子目录——
扩增产物混回源目录是最需要杜绝的错误。

## 5. 下载后跑什么

```bat
:: 1. 全量基线扫描（core 目录整个传进去）
mayapy launch_baseline_scan.py --fps 30 corpus\source

:: 2. 重新标定（覆盖 §9.6 的 n=8 数字）
mayapy launch_baseline_scan.py --fps 30 --calibrate corpus\source

:: 3. 全量扩增（每条源 × {1.00, 0.85, 1.15} × {原/镜像}）
mayapy launch_baseline_scan.py --fps 30 --augment --out corpus\augmented corpus\source
```

跑完把三份报告回填到 `docs/01` §9.6：新的分布、新的阈值、门禁通过率。

### 预期检查点

- [ ] 各角色（foot/ball/toe_tip）分布是否与 §9.6 的形状一致
- [ ] 非对称片段（turn/strafe）镜像后是否被门禁接受
- [ ] Idle 的接触比是否接近 100%（两脚常贴地）
- [ ] Jump 是否走 unmeasurable 路径而不是被硬拒
- [ ] 新阈值下 §10.2 的 6 个 Standard Walk 变体是否仍然全过

## 6. 本地已有资产的排查结论

扫过本机现有 FBX：

| 位置 | 结论 |
|---|---|
| `D:\tool_code\*.fbx` | 2 条可用，已在语料里 |
| `D:\fbx\*.fbx` | 静态网格（无关键帧），采样器已自动跳过 |
| `D:\max_maya\**\*.fbx` | Bip001（3ds Max Biped）骨骼动画。骨骼命名不匹配 `FOOT_PATTERNS`，**暂不纳入语料**；将来可作为「非 Mixamo 骨骼」的鲁棒性测试样本 |
| `D:\locomotion\` | 无 FBX |

> Bip001 那批是真实项目资产。等语料主线跑通后，值得拿一条来测采样器对
> 非标准命名的容错——`find_foot_bones` 的 heuristic 在那套命名上会空手而归，
> 到时候需要 `feet=[...]` 手动指定，正好验证这条逃生通道好不好用。
