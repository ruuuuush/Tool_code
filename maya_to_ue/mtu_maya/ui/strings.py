"""mtu_maya.ui.strings

Central Chinese UI text for the pipeline tool.

Keeping every user-facing string here makes the UI copy easy to review and
leaves the door open for a future EN/ZH toggle.
"""

# Window / app
WINDOW_TITLE = "Maya → UE 动画管线工具"
MENU_TOOLS = "工具(&T)"
MENU_OPEN_EXPORT_FOLDER = "打开导出目录"

# Toolbar
SKELETON_PRESET = "骨架预设："
RELOAD_CONFIG = "重载配置"

# Guided steps header
# Wizard steps — the step bar is the ONLY place these names appear.
# Order matters: checks come LAST because they judge what the first two
# steps produce (clip ranges, export paths). Checking first would leave a
# third of the validators with nothing to look at.
# No hint/subtitle strings on purpose: the UI explains itself through
# placeholders and state text, not through captions pinned next to widgets.
STEP_TITLES = ("动画片段", "导出设置", "检查")

# Navigation
NAV_PREV = "上一步"
NAV_NEXT = "下一步"

# Export gate
GATE_NOT_RUN = "点【开始检查】跑一遍，通过后才能导出"
GATE_BLOCKED = "还有 {n} 项必须修，修完再跑一次检查"
GATE_READY = "检查已通过，可以导出"
GATE_READY_WARN = "检查通过（{n} 项警告可忽略），可以导出"

# Scene info bar
SCENE_NOT_READ = "（尚未读取场景）"
MAYA_UNAVAILABLE = "未检测到 Maya —— 当前在 Maya 之外运行。"
SCENE_READ_FAILED = "无法读取场景：{exc}"
SCENE_INFO_FMT = "场景：{name}　|　{up} 轴向上　|　单位 {unit}　|　{fps:g} fps　|　时间轴 {start}–{end}"

# Check list panel
CHECKS_NOT_RUN = "（未运行）"
CHECKS_COUNT = "{n} 项"
CHECKS_SUMMARY_FMT = "{passed}/{total} 通过"
RUN_CHECKS = "开始检查"
FIX_SELECTED = "修复选中"
FIX_ALL_WARNINGS = "一键修复所有警告"
COL_CHECK = "检查"
COL_STATUS = "状态"
STATUS_OK = "通过"
STATUS_FAIL = "未通过"
TOOLTIP_RESULT_FMT = "{level}：{msg}"

# 跳过：取消勾选即不执行该检查。这是给导出门禁开的口子，
# 所以每一处呈现都得说清"没跑"，而不是含糊成"没问题"。
STATUS_SKIPPED = "已跳过"
SKIPPED_ICON = "已跳过"
CHECKS_SUMMARY_SKIPPED_FMT = "{passed}/{total} 通过 · {skipped} 项未执行"
TOOLTIP_SKIPPED = "未勾选，本次没有执行"
DETAIL_STATUS_SKIPPED = "已跳过（未执行）"
DETAIL_SKIPPED_BODY = "这一项没有勾选，本次检查没有执行它。\n勾选后重新检查即可恢复。"
MSG_SKIPPED_TITLE = "有检查项被跳过"
MSG_SKIPPED = "本次有 {n} 项检查没有执行，其中 {errors} 项属于会阻断导出的错误。\n\n跳过的项会写进 manifest 与导出报告。仍要导出吗？"

# Categories
CATEGORY_NAMES = {
    "scene": "场景",
    "skeleton": "骨架",
    "mesh": "网格",
    "anim": "动画",
    "export": "导出",
}

# Detail panel
DETAIL_SELECT_HINT = "在左侧选择一项查看详情"
DETAIL_STATUS_PASSED = "通过"
DETAIL_STATUS_FAILED = "未通过（{level}）"
DETAIL_AUTOFIXABLE = "可自动修复"
DETAIL_META_FMT = "级别：{level}{fix} · {status}"
DETAIL_DETAILS_HEADER = "检测结果："
DETAIL_WHY_HEADER = "为什么查这个："
DETAIL_HOW_HEADER = "怎么才算合格 / 怎么改："
DETAIL_CHECK_ID_FMT = "检查项 ID：{cid}"
BTN_FIX = "修复"

