# Maya → UE 动画全流程工具 · 设计思维文档（v0.4 final）

> 状态：**定稿，进入实现阶段**
> 用途：作品集项目，体现 pipeline 工程化能力
> 维护：与需求方共同迭代

## 0. 已确认的关键决策（v0.4 全部锁定）

| 维度 | 决策 |
|------|------|
| UE 端 | **全自动 Python 导入**：读 manifest → 导入 FBX → 生成 AnimSequence |
| 骨骼类型 | **两者都支持**：人形 + 自定义，通过约定配置文件区分 |
| 软件版本 | **Maya 2022+ / UE 5.3+**：Maya 2022 用 PySide2，Maya 2024+ 用 PySide6，UE 用 Python 3.11 |
| 核心展示点 | **全选**：检查项系统 + 跨应用桥接 + 批量动画导出 + UE 自动生成 |
| 骨骼命名 | **多预设可切换**：UE Mannequin / Mixamo / 自定义，每预设含命名正则 + 骨骼映射表 |
| Clip 划分 | **UI 表格手填**：用户在导出 UI 表格中填 clip 名 + 起止帧，工具据此 bake + 导出 |
| 检查分级 | **三级 Error/Warning/Info**：Error 阻断导出，Warning 提示可继续，Info 仅提示 |
| 轴向/单位 | **保留源场景轴/单位，不自动修改坐标**；FBX 导出不 Convert Axis，UE 导入执行坐标/单位转换 |
| FBX 策略 | **单 FBX 多 clip 区间导入**：导出 1 个含全动画的 FBX，UE 端按 clip 帧范围直接导入 AnimSequence |
| Retarget | **v1 跳过**：先把闭环跑通，IK Rig retarget 作为 v2 加分项 |
| 导出报告 | **Markdown 报告**：导出后生成 `.md` 报告含检查结果 + clip 列表 + 路径 |
| 代码顺序 | **自底向上**：bridge → config → checks → export → UI → UE 端 |

十二项决策全部锁定，开始实现。

---

## 1. 项目定位与目标

做一个连接 Maya 与 Unreal Engine 的动画交付工具，覆盖「检查 → 导出 → 桥接 → 导入 → 生成」全链路。

- **Maya 端**：提供 UI + 自动化检查项，确保资产可被 UE 正确接收
- **桥接层**：用配置/清单文件解耦两端，避免硬编码
- **UE 端**：自动导入 FBX 并生成 AnimSequence 等资产

**作品集价值点**：不只是「一个 Maya 脚本」，而是一套有校验、有约定、可复现、可扩展的小型 pipeline。

---

## 2. 整体架构

```
┌───────────────────────────┐      ┌──────────────┐      ┌───────────────────────────┐
│        Maya 端工具         │      │   桥接层      │      │        UE 端工具          │
│  ┌─────────────────────┐  │      │              │      │  ┌─────────────────────┐  │
│  │  UI (PySide)        │  │ FBX  │  manifest    │ FBX  │  │  UI / CLI           │  │
│  │  检查项 (validators) │──┼─────►│  + 约定配置  │─────►│  │  读取 manifest       │  │
│  │  导出器 (exporter)  │  │ JSON │  (json/yaml) │ JSON │  │  FBX 导入            │  │
│  │  配置 (config)      │──┼─────►│              │─────►│  │  生成 AnimSequence   │  │
│  └─────────────────────┘  │      │              │      │  │  设置 root motion 等 │  │
└───────────────────────────┘      └──────────────┘      └───────────────────────────┘
```

三部分通过「清单文件 + FBX」解耦，任一端可独立运行/测试。

---

## 3. 核心流程

1. **准备**：打开 Maya 场景，确认角色/动画已就绪
2. **检查**：UI 触发 validators，逐项扫描，红/绿显示，可定位修复
3. **导出**：检查通过后，按预设 bake 动画、导出 FBX，并写出 manifest
4. **桥接**：manifest 描述 clips、帧率、路径、UE 目标目录、root motion 等
5. **导入**：UE 端读 manifest，调用 `unreal` 模块批量导入 FBX
6. **生成**：自动生成/配置 AnimSequence，可选创建 AnimBP、预览等

---

## 4. Maya 端设计

### 4.1 UI 结构（PySide6 / PySide2，v0.3 细化）

