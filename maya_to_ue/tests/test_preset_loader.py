"""tests.test_preset_loader

Tests for skeleton preset loading and config bundle assembly.

These run without Maya (the loaders are pure-Python). They verify that
the shipped config files parse correctly and that the preset data
classes behave as the validators will expect.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtu_maya.core.preset_loader import (
    DEFAULT_PRESET_IDS,
    NamingConvention,
    PresetRegistry,
    SkeletonPreset,
    default_config_dir,
    get_default_registry,
    load_presets,
    reload_default_registry,
)
from mtu_maya.core.config import (
    ConfigBundle,
    FBXExportPreset,
    PipelineSettings,
    load_all_config,
    load_fbx_preset,
    load_pipeline_settings,
)


class TestShippedPresets(unittest.TestCase):
    """Verify the three presets shipped in config/skeleton_presets.json."""

    @classmethod
    def setUpClass(cls):
        cls.registry = load_presets()

    def test_three_default_presets_loaded(self):
        for pid in DEFAULT_PRESET_IDS:
            self.assertIn(pid, self.registry, f"missing default preset {pid!r}")

    def test_default_order(self):
        self.assertEqual(self.registry.ids(), list(DEFAULT_PRESET_IDS))

    def test_ue_mannequin_fields(self):
        p = self.registry.require("ue_mannequin")
        self.assertEqual(p.display_name, "UE Mannequin")
        self.assertEqual(p.skeleton_type, "humanoid")
        self.assertEqual(p.root_bone, "root")
        self.assertTrue(p.is_humanoid)
        self.assertEqual(p.naming.left_suffix, "_l")
        self.assertEqual(p.naming.right_suffix, "_r")
        self.assertIn("pelvis", p.bone_map)
        self.assertEqual(p.bone_map["thigh_l"], "thigh_l")
        self.assertIn("root", p.required_bones)
        self.assertIn("pelvis", p.required_bones)

    def test_mixamo_fields(self):
        p = self.registry.require("mixamo")
        self.assertEqual(p.display_name, "Mixamo")
        self.assertTrue(p.is_humanoid)
        self.assertEqual(p.root_bone, "Hips")
        self.assertEqual(p.naming.left_suffix, "Left")
        self.assertEqual(p.naming.right_suffix, "Right")
        self.assertEqual(p.bone_map["pelvis"], "Hips")
        self.assertEqual(p.bone_map["thigh_l"], "LeftUpLeg")
        self.assertIn("Hips", p.required_bones)

    def test_custom_preset_is_custom_type(self):
        p = self.registry.require("custom")
        self.assertEqual(p.skeleton_type, "custom")
        self.assertFalse(p.is_humanoid)
        self.assertEqual(p.root_bone, "")
        self.assertEqual(p.bone_map, {})
        self.assertEqual(p.required_bones, [])

    def test_display_names(self):
        names = self.registry.display_names()
        self.assertEqual(names["ue_mannequin"], "UE Mannequin")
        self.assertEqual(names["mixamo"], "Mixamo")
        self.assertEqual(names["custom"], "Custom Skeleton")


class TestNamingConventionRegex(unittest.TestCase):
    """The regex is what the skeleton.naming validator will rely on."""

    def test_ue_mannequin_regex_matches_lowercase(self):
        nc = NamingConvention(naming_regex=r"^[a-z]+(_[a-z0-9]+)*(_l|_r)?$")
        self.assertTrue(nc.matches("pelvis"))
        self.assertTrue(nc.matches("spine_01"))
        self.assertTrue(nc.matches("thigh_l"))
        self.assertTrue(nc.matches("calf_r"))

    def test_ue_mannequin_regex_rejects_bad_names(self):
        nc = NamingConvention(naming_regex=r"^[a-z]+(_[a-z0-9]+)*(_l|_r)?$")
        self.assertFalse(nc.matches("Hips"))          # uppercase
        self.assertFalse(nc.matches("LeftArm"))        # camelcase
        self.assertFalse(nc.matches("bone-01"))        # dash
        self.assertFalse(nc.matches("pelvis extra"))   # space
        self.assertFalse(nc.matches("Pelvis_01"))      # leading uppercase

    def test_mixamo_regex_matches_camelcase(self):
        nc = NamingConvention(naming_regex=r"^(mixamorig[0-9]*:)?[A-Za-z][A-Za-z0-9_]*$")
        self.assertTrue(nc.matches("Hips"))
        self.assertTrue(nc.matches("Spine"))
        self.assertTrue(nc.matches("LeftArm"))
        self.assertTrue(nc.matches("RightUpLeg"))
        # Mixamo prefixes every bone with a namespace on export.
        self.assertTrue(nc.matches("mixamorig:Hips"))
        self.assertTrue(nc.matches("mixamorig1:LeftArm"))

    def test_mixamo_regex_rejects_bad_names(self):
        nc = NamingConvention(naming_regex=r"^(mixamorig[0-9]*:)?[A-Za-z][A-Za-z0-9_]*$")
        self.assertFalse(nc.matches("bone-01"))        # dash
        self.assertFalse(nc.matches("other:Hips"))     # wrong namespace
        self.assertFalse(nc.matches(""))

    def test_empty_regex_always_matches(self):
        nc = NamingConvention(naming_regex="")
        self.assertTrue(nc.matches("anything"))
        self.assertTrue(nc.matches(""))
        self.assertTrue(nc.matches("Hips"))

    def test_invalid_regex_treated_as_no_check(self):
        # A malformed regex in config should not crash; it should degrade
        # gracefully (treat as "no check") so the validator can flag it.
        nc = NamingConvention(naming_regex=r"[unclosed")
        self.assertTrue(nc.matches("anything"))


class TestPresetRegistry(unittest.TestCase):
    def test_register_and_get(self):
        reg = PresetRegistry()
        p = SkeletonPreset(id="x", display_name="X", skeleton_type="custom", root_bone="root")
        reg.register(p)
        self.assertIs(reg.get("x"), p)
        self.assertIn("x", reg)
        self.assertEqual(len(reg), 1)

    def test_require_raises_on_missing(self):
        reg = PresetRegistry()
        with self.assertRaises(KeyError):
            reg.require("nope")

    def test_register_empty_id_rejected(self):
        reg = PresetRegistry()
        with self.assertRaises(ValueError):
            reg.register(SkeletonPreset(id="", display_name="X", skeleton_type="custom", root_bone=""))

    def test_all_orders_defaults_first(self):
        reg = load_presets()
        all_ids = [p.id for p in reg.all()]
        self.assertEqual(all_ids, list(DEFAULT_PRESET_IDS))


class TestConfigLoaders(unittest.TestCase):
    def test_pipeline_settings_from_shipped_file(self):
        s = load_pipeline_settings()
        self.assertEqual(s.frame_rate, 30)
        self.assertEqual(s.overwrite_policy, "rename")
        self.assertEqual(s.default_preset_id, "ue_mannequin")
        self.assertTrue(s.write_markdown_report)
        self.assertEqual(s.log_file_name, "pipeline.log")

    def test_fbx_preset_from_shipped_file(self):
        f = load_fbx_preset()
        self.assertTrue(f.bake_animation)
        self.assertTrue(f.bake_resample_all)
        self.assertEqual(f.bake_step, 1.0)
        # Locked off per design.md §0
        self.assertFalse(f.convert_axis)
        self.assertFalse(f.convert_unit)
        self.assertEqual(f.up_axis, "y")
        self.assertTrue(f.animation_only)
        self.assertFalse(f.include_mesh)
        self.assertFalse(f.include_materials)
        self.assertEqual(f.fbx_version, "")

    def test_load_all_config_bundle(self):
        bundle = load_all_config()
        self.assertIsInstance(bundle, ConfigBundle)
        self.assertIsInstance(bundle.presets, PresetRegistry)
        self.assertIsInstance(bundle.settings, PipelineSettings)
        self.assertIsInstance(bundle.fbx_preset, FBXExportPreset)
        self.assertIn("ue_mannequin", bundle.presets)

    def test_default_config_dir_points_to_repo_config(self):
        cfg = default_config_dir()
        self.assertTrue(cfg.endswith(os.path.join("config", "")) or cfg.endswith("config"))
        self.assertTrue(os.path.isdir(cfg), f"config dir should exist: {cfg}")
        self.assertTrue(os.path.isfile(os.path.join(cfg, "skeleton_presets.json")))


class TestAutoPushSetting(unittest.TestCase):
    """导出后自动推送的开关默认值：缺键即开，显式关才关。"""

    def test_missing_key_defaults_to_enabled(self):
        s = PipelineSettings.from_dict({})
        self.assertTrue(s.auto_push_after_export)

    def test_explicit_false_is_honoured(self):
        s = PipelineSettings.from_dict({"auto_push_after_export": False})
        self.assertFalse(s.auto_push_after_export)

    def test_round_trip_preserves_value(self):
        s = PipelineSettings.from_dict({"auto_push_after_export": False})
        restored = PipelineSettings.from_dict(s.to_dict())
        self.assertFalse(restored.auto_push_after_export)

    def test_shipped_file_enables_it(self):
        self.assertTrue(load_pipeline_settings().auto_push_after_export)


class TestDefaultRegistryCache(unittest.TestCase):
    def test_get_default_registry_returns_same_instance(self):
        r1 = get_default_registry()
        r2 = get_default_registry()
        self.assertIs(r1, r2)

    def test_reload_returns_fresh_instance(self):
        r1 = get_default_registry()
        r2 = reload_default_registry()
        self.assertIsNot(r1, r2)
        self.assertIn("ue_mannequin", r2)


class TestMissingConfigDir(unittest.TestCase):
    """Loading from a nonexistent dir should not crash — graceful empty."""

    def test_load_presets_empty_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            reg = load_presets(tmp)
            self.assertEqual(len(reg), 0)

    def test_pipeline_settings_fallback_to_defaults(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            s = load_pipeline_settings(tmp)
            self.assertEqual(s.frame_rate, 30)  # built-in default

    def test_fbx_preset_fallback_to_defaults(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = load_fbx_preset(tmp)
            self.assertTrue(f.bake_animation)


if __name__ == "__main__":
    unittest.main()
