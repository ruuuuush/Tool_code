## Why

步骤顺序是倒的。第一步是「检查」，但 `_build_context_from_ui()`（`main_window.py:1159-1176`）构造检查上下文时读的全是后两步的输入：`clips` 来自片段表，`fbx_path` / `ue_content_root` / `ue_skeleton_path` / `skeleton_root` 来自导出面板。

结果是 28 个检查项里有 7 个（`export.path_valid`、`export.ue_path_valid`、`export.naming_legal`、`export.skeleton_root_set`、`anim.clip_ranges_valid`、`anim.clip_overlap`、`anim.keys_in_clip_range`）在第一步根本没有输入可查。用户一进来点「开始检查」必然满屏红，只能跑到后面填完再折返重跑。检查是终检，不是首检——现在的流程逼着人先考试后复习。

另一件事：场景信息栏（单位 / 朝上轴 / 帧率 / 时间轴）不是实时的。`_refresh_scene_info_safe()` 只在打开工具和跑完检查后被调用，用户在 Maya 里改了单位或帧率，工具上那行字纹丝不动，得重跑检查才更新——而它显示的恰恰是「检查会拿什么去判定」的依据。

## What Changes

- **步骤顺序改为 ① 动画片段 → ② 导出设置 → ③ 检查**：检查移到最后，拿到完整输入再体检。
- **导出动作跟检查同屏**：主操作按钮留在第三步，检查通过即可直接导出，不必再切页。
- **门禁语义随之调整**：前两步不再显示「导出被卡住」的理由（那时还没检查，说了也无意义）；第三步未跑检查时提示去跑，有 Error 时说明还差几项。
- **步骤条完成态覆盖前两步**：填了片段、填了必要路径，对应步骤标为已完成，让「还差什么」在顶部可见。
- **场景信息栏定时自动刷新**：约每秒读一次场景，值变了才更新文字；窗口关闭时停掉定时器。
- **场景信息栏加时间戳/来源提示**：让用户知道这行字是活的。

## Capabilities

### New Capabilities
<!-- 无新增能力，都是既有 export-ui 的行为调整 -->

### Modified Capabilities
- `export-ui`: 「三步向导式导航」的步骤定义与顺序改变；「检查结果作为导出门禁并可见」的提示时机随之调整；新增场景信息实时性要求。

## Impact

- `mtu_maya/ui/main_window.py`：`_build_ui()` 中三页的装配顺序；`_go_to_step()` 的索引语义；`_update_gate()` 判断「是否在检查步」的条件；新增场景信息定时器与前两步完成度判定
- `mtu_maya/ui/strings.py`：`STEP_TITLES` 顺序调整，门禁文案措辞随之改动
- `tests/test_ui.py`：导航与门禁测试中所有硬编码的步骤索引需要跟着改；新增前两步完成态与定时刷新的测试
- `README.md`：操作流程描述
- 检查项、导出器、manifest 逻辑不受影响
