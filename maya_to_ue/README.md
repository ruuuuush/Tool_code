# Maya → UE Animation Pipeline

一套面向作品集的、从 Maya 到 Unreal Engine 的动画交付工具。覆盖
**检查 → 导出 → 桥接 → 导入** 全链路，强调 pipeline 工程化：
有校验、有约定、可复现、可扩展。

> 设计文档详见 [`docs/design.md`](docs/design.md)（v0.4 定稿）。

---

## 🚀 一键启动（推荐）

只装一次，以后点 Maya 工具架按钮就能打开工具：

1. 打开 Maya → **Script Editor** → 切到 **Python** 标签页。
2. 把仓库根目录下的 **`install_shelf_button.py`** 整个拖进脚本编辑器（或 File → Open 打开它）。
3. 点【运行】（Ctrl+Enter）。

装好后：顶部工具架多出「**MayaToUE**」页 → 「**动画交付**」按钮，点它即开工具。
> 安装脚本会把实际仓库目录永久写进 `userSetup.py`；重启 Maya 也有效，且可重复运行（不会重复装）。

> 不想装按钮、临时用一次：在 Script Editor 跑
> ```python
> import sys
> # 将此处改为你的实际仓库根目录
sys.path.insert(0, r"D:/your_path/maya_to_ue")
> import launch_maya_tool
> launch_maya_tool.show()
> ```

---

```
┌───────────────────────────┐      ┌──────────────┐      ┌───────────────────────────┐
│        Maya 端工具         │      │   桥接层      │      │        UE 端工具          │
│  UI (PySide6 / PySide2)   │ FBX  │  manifest    │ FBX  │  读 manifest              │
│  检查项 (注册式, 三级分级)  │─────►│  + 约定配置  │─────►│  FBX 自动导入              │
│  单 FBX 多 clip 导出       │ JSON │  (json/yaml) │ JSON │  按 clip 范围导入 AnimSequence │
└───────────────────────────┘      └──────────────┘      └───────────────────────────┘
```

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **注册式检查框架** | 新增检查项只需写一个类 + `@register_validator`，UI 自动识别 |
| **三级分级校验** | Error 阻断导出 / Warning 提示可继续 / Info 仅提示 |
| **28 个内置检查项** | 场景/骨骼/网格/动画/导出五类，覆盖真正会让 UE 导入失败的问题 |
| **不做破坏性自动修复** | 历史、冻结变换、骨骼缩放、蒙皮权重等高风险资产修改一律只提示 |
| **骨骼预设可切换** | 内置 UE Mannequin / Mixamo / 自定义，可自行扩展 |
| **manifest 解耦两端** | 单一事实源，记录源场景轴/单位、帧率、clips、路径等交付约定 |
| **单 FBX 多 clip 导出** | 一次 bake 整段；UE 端按 clip 区间直接导入 AnimSequence |
| **UE 全自动导入** | 读 manifest → 按 clip 帧区间导入 FBX → 配 root motion |
| **向导式三步界面** | 片段 → 导出设置 → 检查，一屏只做一件事；检查排最后，才拿得到它要判定的输入 |
| **场景信息实时** | 单位/朝上轴/帧率/时间轴自动跟随 Maya 场景，不必重跑检查才更新 |
| **Maya UI 兼容** | Maya 2024+ 使用 PySide6；Maya 2022 使用 PySide2 |
| **首次交付自动建骨架** | 新绑定不用手动导 UE：勾一个选项，导入时自动创建 Skeleton + SkeletalMesh；只随导出根骨架带出关联蒙皮模型 |
| **导入设置自动对齐** | 动画沿用目标骨架当初的轴/单位/缩放设置，不会出现动画躺倒或大小不符 |
| **Markdown 导出报告** | 每次导出生成可读的 `.md` 报告，作品集友好 |
| **交付产物一目了然** | 导出后逐项列出 FBX / manifest / 报告是否落地；缺 manifest 绝不报成功 |
| **交接不断链** | 导出完成即给出填好 manifest 路径的 UE 导入代码，一键复制 |
| **一键推送 UE** | 导出成功后自动把导入命令发给运行中的编辑器并回显结果；可关闭，连不上时安静退回手动方式 |
| **351 个单元测试** | 核心逻辑（schema/检查项/路径计算/导出策略/UI 导航与门禁/远程协议）在纯 Python 环境可测 |