```
┌─────────────────────────────────────────────────────────────┐
│  Maya→UE Animation Pipeline                  [预设▼] [设置] │  ← 顶栏：骨架预设切换 + 全局设置
├─────────────────────────────────────────────────────────────┤
│ 场景信息：hero_anim.ma | 源轴保留 | cm | 30fps | 1-120          │
├──────────────────────────┬──────────────────────────────────┤
│ 检查项 (5/12 通过)        │ 选中项详情                        │
│ ▼ 场景 (4/4)              │ ┌──────────────────────────────┐ │
│   ✅ scene.unit           │ │ skeleton.scale               │ │
│   ✅ scene.up_axis        │ │ 级别: Warning  可修复         │ │
│   ✅ scene.fps            │ │ 检查: 所有 joint scale=1      │ │
│   ⚠️ scene.timeline_range │ │ 结果: joint 'spine_03'=1.02  │ │
│ ▼ 骨骼 (3/4)              │ │       joint 'arm_l'=1.01     │ │
│   ✅ skeleton.root_exists │ │                              │ │
│   ✅ skeleton.naming      │ │ [修复选中] [修复所有 Warning] │ │
│   ⚠️ skeleton.scale       │ └──────────────────────────────┘ │
│   ℹ️ skeleton.orient_axis │                                  │
│ ▼ 网格 (4/4)              │                                  │
│ ▼ 动画 (4/4)              │                                  │
│ ▼ 导出 (4/4)              │                                  │
├──────────────────────────┴──────────────────────────────────┤
│ Clip 划分表格 (UI 手填)                                     │
│ ┌──────────┬───────┬───────┬────────────┬──────┐            │
│ │ Clip 名  │ Start │ End   │ Root Motion│ 操作 │            │
│ ├──────────┼───────┼───────┼────────────┼──────┤            │
│ │ idle     │ 1     │ 30    │   ☐        │ 🗑️   │            │
│ │ walk     │ 31    │ 90    │   ☑        │ 🗑️   │            │
│ │ run      │ 91    │ 120   │   ☑        │ 🗑️   │            │
│ └──────────┴───────┴───────┴────────────┴──────┘            │
│ [+ 添加 Clip]  [从时间轴填充]                                │
├─────────────────────────────────────────────────────────────┤
│ 导出设置：FBX 路径 [__________] [浏览]                       │
│           UE 目标 [/Game/Animations/Hero]  覆盖策略 [rename▼]│
│           骨架根 [root        ▼]                             │
├─────────────────────────────────────────────────────────────┤
│ [运行检查]  [导出 FBX+Manifest]  [查看日志]    进度: ████░░ │
└─────────────────────────────────────────────────────────────┘
```

**交互要点**
- 「运行检查」全量跑 validators，更新状态图标
- 双击检查项 → 选中相关节点（如双击 skeleton.scale → 选中违规 joint）
- Error 存在时「导出」按钮禁用，悬浮提示「请先修复 Error」
- Warning 存在时点击「导出」弹确认框「仍有 N 个 Warning，是否继续？」
- Clip 表格的「从时间轴填充」按钮：用当前时间轴 start/end 预填一行
- 导出后 UI 显示 manifest 路径，并展示其中 validation 摘要

### 4.2 检查项（核心亮点，v0.3 细化）

采用**注册式框架**：每个检查项是一个类，实现 `check()` / `fix()`（可选）/ `level`，自动收集到注册表，UI 按分类渲染。

#### 严重度分级与阻断规则
| 级别 | 含义 | 阻断导出 |
|------|------|----------|
| Error | 必须修复才能导出 | ✅ 是 |
| Warning | 建议修复，可强制继续 | ❌ 否 |
| Info | 仅提示，不影响 | ❌ 否 |

> 「导出」按钮在存在未修复 Error 时禁用；存在 Warning 时弹确认对话框。

#### 检查项清单（v0.3）

**场景层（scene）**
| ID | 检查 | 级别 | 可自动修复 |
|----|------|------|------------|
| scene.unit | 工作单位 = cm | Error | 是（设为 cm） |
| scene.up_axis | Up axis = Z | Error | 是（设为 Z） |
| scene.fps | 帧率 = 目标值 | Error | 是（设为目标） |
| scene.timeline_range | 时间轴范围非空合理 | Warning | 否 |

**骨骼层（skeleton）**
| ID | 检查 | 级别 | 可自动修复 |
|----|------|------|------------|
| skeleton.root_exists | 存在 root 且在原点 | Error | 否 |
| skeleton.naming | 命名符合当前预设正则 | Warning | 否 |
| skeleton.scale | 所有 joint scale = 1（容差 0.001） | Warning | 是（freeze） |
| skeleton.orient_axis | 关节 orient 轴向一致 | Info | 否 |