# Clip table
COL_NAME = "名称"
COL_START = "起始帧"
COL_END = "结束帧"
COL_ROOT_MOTION = "根运动"
BTN_ADD_CLIP = "＋ 添加片段"
# 读骨骼上的实际 K 帧范围，不是时间轴滑块的范围——所以不叫"从时间轴填充"
BTN_FILL_RANGE = "填充动画范围"
BTN_REMOVE_CLIP = "删除"
DEFAULT_CLIP_NAME = "new_clip"

# Export panel
LBL_FBX_DIR = "保存目录："
LBL_FBX_NAME = "文件名："
LBL_UE_ROOT = "UE 内容根目录："
LBL_UE_SKELETON = "UE Skeleton 路径："
LBL_OVERWRITE = "重名策略："
LBL_SKEL_ROOT = "骨架根节点："
PH_FBX_DIR = "选一个文件夹，例如  D:/exports"
PH_FBX_NAME = "例如  walk.fbx（要以 .fbx 结尾）"
PH_UE_SKELETON = "已有骨架填 /Game/… ；首次交付可留空并勾下面的选项"
LBL_INCLUDE_RIG = "同时导出模型："
CHK_INCLUDE_RIG = "首次交付：把蒙皮模型一起导出，UE 侧自动创建 Skeleton"
LBL_UE_IMPORT_SCALE = "UE 导入缩放："
TIP_UE_IMPORT_SCALE = "创建骨架时的缩放倍数。角色按【米】制作时填 100 左右；\n后续动画会自动沿用同样的缩放。"
LBL_AUTO_PUSH = "导出后推送："
CHK_AUTO_PUSH = "导出成功后自动推送到运行中的 UE 编辑器"
TIP_AUTO_PUSH = "交付齐全时自动执行下方的导入代码。\n没发现编辑器只会提示一句，不影响导出结果。"
LBL_THINNING = "关键帧抽稀："
TIP_THINNING = (
    "导出前抽掉冗余关键帧：作用于场景里的动画曲线，误差不超过档位容差，"
    "整段操作一次 Ctrl+Z 即可撤销。\n关闭 = 完全不动曲线。"
    "逐帧烘焙的动画建议开【中】。"
)
# (显示文案, 内部档位 key)
THINNING_CHOICES = [("关闭", "off"), ("低", "low"), ("中", "medium"), ("高", "high")]
OVERWRITE_CHOICES = [("自动重命名", "rename"), ("覆盖已有资产", "overwrite"), ("跳过已有资产", "skip")]
BTN_BROWSE = "浏览"
BTN_EXPORT = "导出 FBX + Manifest"
STATUS_READY = "就绪"
STATUS_EXPORTING = "正在导出…"
DIALOG_BROWSE_TITLE = "选择保存目录"

# Export flow / messages
MSG_NO_FBX_PATH_TITLE = "缺少 FBX 路径"
MSG_NO_FBX_PATH = "请先设置 FBX 导出路径。"
MSG_NO_PRESET_TITLE = "未选择预设"
MSG_NO_PRESET = "请先选择一个骨架预设。"
MSG_EXPORT_BLOCKED_TITLE = "导出被阻止"
MSG_EXPORT_BLOCKED = "有 {n} 个 Error 级检查未通过，请先修复再导出。"
MSG_WARNINGS_TITLE = "存在警告"
MSG_WARNINGS = "有 {n} 个警告。仍要导出吗？"
MSG_EXPORT_DONE_TITLE = "导出完成"
MSG_EXPORT_DONE = "FBX 与 manifest 已写入。\n\n{summary}\n\nmanifest：{manifest}"
MSG_EXPORT_INCOMPLETE_TITLE = "导出未完成"
MSG_EXPORT_INCOMPLETE = "FBX 没有写出来。原因：\n\n{reasons}"
MSG_EXPORT_NO_REASON = "（未拿到具体原因）可尝试：\n· 确认 FBX 插件已加载\n· 换一个保存目录\n· 查看 Maya 脚本编辑器的红色报错"
MSG_EXPORT_FAILED_TITLE = "导出失败"
MSG_FIX_FAILED_TITLE = "修复失败"
MSG_MAYA_REQUIRED_TITLE = "需要 Maya 环境"
MSG_FIXED_ONE = "已修复：{cid}。正在重新检查…"
MSG_FIXED_N = "已自动修复 {n} 个警告：{ids}"

# 导出面板里那块错误区的引导语
EXPORT_ERRORS_HEADER = "导出失败原因："