---

## 目录结构

```
maya_to_ue/
├── README.md                      ← 本文件
├── docs/
│   └── design.md                  ← 设计文档（v0.4 定稿）
├── config/
│   ├── skeleton_presets.json      ← 3 个骨骼预设
│   ├── fbx_export_preset.json     ← FBX 导出参数
│   └── default_settings.json      ← 默认设置
├── bridge/                        ← manifest 解耦层
│   ├── schema.py                  ← 数据类 + 锁定校验
│   └── manifest.py                ← 读写 API
├── mtu_maya/                          ← Maya 端
│   ├── core/
│   │   ├── preset_loader.py       ← 预设数据类 + 加载器
│   │   ├── config.py              ← 统一配置访问
│   │   └── maya_utils.py          ← cmds 懒加载封装
│   ├── checks/                    ← 注册式检查框架
│   │   ├── registry.py            ← 注册表 + 运行器
│   │   ├── scene_checks.py        ← 4 项
│   │   ├── skeleton_checks.py     ← 6 项
│   │   ├── mesh_checks.py         ← 4 项
│   │   ├── anim_checks.py         ← 7 项
│   │   └── export_checks.py       ← 4 项
│   ├── export/
│   │   ├── fbx_exporter.py        ← 单 FBX 多 clip 导出
│   │   └── manifest_writer.py     ← manifest + 日志 + Markdown 报告
│   └── ui/
│       └── main_window.py         ← PySide6 / PySide2 主窗口
├── unreal/                        ← UE 端
│   ├── importer.py                ← FBX 按 clip 范围导入 AnimSequence
│   └── anim_builder.py            ← 可选后处理
├── tests/                         ← 299 个测试（全部可在纯 Python 跑）
│   ├── test_bridge_schema.py
│   ├── test_preset_loader.py
│   ├── test_checks.py
│   ├── test_export.py
│   ├── test_ui.py
│   └── test_ue_importer.py
├── launch_maya_tool.py            ← Maya 内启动器
├── launch_ue_importer.py          ← UE 内启动器
└── demo_e2e.py                    ← 无 Maya/UE 的端到端模拟
```

---

## 快速开始

### Maya 端

```python
# 在 Maya Script Editor (Python) 中：
import sys
# 将此处改为你的实际仓库根目录
sys.path.insert(0, r"D:/your_path/maya_to_ue")   # 仓库根目录

from mtu_maya.ui import show
show()
```

或运行仓库根的 `launch_maya_tool.py`。

#### 改完代码后重新打开

Maya 一个会话只加载一次 Python 模块，改了源码光关窗重开是没用的——拿到的还是旧代码。用：

```python
import sys
sys.path.insert(0, r"D:/your_path/maya_to_ue")
import launch_maya_tool
launch_maya_tool.reload_and_show()   # 清模块缓存 → 重新读盘 → 开窗
```

`launch_maya_tool.unload()` 只清缓存不开窗，需要时可单独调用。

UI 操作流程（顶部步骤条 · 一屏一步）：

**① 动画片段 → ② 导出设置 → ③ 检查**，点步骤条上的任意一步可随时跳转。

检查排在最后是有意的：它判定的正是前两步填的东西（片段帧范围、导出路径、UE 目标路径），先检查会让一批检查项无据可查。