**网格层（mesh，仅当含 mesh 时）**
| ID | 检查 | 级别 | 可自动修复 |
|----|------|------|------------|
| mesh.history | 历史已删除 | Warning | 是（delete history） |
| mesh.transforms | 变换已冻结 | Warning | 是（freeze transform） |
| mesh.uv | UV 存在且无严重重叠 | Warning | 否 |
| mesh.skin_weight | skinCluster 权重归一化 | Warning | 是（normalize） |

**动画层（anim）**
| ID | 检查 | 级别 | 可自动修复 |
|----|------|------|------------|
| anim.curves_on_expected | 仅预期节点带动画曲线 | Info | 否 |
| anim.stray_layers | 无游离动画层 | Info | 否 |
| anim.clip_ranges_valid | 表格填的 clip 范围合法（start≤end，在时间轴内） | Error | 否 |
| anim.root_motion_match | root motion 开关与 clip 类型匹配（如 walk 应开） | Info | 否 |

**导出层（export）**
| ID | 检查 | 级别 | 可自动修复 |
|----|------|------|------------|
| export.fbx_plugin | FBX 插件已加载 | Error | 否 |
| export.path_valid | 导出路径有效可写 | Error | 否 |
| export.naming_legal | clip 名无非法字符（`/\\:*?"<>|`） | Error | 否 |
| export.skeleton_root_set | 已选 skeleton root | Error | 否 |

#### 检查项注册接口（伪代码）
```python
class Validator(Protocol):
    id: str
    category: str          # scene/skeleton/mesh/anim/export
    level: Literal["error", "warning", "info"]
    auto_fixable: bool
    def check(self, ctx) -> CheckResult: ...
    def fix(self, ctx) -> None: ...  # 可选

# 装饰器注册
@register_validator
class SceneUnitValidator(Validator): ...
```

UI 通过 `registry.all()` 按分类分组渲染，每项显示状态图标 + 双击定位 + 修复按钮（若 auto_fixable）。

### 4.3 导出模块
- FBX 预设可配置（bake、resample、约束、轴、单位）
- 支持单段或按 clip 范围批量导出
- 导出同时写 `manifest.json`

---

## 5. UE 端设计（方案 A：全自动 Python 导入，已锁定）

### 5.1 执行流程
1. 读取 Maya 导出的 `manifest.json`
2. 校验 FBX 路径、目标 Content 路径
3. 用 `unreal.AssetTools` + `FbxImportUI` 导入 FBX
4. 对每个 manifest clip 使用其帧范围直接导入 AnimSequence
5. 根据 `root_motion` 配置启用/关闭 Root Motion
6. 按约定创建文件夹结构，命名归一化
7. 写入导入日志 `manifest.json` 反馈结果

### 5.2 关键技术点
- **FBX 导入参数**：通过 `unreal.FbxImportUI` 配置（导入为 Skeleton/SkeletalMesh/Animation）
- **多 clip 导入**：每个 clip 用 `FbxAnimSequenceImportData` 的帧范围直接导入，不导入整段后再用 Python 切片
- **Root Motion**：导入时 `unreal.FbxAnimSequenceImportData.bImportMesh` / `bConvertScene` 等开关
- **人形 retarget（可选）**：人形资产走 IK Rig + IK Retargeter，自定义跳过
- **资产路径**：`/Game/Animations/<Character>/<Clip>` 自动建包

### 5.3 入口方式
- UE 编辑器内：Output Log 跑 Python，或做成 Editor Utility Widget 提供按钮
- CLI：`unreal.EditorAssetLibrary` + 命令行脚本（适合 CI/批量）

### 5.4 错误与回滚
- 导入失败：捕获异常，记录到 manifest 的 `result` 字段，不中断后续 clip
- 重名处理：可选覆盖/跳过/重命名（配置项）

---

## 6. 桥接层 manifest（v0.3 schema）

```json
{
  "version": "1.0",
  "export_time": "2026-07-20T12:00:00",
  "tool_version": "0.1.0",

  "source": {
    "maya_scene": "hero_anim.ma",
    "maya_version": "2024",
    "preset": "ue_mannequin",
    "skeleton_root": "root"
  },

  "convention": {
    "up_axis": "z",
    "unit": "cm",
    "frame_rate": 30,
    "axis_conversion": false
  },

  "clips": [
    {"name": "idle", "start": 1, "end": 30,  "root_motion": false},
    {"name": "walk", "start": 31, "end": 90, "root_motion": true}
  ],

  "fbx_path": "./exports/hero_anim.fbx",

  "ue_destination": {
    "content_root": "/Game/Animations/Hero",
    "skeleton_path": "/Game/Animations/Hero/Hero_Skeleton",
    "overwrite_policy": "rename"
  },

  "validation": {
    "status": "passed",
    "errors": 0,
    "warnings": 1,
    "infos": 0,
    "results": [
      {"check": "scene.unit", "level": "error",   "passed": true, "message": "单位 = cm"},
      {"check": "scene.up_axis", "level": "info", "passed": true, "message": "Scene up axis preserved"},
      {"check": "skeleton.scale", "level": "warning", "passed": false, "message": "joint 'spine_03' scale = 1.02", "auto_fixable": true}
    ]
  },

  "result": {
    "status": "pending",
    "imported_clips": [],
    "errors": []
  }
}
```

