"""maya.export.fbx_exporter

Single-FBX-multi-clip animation export (see design.md section 5 & 10):

    1. Build a CheckContext from the live scene.
    2. Run all validators; abort if any Error (locked convention).
    3. Compute the FBX export range = [min clip start, max clip end].
    4. Apply the FBX export preset to Maya's FBX plugin.
    5. Bake + export a single FBX covering the whole range.
    6. The clip boundaries are NOT cut here — UE slices them later via
       the manifest. This keeps the FBX count at 1 regardless of clips.

The exporter is the orchestrator; manifest/report writing live in
sibling modules and are called by export_animation().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import List, Optional, Set

from bridge.schema import (
    Clip,
    Manifest,
    Source,
    Convention,
    UEDestination,
    SkeletonDelivery,
)
from mtu_maya.checks import (
    CheckContext,
    RunReport,
    run_all_checks,
)
from mtu_maya.core import maya_utils
from mtu_maya.core.config import FBXExportPreset, PipelineSettings
from mtu_maya.core.curve_thinning import ThinningResult, thin_skeleton_curves
from mtu_maya.core.preset_loader import SkeletonPreset


# ---------------------------------------------------------------------------
# Export request (what the UI hands us)
# ---------------------------------------------------------------------------

@dataclass
class ExportRequest:
    """User inputs gathered by the UI for a single export action.

    All path-like fields are taken verbatim from the UI; the exporter
    resolves them to absolute paths internally.
    """

    fbx_path: str
    clips: List[Clip]
    preset: SkeletonPreset                  # active skeleton preset
    skeleton_root: str                       # explicit root joint path
    ue_content_root: str = "/Game/Animations"
    ue_skeleton_path: str = ""
    overwrite_policy: str = "rename"
    # First-delivery options: ship the rig in the same FBX and let UE build
    # the Skeleton, instead of requiring it to exist beforehand.
    include_rig: bool = False
    create_skeleton_if_missing: bool = False
    ue_import_scale: float = 1.0
    # 关键帧抽稀档位：off（默认，不动曲线）/ low / medium / high。
    # 作用于场景曲线、导出前执行、单 undo chunk 可整体撤销。
    thinning_level: str = "off"
    fbx_preset: Optional[FBXExportPreset] = None
    settings: Optional[PipelineSettings] = None
    skipped_checks: Set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Export outcome
# ---------------------------------------------------------------------------

@dataclass
class ExportResult:
    """What export_animation() returns.

    `manifest` is always populated (even on failure) so the UI can show
    the validation report; `fbx_written` is False if export was blocked
    or FBX writing failed. `manifest_path` / `report_path` are filled in
    by manifest_writer.write_all_artifacts() and stay empty when that
    artifact could not be written — an FBX without a manifest is not a
    complete delivery.
    """

    manifest: Manifest
    report: RunReport
    fbx_written: bool
    fbx_path: str
    export_range: Optional[tuple]   # (start, end) used, or None if blocked
    errors: List[str] = None
    manifest_path: str = ""
    report_path: str = ""
    # 本次导出执行的抽稀结果；档位为 off 或被阻断时为 None。
    thinning: "Optional[ThinningResult]" = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def is_complete(self) -> bool:
        """True only when both the FBX and its manifest reached disk."""
        return bool(self.fbx_written and self.manifest_path)


# ---------------------------------------------------------------------------
# Scene scope helpers
# ---------------------------------------------------------------------------

def _joint_hierarchy(c, root: Optional[str]) -> List[str]:
    """Return *root* and every descendant joint, using full DAG paths."""
    if not root:
        return []
    try:
        descendants = c.listRelatives(
            root, allDescendents=True, type="joint", fullPath=True
        ) or []
    except Exception:
        descendants = []
    joints = []
    seen = set()
    for joint in [root] + list(descendants):
        if joint not in seen:
            joints.append(joint)
            seen.add(joint)
    return joints


def _select_joint_hierarchy(c, root: str) -> List[str]:
    """Select only joints under *root*, then return their full DAG paths."""
    try:
        c.select(root, hierarchy=True, replace=True)
        return c.ls(selection=True, type="joint", long=True) or []
    except Exception:
        return _joint_hierarchy(c, root)


def _skin_clusters_for_mesh(c, mesh: str) -> List[str]:
    try:
        return c.listConnections(mesh, type="skinCluster", destination=False) or []
    except Exception:
        return []


def _skin_cluster_belongs_to_hierarchy(c, skin_cluster: str, joints: List[str]) -> bool:
    """True when a mesh is bound only to joints in the selected hierarchy."""
    target_joints = set(joints)
    if not target_joints:
        return False
    try:
        influences = c.skinCluster(skin_cluster, query=True, influence=True) or []
    except Exception:
        return False
    if not influences:
        return False

    resolved_influences = []
    for influence in influences:
        try:
            paths = c.ls(influence, long=True) or []
        except Exception:
            return False
        if not paths:
            return False
        resolved_influences.extend(paths)

    # A mesh can be influenced by non-joint helper nodes. Ignore those, but
    # require at least one target joint and reject joints from another rig.
    joint_influences = [
        path for path in resolved_influences if _node_is_joint(c, path)
    ]
    if not joint_influences:
        return False
    return (
        any(path in target_joints for path in joint_influences)
        and all(path in target_joints for path in joint_influences)
    )


def _node_is_joint(c, path: str) -> bool:
    try:
        return c.nodeType(path) == "joint"
    except Exception:
        return False


def _target_skinned_meshes(c, joints: List[str]):
    """Return ``(shape, transform, skin_clusters)`` for the target rig only."""
    if not joints:
        return []
    try:
        meshes = c.ls(type="mesh", long=True) or []
    except Exception:
        return []

    result = []
    seen_transforms = set()
    for mesh in meshes:
        skin_clusters = _skin_clusters_for_mesh(c, mesh)
        if not skin_clusters:
            continue
        if not all(
            _skin_cluster_belongs_to_hierarchy(c, skin_cluster, joints)
            for skin_cluster in skin_clusters
        ):
            continue
        try:
            parents = c.listRelatives(mesh, parent=True, fullPath=True) or []
        except Exception:
            parents = []
        transform = parents[0] if parents else mesh
        if transform in seen_transforms:
            continue
        seen_transforms.add(transform)
        result.append((mesh, transform, skin_clusters))
    return result


# ---------------------------------------------------------------------------
# Scene -> CheckContext
# ---------------------------------------------------------------------------

def build_context(req: ExportRequest) -> CheckContext:
    """Build a CheckContext from the live Maya scene + the export request.

    This is the ONE place that reads the scene for validation. All
    validators receive this context and never call cmds themselves
    during check().
    """
    c = maya_utils.cmds()
    root = req.skeleton_root or maya_utils.find_root_joint()
    resolved_root = maya_utils.resolve_joint(root) if root else None
    joints = _joint_hierarchy(c, resolved_root)

    joint_scales = {}
    for j in joints:
        try:
            joint_scales[j] = maya_utils.joint_scale(j)
        except Exception:
            joint_scales[j] = (1.0, 1.0, 1.0)

    # Mesh state is scoped to the selected export hierarchy. A scene can hold
    # several characters; unrelated meshes must not affect this delivery.
    target_meshes = _target_skinned_meshes(c, joints)
    meshes = [mesh for mesh, _transform, _skins in target_meshes]
    mesh_history = {}
    mesh_frozen = {}
    mesh_has_uvs = {}
    mesh_skin_normalized = {}
    mesh_skinned = {}
    # Deformers are legitimate history on a rigged character: deleting them
    # would destroy the rig. Only *modelling* history counts as a problem.
    _DEFORMER_TYPES = (
        "skinCluster", "blendShape", "cluster", "lattice", "ffd",
        "wrap", "nonLinear", "deltaMush", "tension", "proximityWrap",
    )
    _IGNORED_HISTORY = (
        "mesh", "transform", "shadingEngine", "groupId", "groupParts",
        "objectSet", "tweak", "joint", "dagPose",
    )
    for m, xform, skins in target_meshes:
        # Use the transform parent for history/freeze queries.
        is_skinned = bool(skins)
        mesh_skinned[xform] = is_skinned
        try:
            hist = c.listHistory(xform, pruneDag=True, groupLevels=True) or []
            has_hist = any(
                c.nodeType(h) not in _IGNORED_HISTORY
                and c.nodeType(h) not in _DEFORMER_TYPES
                for h in hist
            )
        except Exception:
            has_hist = False
        mesh_history[xform] = not has_hist
        try:
            t = c.getAttr(f"{xform}.translate")[0]
            r = c.getAttr(f"{xform}.rotate")[0]
            s = c.getAttr(f"{xform}.scale")[0]
            mesh_frozen[xform] = (
                all(abs(v) < 1e-4 for v in t + r)
                and all(abs(v - 1.0) < 1e-4 for v in s)
            )
        except Exception:
            mesh_frozen[xform] = True
        try:
            mesh_has_uvs[xform] = bool(c.polyEvaluate(m, uv=True))
        except Exception:
            mesh_has_uvs[xform] = True
        try:
            mesh_skin_normalized[xform] = all(
                int(c.getAttr(f"{skin}.normalizeWeights")) != 0 for skin in skins
            )
        except Exception:
            mesh_skin_normalized[xform] = True

    # Animation state is scoped to the export hierarchy. Curves on other
    # characters or scene controls must not make this rig appear animated.
    animated_nodes = []
    animation_curve_targets = {}
    try:
        for joint in joints:
            curves = c.listConnections(
                joint, type="animCurve", source=True, destination=False
            ) or []
            for curve in curves:
                if curve in animation_curve_targets:
                    continue
                animated_nodes.append(curve)
                try:
                    targets = c.listConnections(
                        curve, source=False, destination=True
                    ) or []
                    animation_curve_targets[curve] = [
                        node for node in targets
                        if c.nodeType(node) not in ("unitConversion",)
                    ]
                except Exception:
                    animation_curve_targets[curve] = []
    except Exception:
        animated_nodes = []
        animation_curve_targets = {}
    try:
        layers = c.ls(type="animLayer", long=True) or []
        stray = []
        for layer in layers:
            is_base = bool(c.animLayer(layer, query=True, root=True))
            has_curves = bool(c.animLayer(layer, query=True, animCurves=True) or [])
            if not is_base and not has_curves:
                stray.append(layer)
    except Exception:
        stray = []

    # 逐帧烘焙曲线：key 数 ≥ 帧跨度的 90%。按密度降序，最密的排最前。
    dense_curves = []
    for curve in animated_nodes:
        try:
            times = c.keyframe(curve, query=True, timeChange=True) or []
        except Exception:
            continue
        if len(times) < 10:
            continue
        span = max(times) - min(times)
        if span > 0 and len(times) >= 0.9 * (span + 1):
            dense_curves.append((len(times) / (span + 1), curve))
    dense_curves = [curve for _density, curve in sorted(
        dense_curves, key=lambda kv: kv[0], reverse=True)]

    tl_start, tl_end = maya_utils.timeline_range()

    # --- Skeleton topology facts that actually break UE imports -------------
    skeleton_roots = []
    duplicate_joint_names = []
    segment_scale_compensate = []
    constrained_joints = []
    unanimated_joints = []
    keys_outside_clip_range = []

    short_name_counts = {}
    for j in joints:
        short = j.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
        short_name_counts[short] = short_name_counts.get(short, 0) + 1
        try:
            parent = c.listRelatives(j, parent=True, fullPath=True) or []
            if (
                not parent
                or c.nodeType(parent[0]) != "joint"
                or parent[0] not in joints
            ):
                if j not in skeleton_roots:
                    skeleton_roots.append(j)
        except Exception:
            pass
        try:
            if c.attributeQuery("segmentScaleCompensate", node=j, exists=True):
                if bool(c.getAttr(f"{j}.segmentScaleCompensate")):
                    segment_scale_compensate.append(j)
        except Exception:
            pass
        try:
            cons = c.listConnections(j, type="constraint", source=True, destination=False) or []
            if cons:
                constrained_joints.append(j)
        except Exception:
            pass
    duplicate_joint_names = sorted(n for n, count in short_name_counts.items() if count > 1)

    # Skeleton height along the scene's up axis. A character that is 3 units
    # tall in a centimetre scene will look microscopic in UE, and that is far
    # cheaper to catch here than after a full round trip.
    skeleton_height = 0.0
    if joints:
        up_index = 2 if maya_utils.scene_up_axis().lower() == "z" else 1
        coords = []
        for j in joints:
            try:
                pos = c.xform(j, query=True, worldSpace=True, translation=True)
                coords.append(pos[up_index])
            except Exception:
                continue
        if coords:
            skeleton_height = max(coords) - min(coords)

    # Which joints actually carry animation, and do their keys sit in range?
    clip_bounds = None
    if req.clips:
        clip_bounds = (
            min(cl.start for cl in req.clips),
            max(cl.end for cl in req.clips),
        )
    for j in joints:
        try:
            curves = c.listConnections(
                j, type="animCurve", source=True, destination=False
            ) or []
        except Exception:
            curves = []
        if not curves:
            unanimated_joints.append(j)
            continue
        if clip_bounds is None:
            continue
        try:
            times = c.keyframe(j, query=True, timeChange=True) or []
        except Exception:
            times = []
        if times and (min(times) > clip_bounds[1] or max(times) < clip_bounds[0]):
            keys_outside_clip_range.append(j)

    # Rough T-pose signal at the export start. This cannot prove a Bind Pose:
    # UE should use the FBX Bind Pose when present and Use T0 As Ref Pose is off.
    tpose_arm_deviation = -1.0
    if req.include_rig and req.preset is not None:
        tpose_arm_deviation = _measure_tpose_deviation(
            c, joints, req.preset, clip_bounds[0] if clip_bounds else None
        )

    return CheckContext(
        scene_name=maya_utils.current_scene_name(),
        scene_units=maya_utils.scene_units(),
        scene_up_axis=maya_utils.scene_up_axis(),
        scene_fps=maya_utils.scene_fps(),
        target_frame_rate=(
            req.settings.frame_rate if req.settings is not None else 30.0
        ),
        timeline_start=tl_start,
        timeline_end=tl_end,
        joints=joints,
        root_joint=root,
        joint_scales=joint_scales,
        preset=req.preset,
        has_mesh=bool(meshes),
        mesh_nodes=list(mesh_history.keys()),
        mesh_history=mesh_history,
        mesh_frozen=mesh_frozen,
        mesh_has_uvs=mesh_has_uvs,
        mesh_skin_normalized=mesh_skin_normalized,
        mesh_skinned=mesh_skinned,
        animated_nodes=animated_nodes,
        animation_curve_targets=animation_curve_targets,
        stray_anim_layers=stray,
        dense_curves=dense_curves,
        thinning_level=req.thinning_level,
        unanimated_joints=unanimated_joints,
        keys_outside_clip_range=keys_outside_clip_range,
        constrained_joints=constrained_joints,
        skeleton_roots=skeleton_roots,
        duplicate_joint_names=duplicate_joint_names,
        segment_scale_compensate=segment_scale_compensate,
        skeleton_height=skeleton_height,
        include_rig=req.include_rig,
        tpose_arm_deviation=tpose_arm_deviation,
        clips=req.clips,
        fbx_path=req.fbx_path,
        skeleton_root_selected=req.skeleton_root,
        ue_content_root=req.ue_content_root,
        ue_skeleton_path=req.ue_skeleton_path,
        create_skeleton_if_missing=req.create_skeleton_if_missing,
        fbx_plugin_loaded=maya_utils.fbx_plugin_loaded(),
    )


# ---------------------------------------------------------------------------
# Range computation
# ---------------------------------------------------------------------------

def compute_export_range(clips: List[Clip]) -> Optional[tuple]:
    """Return (min_start, max_end) across all clips, or None if no clips."""
    if not clips:
        return None
    starts = [c.start for c in clips]
    ends = [c.end for c in clips]
    return (min(starts), max(ends))


# ---------------------------------------------------------------------------
# FBX export
# ---------------------------------------------------------------------------

def _apply_fbx_preset(preset: FBXExportPreset) -> None:
    """Push the preset into Maya's FBX plugin."""
    preset.apply_to_maya()