1. 顶部选择骨骼预设（UE Mannequin / Mixamo / 自定义）
2. 第 ① 步在表格里填 clip 名 + 起止帧 + root motion 开关，或点【填充动画范围】——它读的是骨骼上实际的 K 帧范围（优先 hips），不是时间轴滑块的位置，所以下载来的 0–35 帧动作不会被填成默认的 1–120
3. 第 ② 步设置 FBX 保存目录/文件名、UE 目标路径、UE Skeleton 路径、覆盖策略
4. 前两步填好后，步骤条上对应的圆点会变成对勾——不进那一步也知道还差什么
5. 第 ③ 步点 **开始检查**，检查项列表显示 ✅/❌/⚠️；双击可定位到违规节点，仅对导出目录提供低风险自动修复
6. Error 清零后底部的 **导出 FBX + Manifest** 按钮亮起（有 Error 时点不动，旁边写明还差几项）
7. 导出生成 `xxx.fbx` + `xxx_manifest.json` + `xxx_export_report.md`；交付清单出现在步骤区下方（不属于任何一步，停在哪一步都看得见），逐项显示落地情况，缺 manifest 会明确标成「交付不完整」

### 跳过用不上的检查

每个检查项前有勾选框，默认全勾；分类行可整组开关。取消勾选的检查**根本不会执行**，列表里标成「已跳过」，统计写成 `19/26 通过 · 2 项未执行`。

跳过对所有级别开放，包括会阻断导出的 Error——只交动画不带模型时，「骨架实际尺寸」这类检查本来就无据可查。

代价是留痕，三处都写着：

- 界面：跳过项灰显、不显示通过图标，选中它会说明"本次没有执行"
- 导出前：弹一次确认，点名跳了几项、其中几项是 Error 级
- 交付物：manifest 的 `validation.skipped` 记下 id 与级别，导出报告单列「Skipped checks」一节，Error 级排最前

跳过只在本次会话有效，重开工具恢复全勾——它是临时决定，不该静静地活到下一个项目。

顶部的场景信息条（单位 / 朝上轴 / 帧率 / 时间轴）每秒自动跟随 Maya 场景刷新，不需要重跑检查。

> **Maya 端到此为止。** 导出只写 FBX 和 manifest，**不会在 UE 工程里创建任何资产**——那是另一个进程。
> ③ 里填的 UE 路径是写进 manifest 的目标声明，供 UE 侧导入时读取。
> 交付完成后，卡片下方会给出已填好本次 manifest 路径的 UE 代码：
> 默认会**自动推送**到正在运行的编辑器；也可点【**推送到 UE**】重推，或点【复制代码】手动粘贴。

### UE 端：把交付导进工程

#### 方式一：从 Maya 一键推送（推荐）

导出设置里的【**导出后推送**】默认开启：交付齐全时，导出结束就自动把导入命令发给正在运行的编辑器，不用点任何按钮。想手动控制就取消勾选，或改 `config/default_settings.json` 里的 `auto_push_after_export`（该值只作为界面初值，运行期以勾选状态为准）。

交付卡片上的【推送到 UE】始终保留，用来重推或在关掉自动推送时手动触发；导入结果回显在 Maya 里，不用切窗口。推送成功后卡片会回读 manifest，逐项列出 UE 里实际创建的资产（N 个 AnimSequence、首次交付的 Skeleton/SkeletalMesh、按策略跳过的片段）；同时 UE 的 Content Browser 会自动定位选中这批新资产。

前置条件（只配一次）：

1. UE 里 **编辑 → 项目设置 → 插件 → Python** → 勾选「**启用远程执行**」（英文 `Enable Remote Execution`），重启编辑器
2. 编辑器保持打开状态
3. Maya 与 UE 在**同一台机器**上

> 走的是 UE 官方的 Python Remote Execution（UDP 多播发现 + 编辑器反向 TCP 连接）。
> 只支持同机：多播出不了本机，跨机器请用下面的手动方式。
> 任何一环不满足，界面会说明原因，复制代码那条路始终可用。

#### 方式二：手动粘贴

在 UE 编辑器 → **Output Log** → 切到 **Python**，粘贴交付卡片给出的代码（等价于）：