**字段说明**
- `convention.axis_conversion: false` —— Maya 不执行轴转换；`convention.up_axis` 记录源场景实际轴向，UE 导入负责转换
- `clips[].root_motion` —— 每 clip 独立开关，因为 idle 通常不要 root motion，walk/run 要
- `ue_destination.overwrite_policy` —— `overwrite` / `skip` / `rename`（默认 rename 避免误删）
- `validation` —— Maya 端检查结果原样写入，UE 端可二次校验
- `result` —— UE 端回写，Maya UI 可读取展示导入结果

---

## 7. 骨骼预设配置（v0.3 新增）

「两者都支持 + 多预设可切换」通过配置文件实现，不硬编码骨骼名。

### 7.1 预设文件结构（`config/skeleton_presets.yaml`）

```yaml
presets:
  ue_mannequin:
    display_name: "UE Mannequin"
    skeleton_type: "humanoid"
    root_bone: "root"
    naming:
      left_suffix: "_l"
      right_suffix: "_r"
      naming_regex: "^[a-z]+(_[a-z]+)*(_l|_r)?$"
    # UE Mannequin 标准骨骼名，用于人形 retarget 映射
    bone_map:
      pelvis: "pelvis"
      spine_01: "spine_01"
      # ... 完整 UE Mannequin 骨骼
      thigh_l: "thigh_l"
      calf_l: "calf_l"
      foot_l: "foot_l"
    required_bones:
      - "root"
      - "pelvis"
      - "spine_01"

  mixamo:
    display_name: "Mixamo"
    skeleton_type: "humanoid"
    root_bone: "Hips"
    naming:
      left_suffix: "Left"
      right_suffix: "Right"
      naming_regex: "^[A-Z][a-zA-Z]*(Left|Right)?$"
    bone_map:
      pelvis: "Hips"
      spine_01: "Spine"
      thigh_l: "LeftUpLeg"
      # ... Mixamo → UE 映射
    required_bones:
      - "Hips"
      - "Spine"

  custom:
    display_name: "自定义骨架"
    skeleton_type: "custom"
    root_bone: ""           # 用户填
    naming:
      left_suffix: ""
      right_suffix: ""
      naming_regex: ""
    bone_map: {}            # 无 retarget 映射
    required_bones: []      # 仅校验 root
```

### 7.2 预设的使用
- UI 顶栏下拉切换预设，切换后重跑相关检查项
- `skeleton.naming` 检查项用预设的 `naming_regex` 校验
- `skeleton.root_exists` 用预设的 `root_bone`
- UE 端：若 `skeleton_type == "humanoid"` 走 IK Rig retarget 流程；`custom` 跳过

### 7.3 预设扩展性
- 用户可在 `config/skeleton_presets.yaml` 添加自己的预设
- 工具启动时扫描配置目录加载所有预设
- 作品集可展示「3 个内置预设 + 自定义扩展」体现可配置性

---

## 8. 建议目录结构（v0.3 细化）

```
maya_to_ue/
├── README.md
├── docs/
│   └── design.md                  ← 本文档
├── config/
│   ├── skeleton_presets.yaml      ← 骨骼预设（UE Mannequin/Mixamo/自定义）
│   ├── fbx_export_preset.json     ← FBX 导出参数预设
│   └── default_settings.yaml      ← 默认设置（帧率、路径、覆盖策略）
├── mtu_maya/
│   ├── __init__.py
│   ├── main.py                    ← UI 入口（启动函数）
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py         ← 主窗口
│   │   ├── check_widget.py        ← 检查项列表组件
│   │   ├── clip_table.py          ← Clip 表格组件
│   │   └── export_panel.py        ← 导出设置面板
│   ├── checks/                    ← 检查项（注册式）
│   │   ├── __init__.py
│   │   ├── registry.py            ← 注册表 + 基类
│   │   ├── scene_checks.py        ← scene.* 检查项
│   │   ├── skeleton_checks.py     ← skeleton.* 检查项
│   │   ├── mesh_checks.py         ← mesh.* 检查项
│   │   ├── anim_checks.py         ← anim.* 检查项
│   │   └── export_checks.py       ← export.* 检查项
│   ├── export/
│   │   ├── __init__.py
│   │   ├── fbx_exporter.py        ← FBX 导出逻辑
│   │   ├── manifest_writer.py     ← 写 manifest.json
│   │   └── preset_loader.py       ← 加载 FBX 预设
│   └── core/
│       ├── __init__.py
│       ├── maya_utils.py          ← cmds 封装
│       └── config.py              ← 读取 config/*.yaml
├── bridge/
│   ├── __init__.py
│   ├── schema.py                  ← manifest 数据类（dataclass）
│   └── manifest.py                ← 读写 manifest 的 API
├── unreal/
│   ├── __init__.py
│   ├── importer.py                ← FBX 导入（unreal.AssetTools）
│   ├── anim_builder.py            ← AnimSequence 后处理
│   ├── retarget.py                ← 人形 IK Rig retarget（可选）
│   └── config.py
└── tests/
    ├── test_bridge_schema.py
    ├── test_checks.py
    └── test_manifest.py
```