def _measure_tpose_deviation(c, joints, preset, frame) -> float:
    """Return how far the arms are from horizontal at *frame*, in degrees.

    A T-pose has both arms roughly level with the shoulders. Measuring the
    angle between the shoulder->hand vector and the horizontal plane gives a
    cheap, rig-agnostic signal that works for any preset with an arm mapping.

    Returns -1.0 when the pose cannot be measured (unmapped rig, missing
    joints, or no Maya session).
    """
    import math

    bone_map = getattr(preset, "bone_map", None) or {}
    pairs = [
        (bone_map.get("upperarm_l"), bone_map.get("hand_l")),
        (bone_map.get("upperarm_r"), bone_map.get("hand_r")),
    ]
    pairs = [(a, b) for a, b in pairs if a and b]
    if not pairs:
        return -1.0

    def _resolve(short_name):
        for path in joints:
            leaf = path.rsplit("|", 1)[-1]
            if leaf == short_name or leaf.rsplit(":", 1)[-1] == short_name:
                return path
        return None

    original_time = None
    try:
        if frame is not None:
            original_time = c.currentTime(query=True)
            c.currentTime(frame)

        up_index = 2 if maya_utils.scene_up_axis().lower() == "z" else 1
        deviations = []
        for shoulder_name, hand_name in pairs:
            shoulder = _resolve(shoulder_name)
            hand = _resolve(hand_name)
            if not shoulder or not hand:
                continue
            sp = c.xform(shoulder, query=True, worldSpace=True, translation=True)
            hp = c.xform(hand, query=True, worldSpace=True, translation=True)
            delta = [hp[i] - sp[i] for i in range(3)]
            length = math.sqrt(sum(v * v for v in delta))
            if length < 1e-6:
                continue
            # Angle between the arm and the horizontal plane.
            vertical = abs(delta[up_index])
            deviations.append(math.degrees(math.asin(min(1.0, vertical / length))))

        if not deviations:
            return -1.0
        return max(deviations)
    except Exception:
        return -1.0
    finally:
        if original_time is not None:
            try:
                c.currentTime(original_time)
            except Exception:
                pass