```python
import sys, importlib
sys.path.insert(0, r"D:/your_path/maya_to_ue")
import launch_ue_importer
importlib.reload(launch_ue_importer)   # 编辑器是长驻进程，保证跑最新代码
outcome = launch_ue_importer.run(r"D:/exports/hero_walk_manifest.json")
launch_ue_importer.report(outcome)
```

首次在某个引擎版本上使用，先跑一次环境自检：

```python
launch_ue_importer.check()
```

它会报告引擎版本、所需 API 是否齐全、Interchange FBX 导入的开关状态。出现 `PROBLEM:` 先解决它再导入。

#### 新绑定的首次交付

UE 里还没有这套骨架时，不需要先手动导一遍：

1. 勾选 ③ 里的 **同时导出模型**
2. **UE Skeleton 路径** 留空（或填希望生成的路径）
3. 如果角色按【米】制作，把 **UE 导入缩放** 填成对应倍数（检查项会给建议值）
4. 导出后在 UE 点「导入动画…」

工具会先用同一个 FBX 建出 `SkeletalMesh` + `Skeleton`，再把各段动画绑上去，并把实际生成的骨架路径写回 manifest。首次交付只会带出与③所选骨架关联的蒙皮模型；之后同一套绑定的动画就不用再勾这个选项。

> **关于参考姿势**：UE 通常优先使用 FBX Bind Pose 创建 Skeleton Reference Pose；只有 FBX 缺 Bind Pose 或启用 `Use T0 As Ref Pose` 时，动画首帧才可能污染参考姿势。`skeleton.bind_pose` 只做起始姿势提示，首次交付后仍应在 UE 验证生成的 Skeleton。

### UE 端

**一键安装菜单（推荐，只装一次）**

Window → Output Log，底部下拉切到 **Python**，粘贴（路径改成你的仓库目录）：

```python
exec(open(r"D:/tool_code/maya_to_ue/install_ue_menu.py").read())
```

主菜单栏会出现「**Maya→UE**」，包含三个按钮：

| 按钮 | 作用 |
|------|------|
| 导入动画… | 选 manifest 文件，按片段导入 AnimSequence |
| 环境自检 | 确认当前引擎版本的 API 是否齐全 |
| 重新载入工具 | 改完 Python 代码后刷新，不用重启 UE |

想开机自动加载：把仓库目录加进 `Project Settings → Plugins → Python → Startup Scripts`。

**或者用 Python 直接调用**

```python
import sys, importlib
sys.path.insert(0, r"D:/your_path/maya_to_ue")

# 注意：本仓库的包名叫 `unreal`，与 UE 自带模块同名。
# launch_ue_importer 已经处理了这个冲突，直接用它：
import launch_ue_importer
importlib.reload(launch_ue_importer)   # 编辑器是长驻进程，保证跑最新代码
launch_ue_importer.check()                       # 先自检
outcome = launch_ue_importer.run(r"D:/exports/hero_manifest.json")
launch_ue_importer.report(outcome)
```

工具会：
1. 自检当前引擎版本，并在 UE 5.5+ 上自动切回 legacy FBX 路径（Interchange 会忽略帧范围和目标骨架设置）
2. 读取目标 Skeleton 当初的导入设置（轴转换/单位/缩放），让动画与骨架严格对齐
3. 在 Content Browser 创建目标文件夹
4. 对 manifest 每个 clip 按 start/end 帧范围导入 FBX
5. 生成每个 clip 对应的 AnimSequence，并按 clip 的 root_motion 字段配置 root motion
6. 把导入结果回写到 manifest 的 `result` 字段

### 验证：无 Maya/UE 也能跑

测试与 demo 只依赖标准库 + PySide，任何 Python 3.7+ 解释器都能跑。
本机没装独立 Python 时，直接用 Maya 自带的 `mayapy`：

```bash
cd D:/your_path/maya_to_ue

# 用 Maya 自带解释器（Maya 2022 为例）
D:/Maya2022/bin/mayapy.exe -m unittest discover -s tests
D:/Maya2022/bin/mayapy.exe demo_e2e.py

# 或者用你自己的 Python 3
python -m unittest discover -s tests          # 跑全部测试
python demo_e2e.py                            # 端到端模拟（生成 manifest + 报告 + UE 路径预测）
```