每个 Maya 检查项类放在 `checks/` 下按分类分文件，新增检查项只需写类 + `@register_validator`，UI 自动识别——这就是注册式框架的价值，也是作品集要重点讲的设计点。

---

## 8. 技术选型（待版本确认后定）
- Maya：Python 3（Maya 2022+）+ PySide2/PySide6 + maya.cmds
- UE：UE5 + Python + `unreal` 模块
- 配置：JSON（无额外依赖）或 YAML

---

## 9. 作品集加分项
- 检查项可配置、可扩展（注册式 + 三级分级 + 自动修复）
- manifest schema 清晰，两端解耦，UE 端可二次校验
- 骨骼预设外置（3 内置 + 可扩展），体现「不硬编码约定」
- 批量 clip 导出 + 每 clip 独立 root motion 配置
- UE 端全自动按 clip 帧范围导入 AnimSequence
- 完整 README + 流程图 + 截图 + 使用说明
- 错误处理、日志、导出报告
- （可选）单元测试覆盖 bridge 层和检查项

---

## 10. 实现路线图（v0.4，自底向上）

按依赖顺序实现，每层可独立测试：

| 阶段 | 模块 | 产出 | 可测试点 |
|------|------|------|----------|
| 1 | `bridge/schema.py` | manifest 数据类（dataclass） | 序列化/反序列化测试 |
| 2 | `bridge/manifest.py` | manifest 读写 API | 读写往返测试 |
| 3 | `config/skeleton_presets.yaml` + `mtu_maya/core/config.py` | 预设加载 | 预设解析测试 |
| 4 | `mtu_maya/checks/registry.py` + 5 类检查项 | 注册式检查框架 | 各检查项单测 |
| 5 | `mtu_maya/export/fbx_exporter.py` + `manifest_writer.py` | 单 FBX 多 clip 导出 | 干跑模式测试 |
| 6 | `mtu_maya/ui/*` | PySide6 / PySide2 主界面 | 手动验证 |
| 7 | `unreal/importer.py` + `anim_builder.py` | UE 全自动导入 | UE 内验证 |
| 8 | 导出报告 + 日志 + README | 收尾 | — |

### 10.1 ✅ 已解决（v0.4 全部）
- [x] 骨骼命名约定 → 多预设可切换（见 §7）
- [x] Clip 划分方式 → UI 表格手填
- [x] 检查分级 → 三级 Error/Warning/Info
- [x] 轴向/单位 → 保留源场景轴/单位，UE 导入时转换
- [x] FBX 策略 → 单 FBX 多 clip 区间导入
- [x] Retarget → v1 跳过
- [x] 导出报告 → Markdown
- [x] 代码顺序 → 自底向上

### 10.2 留给代码阶段的小决策（实现时定，不阻塞）
- Clip 表格 root motion 默认值推断（walk/run 默认开，idle 默认关）
- 进度条粒度（检查/导出各一个粗粒度进度）
- manifest 版本兼容策略（先只支持 1.0，未来加迁移函数）
- FBX 导出预设精确参数（bake/resample/约束/变形器开哪些，先用业界标准值）

---

## 11. 文档版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-07-20 | 初版草案 |
| v0.2 | 2026-07-20 | 锁定 4 项关键决策（UE 端/骨骼/版本/展示点） |
| v0.3 | 2026-07-20 | 锁定 4 项细节（命名预设/Clip 划分/检查分级/轴向单位）+ 细化各章节 |
| v0.4 | 2026-07-20 | **定稿**：锁定 FBX 策略/Retarget/报告/代码顺序，进入实现 |