# 交付产物卡片
DELIVERY_TITLES = ("FBX", "Manifest", "报告")
DELIVERY_OK = "交付完成 —— UE 端可以直接导入"
DELIVERY_PUSHED = "已送达 UE —— 资产已在工程里"
DELIVERY_PARTIAL = "交付不完整 —— 缺 manifest，UE 端读不到片段信息"
DELIVERY_FAILED = "导出未完成"
DELIVERY_NOT_WRITTEN = "未写出"
DELIVERY_SKIPPED = "已按设置跳过"
DELIVERY_BLOCKED = "未导出（原因未记录——见同目录 pipeline.log）"

# 交接给 UE —— Maya 端只写 FBX + manifest，建资产是 UE 那边的事。
# 用户填了 UE 目标路径就以为导出会自动进 UE，这里必须把断层补上。
HANDOFF_TITLE = "下一步：在 UE 里导入"
HANDOFF_COPY = "复制代码"
HANDOFF_COPIED = "已复制 —— 到 UE 的 Output Log（Python）里粘贴运行"

# 直推：把上面这段代码发给正在运行的 UE 编辑器执行。
# 推送失败绝不能挡住交付——复制代码那条路始终留着。
HANDOFF_PUSH = "推送到 UE"
PUSH_BUSY = "正在推送到 UE…"
PUSH_OK = "已在 UE 中导入完成（{editor}）"
PUSH_NO_EDITOR = (
    "没有发现正在运行的 UE 编辑器 —— 确认编辑器已打开，且在"
    "【编辑 → 项目设置 → 插件 → Python】里勾选了「启用远程执行」；"
    "也可以直接复制上面的代码手动运行"
)
PUSH_FAILED = "推送失败：{reason} —— 可以复制上面的代码手动运行"

# 推送成功后回读 manifest.result 呈现导入结果：资产清单是证据，不是装饰。
# 读不到（pending / 文件损坏）时退回 PUSH_OK，不推翻推送成功的事实。
IMPORT_CLIPS_LINE = "已创建 {n} 个 AnimSequence：{names}"
IMPORT_SKIPPED_LINE = "按覆盖策略跳过 {n} 个：{names}"
IMPORT_RIG_LINE = "首次交付已创建骨架：{skeleton}（模型：{mesh}）"
IMPORT_RIG_LINE_NO_MESH = "首次交付已创建骨架：{skeleton}"
IMPORT_FAILED_LINE = "UE 侧导入失败：{reasons}"
DELIVERY_IMPORT_FAILED = "已送达 UE —— 但导入未成功"
HANDOFF_CODE = (
    'import sys, importlib\n'
    'sys.path.insert(0, r"{repo}")\n'
    'import launch_ue_importer\n'
    '# 编辑器是长驻进程：重载一次，保证跑的是磁盘上的最新代码\n'
    'importlib.reload(launch_ue_importer)\n'
    '# 首次在新引擎版本上用，先跑一次： launch_ue_importer.check()\n'
    'outcome = launch_ue_importer.run(r"{manifest}")\n'
    'launch_ue_importer.report(outcome)'
)

# 导出设置里 UE 那一组的归属标注：这些值写进 manifest 交给 UE 侧读，
# Maya 端不会代为执行。
GROUP_LOCAL_OUTPUT = "本地产物"
GROUP_UE_HANDOFF = "写入 manifest，供 UE 导入时使用"
MSG_EXPORT_PARTIAL_TITLE = "交付不完整"
MSG_EXPORT_PARTIAL = (
    "FBX 已经写出来了，但 manifest 没有 —— UE 端拿不到片段范围和目标路径，"
    "这次交付不能用。\n\n原因：\n\n{reasons}"
)

# Export summary line
SUMMARY_FMT = (
    "校验：{status}（{errors} 错误 / {warnings} 警告 / {infos} 提示）· "
    "FBX {fbx} · {rng} · {clips} 个片段"
)
SUMMARY_FBX_OK = "已写入"
SUMMARY_FBX_FAIL = "未写入"
SUMMARY_RANGE_FMT = "帧 {start}–{end}"
SUMMARY_NO_RANGE = "无范围"

# Validation summary status (RunReport.status -> 中文)
STATUS_LABELS = {
    "passed": "全部通过",
    "passed_with_warnings": "有警告",
    "failed": "有错误",
}

# Severity levels
LEVEL_LABELS = {
    "error": "错误",
    "warning": "警告",
    "info": "提示",
}