---

## 设计亮点（作品集可重点讲）

### 1. 检查逻辑与场景读取解耦

每个 validator 的 `check()` 只接收一个 `CheckContext`，**不直接调 `maya.cmds`**。这意味着所有检查项的逻辑都能在没有 Maya 的纯 Python 环境下单元测试——这是 `tests/test_checks.py` 能在 0.01 秒内跑完的原因。

只有 `fix()` 在修改场景时才懒加载 `maya.cmds`。

### 1.1 自动修复的边界

自动修复只做**低风险、可逆**的操作：创建导出目录。

刻意**不做**的操作：

| 不自动做 | 原因 |
|----------|------|
| 删除模型历史 | 蒙皮/BlendShape 就是"历史"，删了等于毁绑定 |
| 冻结模型变换 | 冻结已蒙皮模型会破坏 bind pose |
| 修改场景朝上轴 | 会让整个已有场景的角色躺倒 |
| 修改骨骼缩放 / `segmentScaleCompensate` / 蒙皮权重 | 会改变绑定、权重或已有动画的结果 |

这类问题只提示、只定位，改不改由动画师决定。工具不该在别人的资产上做不可逆操作。

### 2. manifest 作为单一事实源

约定（源场景轴、单位、帧率、是否转换）不写在代码里，而是记录并校验在 `bridge/schema.py` 的 `Manifest.validate()` 里——任何一端写错配置都会被 schema 校验拦截。两端通过 manifest 解耦，可独立开发、独立测试。

### 3. 注册式可扩展

加一个检查项：

```python
@register_validator
class MyCheck(BaseValidator):
    id = "scene.my_check"
    category = "scene"
    level = "warning"
    auto_fixable = True
    description = "My custom check"

    def check(self, ctx):
        return CheckResult(
            check_id=self.id, category=self.category, level=self.level,
            passed=..., message="...",
        )

    def fix(self, ctx):
        ...
```

UI 自动识别、自动渲染、自动统计——零 UI 改动。

### 4. 三级分级与导出阻断

`RunReport.can_export()` 一行判断：有 Error 就阻断导出。这个规则在 schema、检查框架、UI 三处一致，不会因为漏判而导出不合规资产。

### 5. 跨应用工程化

不是「一个 Maya 脚本 + 一个 UE 脚本」，而是一套有 schema、有解耦层、有测试、有报告的 pipeline。两端可以独立演进，manifest 是契约。

---

## 当前版本限制 / v2 路线图

| 项 | 现状 | v2 计划 |
|----|------|---------|
| Retarget | v1 跳过 | 加 IK Rig + IK Retargeter 自动生成（人形） |
| Mesh 导出 | 首次交付支持当前骨架关联的蒙皮模型 | 加 LOD 配置 |
| AnimBP | 不生成 | 按 clip 自动生成 AnimBP + State Machine |
| 骨骼映射验证 | 仅命名 regex | 加 UE Mannequin 骨骼完整映射检查 |
| manifest 版本迁移 | 仅支持 1.0 | 加 `migrate()` 支持未来 schema 升级 |
| Editor Utility Widget | 仅 Python | 加 UE 内 UI（EUW） |

---

## 技术栈

- **Maya**: 2022+，Python 3.7+，Maya 2022 使用 PySide2，Maya 2024+ 使用 PySide6；保留源场景轴，UE 导入执行 FBX 坐标转换
- **UE**: 5.3+，Python 3.11
- **配置**: JSON（零依赖）/ YAML（可选 PyYAML）
- **测试**: 标准库 `unittest`，Python 3.7+ 即可运行；测试总数随新增覆盖增长

## 运行测试

```bash
# 独立 Python 3
python -m unittest discover -s tests -v

# 或 Maya 自带解释器
D:/Maya2022/bin/mayapy.exe -m unittest discover -s tests -v
```
