from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class PublicationRequest:
    project: str
    asset: str
    version: int

    def validate(self):
        for value in (self.project, self.asset):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
                raise ValueError("发布项目和资产标识必须以字母开头，仅包含字母、数字和下划线")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise ValueError("发布版本必须为正整数")

    def relative_path(self):
        self.validate()
        return f"{self.project}/{self.asset}/v{self.version:03d}"


def file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def data_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def rules_hash(root: str) -> str:
    entries = {}
    for relative in ("config", "mtu_maya/checks", "mtu_maya/core/preset_loader.py", "mtu_maya/core/config.py"):
        path = os.path.join(root, relative)
        paths = [path] if os.path.isfile(path) else [
            os.path.join(directory, name)
            for directory, _, names in os.walk(path)
            for name in names if name.endswith((".py", ".json"))
        ]
        for source in sorted(paths):
            with open(source, "rb") as stream:
                content = stream.read().replace(b"\r\n", b"\n")
            entries[os.path.relpath(source, root).replace("\\", "/")] = hashlib.sha256(content).hexdigest()
    return data_hash(entries)


def validate_publication(data: Dict[str, Any]):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported publication contract")
    PublicationRequest(data.get("project"), data.get("asset"), data.get("revision")).validate()
    for key in ("fbx_sha256", "rules_sha256", "settings_sha256"):
        if not isinstance(data.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", data[key]):
            raise ValueError(f"Invalid publication {key}")
    if not isinstance(data.get("publish_id"), str) or not re.fullmatch(r"[0-9a-f]{32}", data["publish_id"]):
        raise ValueError("Invalid publication ID")
    size = data.get("fbx_size")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("Publication FBX must be nonempty")
    bones = data.get("required_bones")
    if not isinstance(bones, list) or not bones or not all(isinstance(b, str) and b for b in bones):
        raise ValueError("Publication requires bone tracks")
    checks = data.get("required_checks")
    if not isinstance(checks, list) or not checks or not all(isinstance(check, str) and check for check in checks):
        raise ValueError("Publication requires check identities")
    settings = data.get("settings")
    if not isinstance(settings, dict) or data_hash(settings) != data["settings_sha256"]:
        raise ValueError("Publication settings fingerprint mismatch")


def ready_path(manifest_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "ready.json")


def receipt_path(manifest_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "import_receipt.json")


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def verify_package(manifest, manifest_path: str, fbx_path: str):
    publication = manifest.publication
    validate_publication(publication)
    ready = read_json(ready_path(manifest_path))
    if ready.get("publish_id") != publication["publish_id"] or ready.get("manifest_sha256") != file_hash(manifest_path):
        raise ValueError("发布包 manifest 与 ready 不匹配")
    if os.path.getsize(fbx_path) != publication["fbx_size"] or file_hash(fbx_path) != publication["fbx_sha256"]:
        raise ValueError("发布包 FBX 哈希或大小不匹配")
    report = ready.get("report")
    if (not isinstance(report, str) or os.path.basename(report) != report
            or ready.get("report_sha256") != file_hash(os.path.join(os.path.dirname(manifest_path), report))):
        raise ValueError("发布报告缺失或哈希不匹配")
    if manifest.validation.status == "failed" or manifest.validation.skipped or any(r.skipped for r in manifest.validation.results):
        raise ValueError("正式发布不允许失败或跳过检查")
    if set(publication["required_checks"]) != {result.check for result in manifest.validation.results}:
        raise ValueError("正式发布检查记录不完整")
    if not manifest.clips or any(c.end <= c.start for c in manifest.clips):
        raise ValueError("正式发布片段必须有有效时长")
    names = [clip.name for clip in manifest.clips]
    if len(set(name.lower() for name in names)) != len(names) or not all(
            re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) for name in names):
        raise ValueError("正式发布片段名必须唯一且只包含字母、数字和下划线")
    delivery = manifest.ue_destination.skeleton_delivery
    if not manifest.ue_destination.skeleton_path or delivery.include_rig or delivery.create_if_missing:
        raise ValueError("正式发布仅支持已有 Skeleton")
    return ready["manifest_sha256"]