def _export_fbx(
    fbx_path: str,
    root: str,
    start: int,
    end: int,
    include_rig: bool = False,
) -> None:
    """Bake animation on *root* subtree and export one FBX over [start, end].

    When *include_rig* is set, skinned meshes are exported alongside the
    skeleton so UE can build a Skeleton from the same file.
    """
    c = maya_utils.cmds()

    if not fbx_path or not str(fbx_path).strip():
        raise ValueError("导出路径为空 —— 请在【导出设置】里填好【保存目录】和【文件名】")
    if not str(fbx_path).lower().endswith(".fbx"):
        raise ValueError("导出文件必须以 .fbx 结尾")
    fbx_path = os.path.abspath(fbx_path).replace("\\", "/")
    if not root or not str(root).strip():
        raise ValueError("骨架根节点为空 —— 请在【导出设置】里选中骨架最顶层的关节")

    resolved_root = maya_utils.resolve_joint(root)
    if resolved_root is None:
        raise ValueError(
            f"选中的骨架根 {root!r} 在场景里找不到对应关节 —— "
            "请在【导出设置】的【骨架根节点】下拉里直接选一个，别手动敲"
        )

    selected_joints = _select_joint_hierarchy(c, resolved_root)
    if not selected_joints:
        raise ValueError(
            f"从骨架根 {resolved_root!r} 选不到任何关节 —— 导出会得到空 FBX。"
            "请确认【导出设置】里选的是真正的骨架根节点。"
        )
    try:
        # Re-select explicit joint paths so unrelated geometry parented below
        # the rig cannot leak into export.
        c.select(selected_joints, replace=True)
    except Exception as exc:
        raise ValueError(f"选不中骨架根节点 {resolved_root!r}（它可能不存在或不是关节）：{exc}") from exc

    if include_rig:
        # UE can only build a Skeleton from a file that contains a skinned
        # mesh. Add only meshes bound exclusively to this hierarchy; a scene
        # may contain other characters with their own skinClusters.
        skinned = [
            transform
            for _mesh, transform, _skins in _target_skinned_meshes(c, selected_joints)
        ]
        if not skinned:
            raise ValueError(
                "勾选了【同时导出模型】，但没有找到只蒙皮到当前骨架的模型 —— "
                "UE 无法从纯骨架 FBX 创建 Skeleton。"
            )
        c.select(skinned, add=True)

    parent = os.path.dirname(fbx_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    import maya.mel as mel

    def set_option(command: str, value: str) -> None:
        try:
            mel.eval(f"{command} -v {value}")
        except Exception as exc:
            raise RuntimeError(
                f"could not set FBX export option {command} to {value!r}: {exc}"
            ) from exc

    set_option("FBXExportBakeComplexStart", str(start))
    set_option("FBXExportBakeComplexEnd", str(end))
    set_option("FBXExportBakeComplexAnimation", "true")
    if include_rig:
        # Without these the mesh ships unskinned and UE builds a Skeleton
        # with no bindings.
        set_option("FBXExportSkins", "true")
        set_option("FBXExportShapes", "true")
    try:
        mel.eval('FBXExport -f "{}" -s'.format(fbx_path.replace('"', '\\"')))
    except Exception as exc:
        raise RuntimeError(f"FBXExport failed: {exc}") from exc

    # A "successful" FBXExport can still produce a file with no usable content
    # (wrong selection, stripped hierarchy, ...). UE only reports that as a
    # vague "no mesh or animation track found", so catch it here instead.
    if not os.path.isfile(fbx_path):
        raise RuntimeError(f"FBX 导出命令执行了，但文件没生成：{fbx_path}")
    size = os.path.getsize(fbx_path)
    if size < 1024:
        raise RuntimeError(
            f"导出的 FBX 只有 {size} 字节，等于空文件 —— "
            f"选中的 {len(selected_joints)} 根骨骼没有被写进去。"
        )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def export_animation(req: ExportRequest) -> ExportResult:
    """Run the full export pipeline: validate -> bake -> export FBX.

    Returns an ExportResult. Even when export is blocked by Errors,
    the manifest is still built and returned (with fbx_written=False)
    so the UI can show the validation report.
    """
    errors: List[str] = []

    # 1. Build context from the live scene. Keep the original request intact:
    # first-delivery fields must reach both validation and manifest generation.
    settings = req.settings or PipelineSettings()
    if req.settings is None:
        req = replace(req, settings=settings)
    ctx = build_context(req)

    # 2. Run all checks (locked: Error blocks export).
    report = run_all_checks(ctx, skipped=req.skipped_checks)

    # 3. Compute export range from clips.
    export_range = compute_export_range(req.clips)
    if export_range is None:
        errors.append("no clips defined")

    # 4. Build the manifest (always, even on failure).
    fbx_preset = req.fbx_preset or FBXExportPreset()

    manifest = Manifest.new(
        tool_version="0.1.0",
        source=Source(
            maya_scene=ctx.scene_name,
            maya_version=_maya_version_str(),
            preset=req.preset.id,
            skeleton_root=req.skeleton_root or ctx.root_joint or "",
        ),
        convention=Convention(
            up_axis=ctx.scene_up_axis,
            unit=ctx.scene_units,
            frame_rate=settings.frame_rate,
            axis_conversion=False,
        ),
        clips=list(req.clips),
        fbx_path=os.path.abspath(req.fbx_path) if req.fbx_path else "",
        ue_destination=UEDestination(
            content_root=req.ue_content_root,
            skeleton_path=req.ue_skeleton_path,
            overwrite_policy=req.overwrite_policy,  # type: ignore[arg-type]
            skeleton_delivery=SkeletonDelivery(
                include_rig=req.include_rig,
                create_if_missing=req.create_skeleton_if_missing,
                import_uniform_scale=req.ue_import_scale,
            ),
        ),
        validation=report.to_summary(),
    )

    # 5. Decide whether to actually export.
    can_export = report.can_export() and export_range is not None and not errors
    fbx_written = False
    thinning: Optional[ThinningResult] = None

    if can_export:
        try:
            if not maya_utils.ensure_fbx_plugin():
                errors.append("FBX 插件加载失败（窗口 → 设置/首选项 → 插件管理器 → 勾上 fbxmaya）")
            else:
                _apply_fbx_preset(fbx_preset)
                start, end = export_range  # type: ignore[misc]
                # 抽稀在 bake 之前作用于场景曲线：FBX 插件内部 bake，不存在
                # 可处理的"bake 副本"。单 undo chunk，Ctrl+Z 一次全恢复。
                if req.thinning_level != "off":
                    thinning = thin_skeleton_curves(
                        req.skeleton_root, (start, end), req.thinning_level,
                    )
                    if thinning is not None:
                        manifest.thinning = {
                            "level": thinning.level,
                            "keys_before": thinning.keys_before,
                            "keys_after": thinning.keys_after,
                        }
                _export_fbx(
                    req.fbx_path,
                    req.skeleton_root,
                    start,
                    end,
                    include_rig=req.include_rig,
                )
                fbx_written = os.path.isfile(os.path.abspath(req.fbx_path))
                if not fbx_written:
                    errors.append(
                        "FBX 导出命令执行了，但没生成文件。"
                        "常见原因：根骨骼没选中、该目录不可写、或所选范围没有可烘焙的动画。"
                    )
        except Exception as exc:
            errors.append(f"FBX 导出出错（{type(exc).__name__}）：{exc}")
            fbx_written = False

    return ExportResult(
        manifest=manifest,
        report=report,
        fbx_written=fbx_written,
        fbx_path=os.path.abspath(req.fbx_path) if req.fbx_path else "",
        export_range=export_range,
        errors=errors,
        thinning=thinning,
    )


def _maya_version_str() -> str:
    try:
        c = maya_utils.cmds()
        return str(c.about(version=True))
    except Exception:
        return ""


__all__ = [
    "ExportRequest",
    "ExportResult",
    "build_context",
    "compute_export_range",
    "export_animation",
]
