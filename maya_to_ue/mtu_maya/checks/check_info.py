"""mtu_maya.checks.check_info

Chinese, artist-facing documentation for every check.

Each entry answers three questions a 制作人员 actually asks:
    title      —— 这是什么检查？
    why        —— 为什么要查这个？（不查会怎样）
    how_to_fix —— 怎么才算合格？我该去哪改？

Keyed by check id. The UI looks these up and falls back to the validator's
English `description` only if an entry is missing — so adding a new check
never breaks the UI, it just shows English until documented here.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# check_id -> (title, why, how_to_fix)
CHECK_INFO: Dict[str, Tuple[str, str, str]] = {

    # ---------------------------------------------------------------- scene
    "scene.unit": (
        "场景单位",
        "UE 默认用厘米。Maya 如果是米或毫米，导过去的动画会放大/缩小 100 倍。",
        "把场景线性单位改成 厘米(cm)。\n"
        "位置：Windows → Settings/Preferences → Preferences → Settings → Linear → centimeter。\n"
        "改单位会影响场景解释方式；先保存备份，再由制作人员手动处理。",
    ),
    "scene.up_axis": (
        "朝上轴",
        "工具会保留场景当前朝上轴，避免修改已有角色绑定或动画坐标。",
        "不需要修复。Maya 导出会保留源轴；UE 导入会执行 FBX 坐标转换。",
    ),
    "scene.fps": (
        "场景帧率",
        "帧率不对，动画到 UE 会变快或变慢。必须匹配当前项目配置的目标 FPS。",
        "把帧率改成项目配置的目标值。\n"
        "位置：Windows → Settings/Preferences → Preferences → Settings → Time。\n"
        "改帧率可能改变动画播放解释；先确认项目帧率，再由制作人员手动处理。",
    ),
    "scene.timeline_range": (
        "时间轴范围",
        "时间轴起止帧要是有效的一段（不能是 0 长度或倒过来），否则导不出动画。",
        "确认下方时间轴是一个正常区间（比如 1–120）。\n"
        "手动把开始帧、结束帧拖成有效范围即可。",
    ),

    # ------------------------------------------------------------ skeleton
    "skeleton.root_exists": (
        "骨架根节点",
        "导出必须有一个明确的根骨骼（比如 root / pelvis / Hips），否则 UE 不知道骨架从哪开始。\n"
        "工具只检查【导出设置】里选择的根节点及其后代，不会因场景中其他角色阻断本次导出。",
        "两种情况：\n"
        "① 场景里根本没有骨骼 —— 先搭好或导入骨架。\n"
        "② 有骨骼但没指定根 —— 在【导出设置】的【骨架根节点】下拉框里，选中骨架最顶层的那个关节即可。",
    ),
    "skeleton.naming": (
        "骨骼命名",
        "骨骼名字要符合【当前所选预设】的命名规则，UE 才能正确识别/重定向。\n"
        "绝大多数失败是因为【预设选错了】——比如你用的是 Mixamo 骨架，却选了 UE Mannequin 预设。",
        "按顺序排查：\n"
        "① 先确认右上角【骨架预设】选对了（UE Mannequin / Mixamo / 自定义），和你的骨架来源一致。\n"
        "② 预设对了还是报错：说明部分骨骼名字确实不规范，需要手动重命名\n"
        "   （双击这条结果可选中问题骨骼，右侧详情会列出哪些名字不合规）。\n"
        "③ 如果你只导动画、不关心重定向，这条是警告级，可以忽略后继续导出。",
    ),
    "skeleton.scale": (
        "骨骼缩放",
        "骨骼缩放会影响 FBX 位移与子骨骼变换。直接归一 Scale 可能破坏已有绑定或动画。",
        "先复制场景或备份文件，再由绑定人员确认如何处理。\n"
        "不要对已绑定或已制作动画的骨架直接自动归一缩放。",
    ),
    "skeleton.single_root": (
        "骨架根唯一",
        "本检查只分析【导出设置】里选中的导出根层级；场景可同时保留其他角色。\n"
        "同一导出层级中存在多套独立骨架根时，UE 会只取其中一套，或直接建出错误的 Skeleton。",
        "【导出设置】里选择单一角色的最顶层关节。\n"
        "若该层级内确有多套骨架，拆分导出；双击可选中被识别为根的骨骼。",
    ),
    "skeleton.duplicate_names": (
        "骨骼重名",
        "UE 用【骨骼名字】建骨架，不认 Maya 的层级路径。\n"
        "本检查只分析【导出设置】里选中的导出根层级；该层级内两根骨骼同名会导致 UE 丢骨骼或绑错动画。",
        "把重名骨骼改成唯一名字。\n"
        "右侧详情里列出的就是重复的短名，逐个重命名即可。",
    ),
    "skeleton.real_world_scale": (
        "骨架实际尺寸",
        "UE 用厘米做单位，一个成年人形角色大约 180 cm 高。\n"
        "如果模型是按【米】制作的（常见于网上下载的资产），放进厘米场景后\n"
        "身高就只有 1.8 左右，导到 UE 里小到几乎看不见。",
        "两种处理方式，选一种：\n"
        "① 【推荐】UE 导入骨架时填 Import Uniform Scale（详情里给了建议倍数），\n"
        "   之后动画会自动沿用同样的缩放，不用每次都设。\n"
        "② 在 Maya 里把角色整体放大到真实尺寸再重新绑定。\n"
        "   注意：已经 K 好动画的骨架直接缩放会影响位移曲线，要谨慎。",
    ),
    "skeleton.bind_pose": (
        "参考姿势（T-pose）",
        "这项只测导出起始帧是否接近 T-pose，不是严格 Bind Pose 检查。\n"
        "FBX 含正确 Bind Pose 且 UE 关闭 Use T0 As Ref Pose 时，动画首帧通常不会成为 Skeleton 的参考姿势。\n\n"
        "仍建议在首次交付后检查 Skeleton Reference Pose，尤其后续要做：\n"
        "· 动画重定向（IK Retargeter）\n"
        "· 物理资产、布料\n"
        "· 加法动画（Additive）",
        "先确认 UE 导入选项 Use T0 As Ref Pose 为关闭。\n"
        "再打开新建的 Skeleton 检查 Reference Pose。若 FBX 缺少正确 Bind Pose，\n"
        "推荐单独用带蒙皮且姿势正确的角色 FBX 创建 Skeleton，后续动画复用该 Skeleton。",
    ),
    "skeleton.segment_scale": (
        "骨骼缩放补偿",
        "segmentScaleCompensate 是 Maya 专有特性，FBX 和 UE 都不支持。\n"
        "开着它做过缩放动画，到 UE 里子骨骼会错位、拉伸。",
        "这项不自动修复，因为直接关闭可能改变已有绑定或动画结果。\n"
        "先备份场景，再由绑定人员确认后：选中骨骼 → 属性编辑器 → Joint → 取消勾选 Segment Scale Compensate。",
    ),

    # ---------------------------------------------------------------- mesh
    "mesh.history": (
        "建模历史",
        "未蒙皮模型上残留的建模历史会让导出变慢、带出多余节点。\n"
        "注意：蒙皮模型的变形器历史（skinCluster/blendShape）是绑定本身，工具不会碰。",
        "只对未蒙皮的模型删历史。\n"
        "位置：选中模型 → Edit → Delete by Type → History。\n"
        "绝对不要对已蒙皮角色执行【删除全部历史】，那会毁掉绑定。",
    ),
    "mesh.transforms": (
        "模型变换冻结",
        "未蒙皮模型的位移/旋转/缩放不是 0/0/1 时，导到 UE 位置会跑偏。\n"
        "注意：已蒙皮模型不能冻结变换，冻结会破坏绑定姿势，工具会自动跳过。",
        "只冻结未蒙皮模型：选中模型 → Modify → Freeze Transformations。\n"
        "双击这条结果可以选中问题模型。",
    ),
    "mesh.uv": (
        "模型 UV",
        "模型需要 UV 才能在 UE 里正确贴图。当前是纯动画导出，所以只是提示。",
        "如果这次只导动画、不导模型，可以直接忽略这条。",
    ),
    "mesh.skin_weight": (
        "蒙皮权重",
        "蒙皮权重没有归一化（总和不为 1），模型在 UE 里变形会穿帮。",
        "先备份，再由绑定人员归一化蒙皮权重。\n"
        "位置：选中蒙皮模型 → Skin → Normalize Weights。工具不会自动修改权重。",
    ),

    # ---------------------------------------------------------------- anim
    "anim.curves_on_expected": (
        "动画曲线归属",
        "动画曲线应该只 K 在骨骼或控制器上。K 在别的杂节点上，导出容易带脏数据。",
        "检查右侧列出的节点，把多余的动画曲线清掉，只保留骨骼/控制器上的。",
    ),
    "anim.stray_layers": (
        "多余动画层",
        "场景里有没用到的动画层（Anim Layer），导出时可能混进多余动画。",
        "在动画层编辑器里删掉不用的层，只保留 BaseAnimation 和需要的层。",
    ),
    "anim.clip_ranges_valid": (
        "片段帧范围",
        "【动画片段】里每个动画片段的起止帧要合法：结束帧不能小于开始帧，且要落在时间轴范围内。\n"
        "这是 Error 级——不合法会直接导致导出失败。",
        "在【动画片段】表格里，把每一行的【起始帧/结束帧】改成合法范围\n"
        "（结束帧 ≥ 起始帧，且在场景时间轴内）。",
    ),
    "anim.clip_overlap": (
        "片段区间重叠",
        "两个片段的帧范围重叠时，重叠帧会被导进两个 AnimSequence。\n"
        "UE 里会出现两段动画开头/结尾重复的一小段，接循环时会顿一下。",
        "在【动画片段】表格里调整起止帧，让片段首尾相接而不是相互覆盖。\n"
        "例如 idle 用 1–30，walk 就从 31 开始，而不是 30。",
    ),
    "anim.keys_in_clip_range": (
        "关键帧落在片段内",
        "如果骨骼的关键帧全在你填的片段范围之外，那段范围里其实没有动画。\n"
        "导出的 FBX 在 UE 里会是一段静止不动的动画。",
        "对照时间轴确认【动画片段】里填的起止帧。\n"
        "双击这条结果可以选中关键帧不在范围内的骨骼。",
    ),
    "anim.skeleton_animated": (
        "骨架有动画",
        "整套骨架上一根带动画的骨骼都没有。这种情况导出的 FBX 到 UE 里没有任何动作。\n"
        "常见原因：选错了骨架根、动画还在控制器上没烘焙到骨骼、或打开了错误的场景。",
        "确认三点：\n"
        "① 【导出设置】里的【骨架根节点】选的是真正带动画的那套骨架。\n"
        "② 如果动画在控制器上，先把动画烘焙（Bake）到骨骼。\n"
        "③ 时间轴上确实能看到骨骼在动。",
    ),
    "anim.root_motion_match": (
        "根运动设置",
        "走路/跑步这类位移动画要勾【根运动】，待机/原地动作不勾。\n"
        "勾错了，UE 里角色会原地打滑或漂移。",
        "在【动画片段】表格的【根运动】列：位移类（走/跑/冲刺）打勾，原地类（待机/呼吸）不打勾。",
    ),
    "anim.keys_dense": (
        "关键帧密度",
        "逐帧烘焙的曲线（每帧一个 key）会让 FBX 变大，曲线编辑器里也没法手改。\n"
        "UE 导入不受影响，但资产是冗余的，入库前该抽掉。",
        "在【导出设置】里把【关键帧抽稀】调到低/中/高：导出时自动抽掉冗余 key，"
        "误差不超过档位容差，且可以 Ctrl+Z 整体撤销。\n"
        "开了抽稀之后这项检查会自动通过。",
    ),

    # -------------------------------------------------------------- export
    "export.fbx_plugin": (
        "FBX 插件",
        "Maya 必须加载 FBX 导出插件，否则根本导不出 FBX 文件。",
        "加载 FBX 插件。\n"
        "位置：Windows → Settings/Preferences → Plug-in Manager → 勾上 fbxmaya。",
    ),
    "export.path_valid": (
        "导出路径",
        "FBX 要存到一个真实存在、可写的目录里，文件名还得合法，否则导出会失败。",
        "【导出设置】里分两项填：\n"
        "  · 【保存目录】—— 一个文件夹，点旁边的 … 按钮直接选，不要带 .fbx。\n"
        "  · 【文件名】—— 导出的文件叫什么，要以 .fbx 结尾（比如 walk.fbx）。\n"
        "如果只是【保存目录不存在】：点【修复】，工具会自动把目录建出来。\n"
        "如果提示【不可写】：那个目录没写入权限，换一个有权限的位置。",
    ),
    "export.naming_legal": (
        "片段命名合法",
        "片段名里不能有 \\ : * ? \" < > | / 这些字符——Windows 和 UE 都不允许，会导致建资产失败。",
        "在【动画片段】表格里把片段名改成不含特殊字符的名字（用字母/数字/下划线最安全）。",
    ),
    "export.ue_path_valid": (
        "UE 目标路径",
        "这两个路径会写进 manifest，UE 端全靠它找地方建资产。\n"
        "填错的话 FBX 能导出来，但 manifest 写不出去——UE 那边等于什么都没收到。",
        "【导出设置】里两项都要合法：\n"
        "  · 【UE 目标路径】—— UE 内容浏览器里的包路径，必须以 /Game 开头，"
        "比如 /Game/Animations/Hero。\n"
        "  · 【UE Skeleton 路径】—— UE 里已有的骨架资产路径，同样以 /Game 开头。\n"
        "如果这套绑定是第一次进 UE（骨架还不存在）：Skeleton 路径可以留空，"
        "但必须勾上【同时导出模型】，让 UE 用同一个 FBX 先把骨架建出来。",
    ),
    "export.skeleton_root_set": (
        "指定骨架根",
        "导出前必须告诉工具骨架根节点是哪一个，否则不知道导哪套骨架。",
        "在【导出设置】的【骨架根节点】下拉框里选中骨架最顶层的关节。",
    ),
}


def lookup(check_id: str) -> Optional[Tuple[str, str, str]]:
    """Return (title, why, how_to_fix) for a check id, or None if undocumented."""
    return CHECK_INFO.get(check_id)


def title_for(check_id: str, fallback: str = "") -> str:
    info = CHECK_INFO.get(check_id)
    if info:
        return info[0]
    return fallback or check_id


def why_for(check_id: str, fallback: str = "") -> str:
    info = CHECK_INFO.get(check_id)
    if info:
        return info[1]
    return fallback


def how_to_fix_for(check_id: str, fallback: str = "") -> str:
    info = CHECK_INFO.get(check_id)
    if info:
        return info[2]
    return fallback


__all__ = [
    "CHECK_INFO",
    "lookup",
    "title_for",
    "why_for",
    "how_to_fix_for",
]
