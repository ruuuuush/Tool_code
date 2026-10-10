"""tests.test_ui

Smoke tests for the UI layer.

The full main window needs a QApplication and ideally a Maya session,
so we test only the pure pieces here:
    - level_icon (string formatter)
    - ClipTableModel (data/edit/flags logic) — runs headless with
      QT_QPA_PLATFORM=offscreen

The model is the highest-risk piece (it holds the clips the exporter
consumes), so we cover it thoroughly: add/remove/edit/checkbox flags.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

# Force headless Qt before importing any PySide6 module.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from bridge.schema import (
    Clip,
    CheckResultEntry,
    Convention,
    ImportResult,
    Manifest,
    Source,
    UEDestination,
    ValidationSummary,
)
from bridge.manifest import write_manifest
from mtu_maya.ui.main_window import ClipTableModel, ExportPanel, level_icon


# Need a QApplication for any Qt model operations.
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _export_result(fbx_written=True, manifest_path="D:/exports/hero_manifest.json",
                   report_path="D:/exports/hero_export_report.md", errors=None):
    """Minimal stand-in for ExportResult — the panel only reads these fields."""
    from mtu_maya.export.fbx_exporter import ExportResult

    return ExportResult(
        manifest=None,
        report=None,
        fbx_written=fbx_written,
        fbx_path="D:/exports/hero.fbx",
        export_range=(1, 90),
        errors=list(errors or []),
        manifest_path=manifest_path,
        report_path=report_path,
    )


class TestLevelIcon(unittest.TestCase):
    def test_passed_always_check(self):
        for level in ("error", "warning", "info"):
            self.assertEqual(level_icon(level, True), "✅")

    def test_failed_icons(self):
        self.assertEqual(level_icon("error", False), "❌")
        self.assertEqual(level_icon("warning", False), "⚠️")
        self.assertEqual(level_icon("info", False), "ℹ️")


class TestClipTableModel(unittest.TestCase):
    def test_empty_model(self):
        m = ClipTableModel()
        self.assertEqual(m.rowCount(), 0)
        self.assertEqual(m.columnCount(), 4)

    def test_set_clips(self):
        m = ClipTableModel()
        m.set_clips([Clip("idle", 1, 10, False), Clip("walk", 11, 30, True)])
        self.assertEqual(m.rowCount(), 2)
        self.assertEqual(m.data(m.index(0, 0)), "idle")
        self.assertEqual(m.data(m.index(0, 1)), "1")
        self.assertEqual(m.data(m.index(0, 2)), "10")
        self.assertEqual(m.data(m.index(1, 0)), "walk")
        self.assertEqual(m.data(m.index(1, 2)), "30")

    def test_header_data(self):
        m = ClipTableModel()
        self.assertEqual(m.headerData(0, QtCore.Qt.Horizontal), "名称")
        self.assertEqual(m.headerData(1, QtCore.Qt.Horizontal), "起始帧")
        self.assertEqual(m.headerData(2, QtCore.Qt.Horizontal), "结束帧")
        self.assertEqual(m.headerData(3, QtCore.Qt.Horizontal), "根运动")
        # Vertical header is the row number (1-based).
        self.assertEqual(m.headerData(0, QtCore.Qt.Vertical), 1)

    def test_root_motion_checkstate(self):
        m = ClipTableModel()
        m.set_clips([Clip("idle", 1, 10, False), Clip("walk", 11, 30, True)])
        # PySide6 enums are real enums; compare against the enum directly.
        self.assertEqual(m.data(m.index(0, 3), QtCore.Qt.CheckStateRole), QtCore.Qt.Unchecked)
        self.assertEqual(m.data(m.index(1, 3), QtCore.Qt.CheckStateRole), QtCore.Qt.Checked)

    def test_edit_name(self):
        m = ClipTableModel()
        m.set_clips([Clip("idle", 1, 10)])
        self.assertTrue(m.setData(m.index(0, 0), "renamed"))
        self.assertEqual(m.clips()[0].name, "renamed")

    def test_edit_start_rejects_garbage(self):
        m = ClipTableModel()
        m.set_clips([Clip("idle", 1, 10)])
        self.assertFalse(m.setData(m.index(0, 1), "abc"))
        # The original value is unchanged.
        self.assertEqual(m.clips()[0].start, 1)

    def test_edit_start_accepts_int_string(self):
        m = ClipTableModel()
        m.set_clips([Clip("idle", 1, 10)])
        self.assertTrue(m.setData(m.index(0, 1), "5"))
        self.assertEqual(m.clips()[0].start, 5)

    def test_toggle_root_motion(self):
        m = ClipTableModel()
        m.set_clips([Clip("idle", 1, 10, False)])
        ok = m.setData(m.index(0, 3), QtCore.Qt.Checked, role=QtCore.Qt.CheckStateRole)
        self.assertTrue(ok)
        self.assertTrue(m.clips()[0].root_motion)

    def test_add_clip(self):
        m = ClipTableModel()
        m.add_clip("new", 1, 5)
        self.assertEqual(m.rowCount(), 1)
        self.assertEqual(m.clips()[0].name, "new")

    def test_remove_row(self):
        m = ClipTableModel()
        m.set_clips([Clip("a", 1, 2), Clip("b", 3, 4)])
        m.remove_row(0)
        self.assertEqual(m.rowCount(), 1)
        self.assertEqual(m.clips()[0].name, "b")

    def test_remove_invalid_row_noop(self):
        m = ClipTableModel()
        m.set_clips([Clip("a", 1, 2)])
        m.remove_row(99)
        self.assertEqual(m.rowCount(), 1)

    def test_flags_root_motion_user_checkable(self):
        m = ClipTableModel()
        m.set_clips([Clip("a", 1, 2)])
        flags = m.flags(m.index(0, 3))
        # PySide6 QFlags support `in` / bitwise ops on enum members directly.
        self.assertTrue(QtCore.Qt.ItemIsUserCheckable & flags)

    def test_flags_name_editable(self):
        m = ClipTableModel()
        m.set_clips([Clip("a", 1, 2)])
        flags = m.flags(m.index(0, 0))
        self.assertTrue(QtCore.Qt.ItemIsEditable & flags)


class TestDeliveryCard(unittest.TestCase):
    """The card is the thing that makes a missing manifest impossible to miss.

    It hangs off the main window, not off the export form: the export button
    lives on the check step, and a result rendered on a page the user isn't
    looking at is no result at all.
    """

    def setUp(self):
        self.win = _main_window()
        self.card = self.win._delivery
        self.addCleanup(self.win.stop_push)

    def test_hidden_before_any_export(self):
        self.assertFalse(self.card.isVisible())

    def test_complete_delivery_marks_every_row_ok(self):
        self.win.show_delivery(_export_result())
        for key in ("fbx", "manifest", "report"):
            self.assertEqual(self.card.rows[key]._dot.text(), "●")
        self.assertIn("交付完成", self.card._header.text())

    def test_missing_manifest_is_not_reported_as_success(self):
        result = _export_result(
            manifest_path="",
            errors=["manifest 写入失败（ValueError）：skeleton_path is required"],
        )
        self.win.show_delivery(result)

        self.assertFalse(result.is_complete())
        self.assertIn("交付不完整", self.card._header.text())
        # The reason travels to the row, not just to pipeline.log.
        self.assertIn("skeleton_path", self.card.rows["manifest"]._detail.text())
        # The FBX row still reports the truth: it did get written.
        self.assertIn("hero.fbx", self.card.rows["fbx"]._detail.text())

    def test_blocked_export_marks_fbx_failed(self):
        self.win.show_delivery(_export_result(fbx_written=False, manifest_path=""))
        self.assertIn("未完成", self.card._header.text())

    def test_blocked_export_shows_the_reason_inline(self):
        # 用户站在第③步看卡片，错误框在第②步——原因必须跟着卡片走。
        result = _export_result(fbx_written=False, manifest_path="",
                                errors=["FBX 插件加载失败（请勾选 fbxmaya）"])
        self.win.show_delivery(result)
        self.assertIn("FBX 插件加载失败", self.card.rows["fbx"]._detail.text())

    def test_report_turned_off_is_pending_not_failed(self):
        self.win.show_delivery(_export_result(report_path=""))
        row = self.card.rows["report"]
        self.assertEqual(row._dot.text(), "○")
        self.assertFalse(row._action.isEnabled())

    def test_open_button_enabled_only_for_written_artifacts(self):
        self.win.show_delivery(_export_result(manifest_path=""))
        self.assertTrue(self.card.rows["fbx"]._action.isEnabled())
        self.assertFalse(self.card.rows["manifest"]._action.isEnabled())


class TestDeliveryCardIsGlobal(unittest.TestCase):
    """Regression: the result used to render on the export-settings page while
    the user stood on the check page, so finishing an export showed nothing."""

    def setUp(self):
        from mtu_maya.ui.main_window import STEP_CHECK, STEP_CLIPS

        self.win = _main_window()
        self.CLIPS, self.CHECK = STEP_CLIPS, STEP_CHECK
        self.addCleanup(self.win.stop_push)

    def test_visible_after_exporting_from_the_check_step(self):
        self.win._go_to_step(self.CHECK)
        self.win.show_delivery(_export_result())
        self.assertTrue(self.win._delivery.isVisibleTo(self.win))

    def test_survives_step_changes(self):
        self.win.show_delivery(_export_result())
        for step in (self.CLIPS, self.CHECK):
            self.win._go_to_step(step)
            self.assertTrue(self.win._delivery.isVisibleTo(self.win))

    def test_card_is_not_inside_any_step_page(self):
        card = self.win._delivery
        for i in range(self.win._pages.count()):
            page = self.win._pages.widget(i)
            self.assertNotIn(card, page.findChildren(type(card)))

    def test_export_panel_no_longer_owns_a_card(self):
        self.assertFalse(hasattr(self.win._export_panel, "_delivery"))


class TestStepBar(unittest.TestCase):
    def setUp(self):
        from mtu_maya.ui import style as T

        self.bar = T.StepBar(["检查", "片段", "导出"])

    def test_starts_on_first_step(self):
        self.assertEqual(self.bar.current(), 0)
        self.assertEqual(self.bar._dots[0]._state, "current")

    def test_set_current_moves_the_ring(self):
        self.bar.set_current(2)
        self.assertEqual(self.bar.current(), 2)
        self.assertEqual(self.bar._dots[2]._state, "current")
        self.assertNotEqual(self.bar._dots[0]._state, "current")

    def test_done_state_survives_moving_away(self):
        self.bar.set_step_state(0, "done")
        self.bar.set_current(1)
        self.assertEqual(self.bar._dots[0]._state, "done")

    def test_current_step_outranks_done_state(self):
        # A completed step you are standing on should still read as "current".
        self.bar.set_step_state(0, "done")
        self.bar.set_current(0)
        self.assertEqual(self.bar._dots[0]._state, "current")

    def test_click_emits_index(self):
        seen = []
        self.bar.step_clicked.connect(lambda i: seen.append(i))
        self.bar._dots[1].parent().mousePressEvent(None)
        self.assertEqual(seen, [1])


class _FakeReport:
    """Stand-in for RunReport — the gate only reads these two lists."""

    def __init__(self, errors=(), warnings=()):
        self.errors = list(errors)
        self.warnings = list(warnings)


def _main_window():
    from mtu_maya.ui.main_window import MainWindow

    return MainWindow()


class TestNoDuplicateTitles(unittest.TestCase):
    """The same section name used to be printed three times over."""

    def _labels(self, widget):
        return [
            w.text()
            for w in widget.findChildren(QtWidgets.QLabel)
            if w.text()
        ]

    def test_clip_panel_has_no_own_title(self):
        from mtu_maya.ui.main_window import ClipTablePanel

        panel = ClipTablePanel()
        self.assertNotIn("动画片段（Clip）", self._labels(panel))

    def test_check_panel_has_no_own_title(self):
        from mtu_maya.ui.main_window import CheckListPanel

        panel = CheckListPanel()
        self.assertNotIn("检查项", self._labels(panel))

    def test_step_names_appear_once_in_the_window(self):
        win = _main_window()
        labels = self._labels(win)
        for name in ("动画片段", "导出"):
            exact = [t for t in labels if t == name]
            self.assertLessEqual(len(exact), 1, f"{name} 出现了 {len(exact)} 次")

    def test_no_step_hint_strings_left(self):
        from mtu_maya.ui import strings as S

        for gone in ("STEP1_HINT", "STEP2_HINT", "STEP3_HINT", "APP_SUBTITLE"):
            self.assertFalse(hasattr(S, gone), f"{gone} 应该已删除")


class TestWizardNavigation(unittest.TestCase):
    def setUp(self):
        from mtu_maya.ui.main_window import STEP_CHECK, STEP_CLIPS, STEP_EXPORT

        self.win = _main_window()
        self.CLIPS, self.EXPORT, self.CHECK = STEP_CLIPS, STEP_EXPORT, STEP_CHECK

    def test_checks_come_last(self):
        # Checks judge the clips and paths entered before them; running them
        # first left a third of the validators with nothing to look at.
        self.assertGreater(self.CHECK, self.CLIPS)
        self.assertGreater(self.CHECK, self.EXPORT)

    def test_step_titles_match_the_page_order(self):
        from mtu_maya.ui import strings as S

        self.assertEqual(S.STEP_TITLES[self.CLIPS], "动画片段")
        self.assertEqual(S.STEP_TITLES[self.EXPORT], "导出设置")
        self.assertEqual(S.STEP_TITLES[self.CHECK], "检查")

    def test_starts_on_clips(self):
        self.assertEqual(self.win._pages.currentIndex(), self.CLIPS)
        self.assertEqual(self.win._step_bar.current(), self.CLIPS)

    def test_step_bar_click_jumps(self):
        self.win._step_bar.step_clicked.emit(self.CHECK)
        self.assertEqual(self.win._pages.currentIndex(), self.CHECK)

    def test_next_and_prev(self):
        self.win._next_btn.click()
        self.assertEqual(self.win._pages.currentIndex(), self.EXPORT)
        self.win._prev_btn.click()
        self.assertEqual(self.win._pages.currentIndex(), self.CLIPS)

    def test_prev_disabled_on_first_step(self):
        self.win._go_to_step(self.CLIPS)
        self.assertFalse(self.win._prev_btn.isEnabled())
        self.assertTrue(self.win._next_btn.isEnabled())

    def test_next_disabled_on_last_step(self):
        self.win._go_to_step(self.CHECK)
        self.assertFalse(self.win._next_btn.isEnabled())
        self.assertTrue(self.win._prev_btn.isEnabled())

    def test_out_of_range_is_clamped(self):
        self.win._go_to_step(99)
        self.assertEqual(self.win._pages.currentIndex(), self.CHECK)
        self.win._go_to_step(-5)
        self.assertEqual(self.win._pages.currentIndex(), self.CLIPS)


class TestNavExportButton(unittest.TestCase):
    """Export settings live on step 2, the verdict on step 3 — the nav bar
    carries a second entry point so passing checks doesn't mean walking back."""

    def setUp(self):
        from mtu_maya.ui.main_window import STEP_CHECK, STEP_CLIPS

        self.win = _main_window()
        self.CLIPS, self.CHECK = STEP_CLIPS, STEP_CHECK

    def test_visible_only_on_check_step(self):
        self.win._go_to_step(self.CHECK)
        self.assertTrue(self.win._nav_export_btn.isVisibleTo(self.win))
        self.win._go_to_step(self.CLIPS)
        self.assertFalse(self.win._nav_export_btn.isVisibleTo(self.win))

    def test_follows_the_gate(self):
        self.win._last_report = _FakeReport(errors=["a"])
        self.win._update_gate()
        self.assertFalse(self.win._nav_export_btn.isEnabled())
        self.assertFalse(self.win._export_panel._gate_open)

        self.win._last_report = _FakeReport()
        self.win._update_gate()
        self.assertTrue(self.win._nav_export_btn.isEnabled())
        self.assertTrue(self.win._export_panel._gate_open)

    def test_click_triggers_the_same_export_signal(self):
        # Detach the real handler first — otherwise the click runs a full
        # export, which without Maya ends in a modal error dialog.
        self.win._export_panel.run_export_requested.disconnect()
        seen = []
        self.win._export_panel.run_export_requested.connect(lambda: seen.append(1))
        self.win._last_report = _FakeReport()
        self.win._update_gate()
        self.win._nav_export_btn.click()
        self.assertEqual(len(seen), 1)


class TestStepProgress(unittest.TestCase):
    def setUp(self):
        from mtu_maya.ui.main_window import STEP_CLIPS, STEP_EXPORT

        self.win = _main_window()
        self.CLIPS, self.EXPORT = STEP_CLIPS, STEP_EXPORT

    def test_clips_step_done_once_a_clip_exists(self):
        self.win._clip_panel.set_clips([Clip("idle", 1, 30, False)])
        self.win._update_step_progress()
        self.assertEqual(self.win._step_bar._states[self.CLIPS], "done")

    def test_clips_step_reverts_when_emptied(self):
        self.win._clip_panel.set_clips([Clip("idle", 1, 30, False)])
        self.win._update_step_progress()
        self.win._clip_panel.set_clips([])
        self.win._update_step_progress()
        self.assertEqual(self.win._step_bar._states[self.CLIPS], "todo")

    def test_export_step_done_when_paths_are_filled(self):
        panel = self.win._export_panel
        panel._fbx_dir.setText("D:/exports")
        panel._fbx_name.setText("hero.fbx")
        panel._ue_root.setText("/Game/Animations")
        self.assertEqual(self.win._step_bar._states[self.EXPORT], "done")

    def test_export_step_incomplete_without_a_filename(self):
        panel = self.win._export_panel
        panel._fbx_dir.setText("D:/exports")
        panel._fbx_name.setText("")
        panel._ue_root.setText("/Game/Animations")
        self.assertEqual(self.win._step_bar._states[self.EXPORT], "todo")


class TestExportGate(unittest.TestCase):
    def setUp(self):
        from mtu_maya.ui.main_window import STEP_CHECK, STEP_CLIPS

        self.win = _main_window()
        self.CLIPS, self.CHECK = STEP_CLIPS, STEP_CHECK
        self.win._go_to_step(self.CHECK)

    def test_blocked_before_checks_run(self):
        self.win._last_report = None
        self.win._update_gate()
        self.assertFalse(self.win._nav_export_btn.isEnabled())
        self.assertIn("检查", self.win._gate_label.text())

    def test_errors_block_export_and_state_the_count(self):
        self.win._last_report = _FakeReport(errors=["a", "b"])
        self.win._update_gate()
        self.assertFalse(self.win._nav_export_btn.isEnabled())
        self.assertIn("2", self.win._gate_label.text())

    def test_warnings_do_not_block(self):
        self.win._last_report = _FakeReport(warnings=["w"])
        self.win._update_gate()
        self.assertTrue(self.win._nav_export_btn.isEnabled())

    def test_clean_report_opens_the_gate(self):
        self.win._last_report = _FakeReport()
        self.win._update_gate()
        self.assertTrue(self.win._nav_export_btn.isEnabled())

    def test_step_bar_marks_the_check_step_done_when_clean(self):
        self.win._last_report = _FakeReport()
        self.win._update_gate()
        self.assertEqual(self.win._step_bar._states[self.CHECK], "done")

    def test_reason_hidden_outside_the_check_step(self):
        self.win._last_report = None
        self.win._go_to_step(self.CLIPS)
        self.assertEqual(self.win._gate_label.text(), "")

    def test_busy_does_not_re_enable_a_closed_gate(self):
        self.win._last_report = _FakeReport(errors=["a"])
        self.win._update_gate()
        self.win._export_panel.set_busy(False, "完成")
        self.assertFalse(self.win._nav_export_btn.isEnabled())

    def test_export_settings_page_has_no_export_button(self):
        # 一个动作一个入口：导出只在检查通过之后，第②步只管填设置。
        panel = self.win._export_panel
        labels = [
            b.text() for b in panel.findChildren(QtWidgets.QPushButton)
        ]
        self.assertNotIn("导出 FBX + Manifest", labels)


class TestSceneWatch(unittest.TestCase):
    """The info bar shows what the checks will judge — it can't lag behind."""

    def setUp(self):
        self.win = _main_window()

    def test_timer_runs_after_construction(self):
        self.assertTrue(self.win._scene_timer.isActive())

    def test_refresh_is_safe_without_maya(self):
        self.win._refresh_scene_info_safe()   # must not raise
        self.assertTrue(self.win._scene_info.text())

    def test_unchanged_scene_does_not_repaint(self):
        self.win._refresh_scene_info_safe()
        cached = self.win._scene_info_text
        calls = []
        self.win._scene_info.setText = lambda t: calls.append(t)
        self.win._refresh_scene_info_safe()
        self.assertEqual(calls, [])
        self.assertEqual(cached, self.win._scene_info_text)

    def test_stale_cache_triggers_a_repaint(self):
        self.win._refresh_scene_info_safe()
        self.win._scene_info_text = "something stale"
        self.win._refresh_scene_info_safe()
        self.assertNotEqual(self.win._scene_info_text, "something stale")

    def test_closing_stops_the_timer(self):
        self.win.close()
        self.assertFalse(self.win._scene_timer.isActive())


class TestLauncherReload(unittest.TestCase):
    """Maya keeps one Python session alive; edits stay invisible without this.

    These drive a throwaway module table — unloading the real one mid-suite
    would re-import the Qt classes and crash the interpreter.
    """

    def setUp(self):
        import launch_maya_tool

        self.launcher = launch_maya_tool
        self.table = {
            "mtu_maya": object(),
            "mtu_maya.ui": object(),
            "mtu_maya.ui.strings": object(),
            "bridge": object(),
            "bridge.schema": object(),
            "os": object(),
            "mtu_maya_lookalike": object(),
        }

    def test_unload_drops_tool_modules(self):
        self.launcher.unload(self.table)
        self.assertNotIn("mtu_maya.ui.strings", self.table)
        self.assertNotIn("bridge.schema", self.table)

    def test_unload_reports_how_many_it_dropped(self):
        self.assertEqual(self.launcher.unload(self.table), 5)

    def test_unload_leaves_unrelated_modules_alone(self):
        self.launcher.unload(self.table)
        self.assertIn("os", self.table)

    def test_unload_does_not_match_on_prefix_alone(self):
        # "mtu_maya_lookalike" merely starts with the package name.
        self.launcher.unload(self.table)
        self.assertIn("mtu_maya_lookalike", self.table)

    def test_unload_on_a_clean_table_is_harmless(self):
        self.launcher.unload(self.table)
        self.assertEqual(self.launcher.unload(self.table), 0)

    def test_reload_and_show_clears_the_cache_before_opening(self):
        # The whole point: show() alone hands back the modules Maya loaded
        # the first time, so reload must drop them first.
        calls = []
        original_unload = self.launcher.unload
        original_show = self.launcher.show
        self.launcher.unload = lambda modules=None: calls.append("unload") or 0
        self.launcher.show = lambda: calls.append("show")
        try:
            self.launcher.reload_and_show()
        finally:
            self.launcher.unload = original_unload
            self.launcher.show = original_show
        self.assertEqual(calls, ["unload", "show"])

    def test_launcher_exposes_reload_and_show(self):
        self.assertTrue(callable(self.launcher.reload_and_show))


class _FakeMayaUtils:
    """Stand-in for mtu_maya.core.maya_utils in fill-range tests."""

    def __init__(self, keys_by_node=None, joints=(), subtree=(), timeline=(1, 120)):
        self.keys_by_node = keys_by_node or {}
        self.joints = list(joints)
        self.subtree = list(subtree)
        self.timeline = timeline
        self.asked = []

    def resolve_joint(self, name):
        for node in self.keys_by_node:
            if node.rsplit("|", 1)[-1] == name:
                return node
        return None

    def subtree_joints(self, root):
        return list(self.subtree)

    def list_joints(self):
        return list(self.joints)

    def keyframe_range(self, nodes):
        self.asked.append(list(nodes))
        found = [t for n in nodes for t in self.keys_by_node.get(n, [])]
        if not found:
            return None
        return int(round(min(found))), int(round(max(found)))

    def timeline_range(self):
        return self.timeline


class TestFillAnimationRange(unittest.TestCase):
    """Fill reads keys off the skeleton — the time slider is a view setting."""

    def setUp(self):
        self.win = _main_window()

    def _preset(self, pelvis="Hips"):
        from mtu_maya.core.preset_loader import SkeletonPreset

        return SkeletonPreset(
            id="t", display_name="T", skeleton_type="humanoid",
            bone_map={"pelvis": pelvis} if pelvis else {},
        )

    def _range(self, fake):
        self.win._current_preset = self._preset()
        candidates = list(self.win._keyframe_candidates(fake))
        for nodes in candidates:
            found = fake.keyframe_range(nodes)
            if found:
                return found
        return fake.timeline_range()

    def test_hips_wins_over_the_timeline(self):
        fake = _FakeMayaUtils(keys_by_node={"|rig|Hips": [0.0, 35.0]}, timeline=(1, 120))
        self.assertEqual(self._range(fake), (0, 35))

    def test_hips_is_tried_first(self):
        fake = _FakeMayaUtils(
            keys_by_node={"|rig|Hips": [0.0, 35.0]},
            joints=["|rig|Hips", "|rig|root"],
        )
        self._range(fake)
        self.assertEqual(fake.asked[0], ["|rig|Hips"])

    def test_falls_back_to_the_selected_root_subtree(self):
        # Root itself has no keys (in-place clip), a child does.
        fake = _FakeMayaUtils(
            keys_by_node={"|rig|root|pelvis": [10.0, 60.0]},
            subtree=["|rig|root", "|rig|root|pelvis"],
        )
        self.win._current_preset = self._preset(pelvis=None)
        self.win._export_panel._root_joint.addItem("root", userData="|rig|root")
        candidates = list(self.win._keyframe_candidates(fake))
        self.assertIn(["|rig|root", "|rig|root|pelvis"], candidates)

    def test_falls_back_to_every_joint(self):
        fake = _FakeMayaUtils(
            keys_by_node={"|other|bone": [3.0, 9.0]},
            joints=["|other|bone"],
        )
        self.win._current_preset = self._preset(pelvis=None)
        candidates = list(self.win._keyframe_candidates(fake))
        self.assertIn(["|other|bone"], candidates)

    def test_no_keys_anywhere_falls_back_to_the_timeline(self):
        fake = _FakeMayaUtils(keys_by_node={}, joints=["|rig|root"], timeline=(1, 48))
        self.assertEqual(self._range(fake), (1, 48))

    def test_real_call_without_maya_returns_a_usable_range(self):
        start, end = self.win._animation_range_from_maya()
        self.assertIsInstance(start, int)
        self.assertIsInstance(end, int)
        self.assertLessEqual(start, end)

    def test_fill_button_adds_a_clip_with_that_range(self):
        panel = self.win._clip_panel
        panel._range_fill = lambda: (0, 35)
        panel.set_clips([])
        panel._on_fill()
        clip = panel.clips()[0]
        self.assertEqual((clip.start, clip.end), (0, 35))


class TestCellEditorFits(unittest.TestCase):
    """The clip-name editor used to come out cropped to a sliver.

    Cause: the global QLineEdit rule carries form-field padding (6px top and
    bottom), so the editor wanted ~34px of height while a table row gave it
    28 — and QTableView::item padding shaved off another 10.
    """

    def setUp(self):
        from mtu_maya.ui import style

        self.win = _main_window()
        # The bug lives in the stylesheet, so the theme has to be on or these
        # assertions pass against unstyled defaults and prove nothing.
        style.apply_theme(self.win)
        panel = self.win._clip_panel
        panel.set_clips([Clip("walk_forward", 0, 35, True)])
        self.view = panel._view
        self.model = panel._model
        self.win.show()
        _APP.processEvents()

    def tearDown(self):
        self.win.close()

    def _editor_for(self, column):
        index = self.model.index(0, column)
        self.view.setCurrentIndex(index)
        self.view.edit(index)
        _APP.processEvents()
        return self.view.viewport().findChild(QtWidgets.QLineEdit)

    def _chrome_height(self, editor):
        """Pixels the editor spends on padding + border, above the text itself.

        This is the number the bug was made of, and unlike raw heights it
        does not move with the font: the global QLineEdit rule carries
        form-field padding (6px top and bottom), pushing the chrome to ~18px
        so the editor needed 34px inside a 30px row. Cell editors must stay
        lean. height() and contentsRect() both ignore stylesheet padding —
        sizeHint is the one that accounts for it.
        """
        return editor.sizeHint().height() - editor.fontMetrics().height()

    _MAX_CHROME = 10   # a thin border plus a couple of px, nothing more

    def test_name_editor_is_not_padded_like_a_form_field(self):
        editor = self._editor_for(0)
        self.assertIsNotNone(editor)
        self.assertLessEqual(
            self._chrome_height(editor), self._MAX_CHROME,
            "编辑框的内边距太厚，行装不下，文字会被裁掉",
        )

    def test_frame_editor_is_not_padded_like_a_form_field(self):
        editor = self._editor_for(1)
        self.assertIsNotNone(editor)
        self.assertLessEqual(self._chrome_height(editor), self._MAX_CHROME)

    def test_editor_fits_the_row_it_lives_in(self):
        editor = self._editor_for(0)
        self.assertLessEqual(editor.sizeHint().height(), self.view.rowHeight(0))

    def test_row_height_clears_the_font(self):
        metrics = self.view.fontMetrics().height()
        self.assertGreater(self.view.rowHeight(0), metrics)

    def test_editor_shows_the_existing_name(self):
        editor = self._editor_for(0)
        self.assertEqual(editor.text(), "walk_forward")


class TestVisualPolish(unittest.TestCase):
    def setUp(self):
        from mtu_maya.ui import style

        self.win = _main_window()
        style.apply_theme(self.win)
        self.addCleanup(self.win.close)
        self.win.show()
        _APP.processEvents()

    def test_publication_controls_require_explicit_identity(self):
        panel = self.win._export_panel
        self.assertIsNone(panel.publication_request())
        panel._include_rig.setChecked(True)
        panel._publish.setChecked(True)
        self.assertFalse(panel._include_rig.isChecked())
        self.assertFalse(panel._include_rig.isEnabled())
        with self.assertRaises(ValueError):
            panel.publication_request()
        panel._publish_project.setText("Demo")
        panel._publish_asset.setText("Hero")
        self.assertEqual(panel.publication_request().relative_path(), "Demo/Hero/v001")
        panel._publish.setChecked(False)
        self.assertTrue(panel._include_rig.isEnabled())

    def test_publication_missing_receipt_does_not_report_success(self):
        from test_publication import package
        with tempfile.TemporaryDirectory() as directory:
            _, path, _ = package(directory)
            self.win._last_manifest_path = path
            outcome = self.win._read_back_import_outcome()
            self.assertEqual(outcome[0], "failed")
            self.assertIn("回执", outcome[1])

    def test_theme_leaves_host_application_unchanged(self):
        from mtu_maya.ui import style

        before = (_APP.styleSheet(), _APP.style(), _APP.font().toString())
        style.apply_theme(self.win)
        after = (_APP.styleSheet(), _APP.style(), _APP.font().toString())
        self.assertEqual(before, after)

    def test_ui_and_code_fonts_are_explicit(self):
        database = QtGui.QFontDatabase if QtCore.qVersion().startswith("6.") else QtGui.QFontDatabase()
        families = set(database.families())
        expected = next((
            family for family in (
                "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI"
            ) if family in families
        ), _APP.font().family())
        self.assertEqual(self.win.font().family(), expected)
        self.assertEqual(self.win.font().pixelSize(), 13)
        self.assertEqual(self.win._export_panel._fbx_name.font().family(), expected)
        self.assertTrue(self.win._delivery._handoff_code.property("codeText"))
        self.assertEqual(self.win._delivery._handoff_code.font().pixelSize(), 12)

    def test_form_fits_default_window(self):
        from mtu_maya.ui.main_window import STEP_EXPORT

        self.win._go_to_step(STEP_EXPORT)
        _APP.processEvents()
        panel = self.win._export_panel
        scroll = self.win._pages.currentWidget().findChild(QtWidgets.QScrollArea)
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.win.rect().contains(panel._overwrite.mapTo(self.win, panel._overwrite.rect().bottomRight())))

    def test_overwrite_labels_keep_internal_keys(self):
        from mtu_maya.ui import strings as S

        panel = self.win._export_panel
        for index, (label, policy) in enumerate(S.OVERWRITE_CHOICES):
            panel._overwrite.setCurrentIndex(index)
            self.assertEqual(panel._overwrite.currentText(), label)
            self.assertEqual(panel.overwrite_policy(), policy)

    def test_checkbox_paints_check_and_partial_mark(self):
        from mtu_maya.ui import style

        checkbox = style.CheckBox()
        style.apply_theme(checkbox)
        checkbox.setTristate(True)
        checkbox.resize(28, 28)
        counts = []
        for state in (QtCore.Qt.Unchecked, QtCore.Qt.Checked, QtCore.Qt.PartiallyChecked):
            checkbox.setCheckState(state)
            image = checkbox.grab().toImage()
            counts.append(sum(
                1 for x in range(image.width()) for y in range(image.height())
                if min(image.pixelColor(x, y).red(), image.pixelColor(x, y).green(), image.pixelColor(x, y).blue()) > 210
            ))
        self.assertEqual(counts[0], 0)
        self.assertGreater(counts[1], 0)
        self.assertGreater(counts[2], 0)

    def test_dropdown_paints_visible_arrow(self):
        from mtu_maya.ui import style

        combo = style.ComboBox()
        combo.addItem("")
        style.apply_theme(combo)
        combo.resize(150, 36)
        option = QtWidgets.QStyleOptionComboBox()
        combo.initStyleOption(option)
        rect = combo.style().subControlRect(
            QtWidgets.QStyle.CC_ComboBox, option, QtWidgets.QStyle.SC_ComboBoxArrow, combo
        )
        image = combo.grab().toImage()
        center = rect.center()
        self.assertTrue(any(
            image.pixelColor(x, y).lightness() > 90
            for x in range(center.x() - 5, center.x() + 6)
            for y in range(center.y() - 4, center.y() + 5)
        ))

    def test_result_rows_have_text_states(self):
        from mtu_maya.checks import CheckResult, RunReport
        from mtu_maya.ui import strings as S

        panel = self.win._check_panel
        ids = list(panel._items_by_id)[:3]
        panel.update_results(RunReport(results=[
            CheckResult(check_id=ids[0], category="scene", level="error", passed=True),
            CheckResult(check_id=ids[1], category="scene", level="warning", passed=False),
            CheckResult(check_id=ids[2], category="scene", level="error", passed=False, skipped=True),
        ]))
        self.assertEqual(panel._items_by_id[ids[0]].text(1), S.STATUS_OK)
        self.assertEqual(panel._items_by_id[ids[1]].text(1), S.LEVEL_LABELS["warning"])
        self.assertEqual(panel._items_by_id[ids[2]].text(1), S.STATUS_SKIPPED)
        self.assertEqual(panel._tree.columnWidth(1), 96)

    def test_detail_escapes_dynamic_message_and_nodes(self):
        from mtu_maya.checks import CheckResult

        message = '<b>root & pelvis</b><img src="missing.png">'
        detail = self.win._detail_panel
        detail.show_result(CheckResult(
            check_id="skeleton.scale", category="skeleton", level="warning",
            passed=False, message=message, details=["<joint> & value"],
        ))
        self.assertIn(message, detail._details.toPlainText())
        self.assertIn("<joint> & value", detail._details.toPlainText())
        self.assertIn("&lt;b&gt;", detail._details.toHtml())

    def test_delivery_scroll_keeps_navigation_visible(self):
        from mtu_maya.ui.main_window import STEP_CHECK

        self.win._go_to_step(STEP_CHECK)
        self.win.show_delivery(_export_result())
        _APP.processEvents()
        self.win._focus_delivery()
        _APP.processEvents()
        nav = self.win._nav_export_btn
        self.assertTrue(self.win.rect().contains(nav.mapTo(self.win, nav.rect().bottomRight())))
        self.assertFalse(self.win._content_scroll.isAncestorOf(nav))
        code_scroll = self.win._delivery._handoff.findChild(QtWidgets.QScrollArea)
        self.assertEqual(code_scroll.height(), 112)
        self.assertTrue(self.win._delivery._copy_btn.isVisibleTo(self.win))


class TestUEHandoff(unittest.TestCase):
    """Maya writes FBX + manifest; UE builds the assets. The card has to say
    so, or users fill in a UE path and go looking for assets that were never
    created."""

    def setUp(self):
        self.win = _main_window()
        self.card = self.win._delivery
        self.addCleanup(self.win.stop_push)

    def test_hidden_before_any_export(self):
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))

    def test_shown_when_delivery_is_complete(self):
        self.win.show_delivery(_export_result())
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))

    def test_hidden_when_manifest_failed(self):
        # UE would have nothing to read; sending the user there earns them
        # an error, not an import.
        self.win.show_delivery(_export_result(manifest_path="", errors=["manifest 写入失败"]))
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))

    def test_hidden_when_export_was_blocked(self):
        self.win.show_delivery(_export_result(fbx_written=False, manifest_path=""))
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))

    def test_snippet_carries_this_run_s_manifest_path(self):
        self.win.show_delivery(
            _export_result(manifest_path="D:/exports/hero_walk_manifest.json")
        )
        self.assertIn(
            "D:/exports/hero_walk_manifest.json", self.card._handoff_code.text()
        )

    def test_snippet_has_no_placeholders_left(self):
        self.win.show_delivery(_export_result())
        code = self.card._handoff_code.text()
        self.assertNotIn("{", code)
        self.assertNotIn("}", code)

    def test_snippet_points_at_the_ue_launcher(self):
        self.win.show_delivery(_export_result())
        code = self.card._handoff_code.text()
        self.assertIn("launch_ue_importer", code)
        self.assertIn("run(", code)

    def test_snippet_includes_the_repo_path(self):
        from mtu_maya.ui.main_window import _repo_root

        self.win.show_delivery(_export_result())
        self.assertIn(_repo_root(), self.card._handoff_code.text())

    def test_copy_puts_the_snippet_on_the_clipboard(self):
        self.win.show_delivery(_export_result())
        self.card._copy_btn.click()
        self.assertEqual(
            QtWidgets.QApplication.clipboard().text(),
            self.card._handoff_code.text(),
        )

    def test_push_button_exists_when_delivery_is_complete(self):
        self.win.show_delivery(_export_result())
        self.assertTrue(self.card._push_btn.isVisibleTo(self.card))
        self.assertTrue(self.card._push_btn.isEnabled())

    def test_push_emits_the_same_snippet(self):
        # Detach the real handler: clicking otherwise fires a live push that
        # spends seconds hunting for an editor on a background thread.
        self.card.push_requested.disconnect()
        seen = []
        self.card.push_requested.connect(lambda code: seen.append(code))
        self.win.show_delivery(_export_result())
        self.card._push_btn.click()
        self.assertEqual(seen, [self.card._handoff_code.text()])

    def test_push_state_starts_hidden(self):
        self.win.show_delivery(_export_result())
        self.assertFalse(self.card._push_status.isVisibleTo(self.card))

    def test_busy_state_disables_the_push_button(self):
        self.win.show_delivery(_export_result())
        self.card.set_push_state("正在推送…", "info", busy=True)
        self.assertFalse(self.card._push_btn.isEnabled())

    def test_failure_keeps_the_manual_route_alive(self):
        # A failed push must never strand the user: the snippet and its copy
        # button are the fallback, and the only route for another machine.
        self.win.show_delivery(_export_result())
        self.card.set_push_state("推送失败：没有发现编辑器", "error")
        self.assertTrue(self.card._copy_btn.isEnabled())
        self.assertTrue(self.card._handoff_code.text())
        self.assertTrue(self.card._push_btn.isEnabled())

    def test_success_state_is_shown(self):
        self.win.show_delivery(_export_result())
        self.card.set_push_state("已在 UE 中导入完成", "ok")
        self.assertTrue(self.card._push_status.isVisibleTo(self.card))
        self.assertIn("完成", self.card._push_status.text())


class _FakeMessageBox(object):
    """模态弹窗会挂住测试进程 —— 换成只记账的替身。"""

    Yes = QtWidgets.QMessageBox.Yes
    No = QtWidgets.QMessageBox.No
    calls = []
    texts = None
    answer = QtWidgets.QMessageBox.Yes

    @classmethod
    def information(cls, *args, **kwargs):
        cls.calls.append("information")

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.calls.append("warning")

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.calls.append("critical")

    @classmethod
    def question(cls, *args, **kwargs):
        cls.calls.append("question")
        if cls.texts is not None and len(args) >= 3:
            cls.texts.append(args[2])
        return cls.answer


class _QtWidgetsShim(object):
    """除 QMessageBox 外一律透传给真的 QtWidgets。"""

    QMessageBox = _FakeMessageBox

    def __getattr__(self, name):
        return getattr(QtWidgets, name)


class TestAutoPushAfterExport(unittest.TestCase):
    """导出的意图就是送进 UE —— 那一次点击不表达任何决策。"""

    def setUp(self):
        from mtu_maya.export import fbx_exporter, manifest_writer
        from mtu_maya.ui import main_window as mw

        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.pushed = []
        self.win._push_to_ue = lambda code: self.pushed.append(code)

        _FakeMessageBox.calls = []
        self.dialogs = _FakeMessageBox.calls

        self._mw, self._fbx, self._mfw = mw, fbx_exporter, manifest_writer
        self._orig = (mw.QtWidgets, fbx_exporter.export_animation,
                      manifest_writer.write_all_artifacts)
        mw.QtWidgets = _QtWidgetsShim()
        manifest_writer.write_all_artifacts = lambda result, write_report=True: None
        self.addCleanup(self._restore)

        self.win._current_preset = object()
        self.win._format_export_summary = lambda result: "已导出"
        self.win._export_panel._fbx_dir.setText("D:/exports")
        self.win._export_panel._fbx_name.setText("hero.fbx")

    def _restore(self):
        self._mw.QtWidgets, self._fbx.export_animation, self._mfw.write_all_artifacts = self._orig

    def _export(self, result=None, report=None):
        """跑一次真实的 _on_export，只把 Maya 导出与检查换成桩。"""
        result = result if result is not None else _export_result()
        self._fbx.export_animation = lambda req: result
        self.win._on_run_checks = lambda: setattr(
            self.win, "_last_report", report if report is not None else _FakeReport()
        )
        self.win._on_export()
        return result

    def test_complete_delivery_pushes_without_a_click(self):
        result = self._export()
        self.assertEqual(self.pushed, [self.win._handoff_code(result)])

    def test_pushed_code_is_the_code_on_screen(self):
        self._export()
        self.assertEqual(self.pushed, [self.win._delivery._handoff_code.text()])

    def test_switch_off_means_no_push(self):
        self.win._export_panel._auto_push.setChecked(False)
        self._export()
        self.assertEqual(self.pushed, [])

    def test_missing_manifest_does_not_push(self):
        self._export(_export_result(manifest_path="", errors=["manifest 写入失败"]))
        self.assertEqual(self.pushed, [])

    def test_blocked_export_does_not_push(self):
        self._export(_export_result(fbx_written=False, manifest_path=""))
        self.assertEqual(self.pushed, [])

    def test_failed_checks_do_not_push(self):
        self._export(report=_FakeReport(errors=["根关节缺失"]))
        self.assertEqual(self.pushed, [])

    def test_push_starts_before_the_modal_dialog(self):
        # 弹窗是模态的：先发车，线程才能趁用户读弹窗时把活干完。
        order = []
        self.win._push_to_ue = lambda code: order.append("push")
        _FakeMessageBox.calls = order
        self._export()
        self.assertEqual(order, ["push", "information"])

    def test_failed_auto_push_leaves_the_export_a_success(self):
        self._export()
        self.assertEqual(self.dialogs, ["information"])
        self.win._on_push_finished(_FakePushResult(ok=False, message="连接未建立"))
        # 导出结论不变，失败只落在卡片上，不再弹第二个窗。
        self.assertEqual(self.dialogs, ["information"])
        self.assertIn("交付完成", self.win._delivery._header.text())
        panel = self.win._export_panel
        self.assertFalse(panel._errors_box.isVisibleTo(panel))

    def test_failed_auto_push_keeps_the_manual_route(self):
        self._export()
        self.win._on_push_finished(
            _FakePushResult(ok=False, message="连接未建立", editor=_FakeEditor())
        )
        card = self.win._delivery
        self.assertIn("推送失败", card._push_status.text())
        self.assertTrue(card._push_btn.isEnabled())
        self.assertTrue(card._copy_btn.isEnabled())


class _FakeEditor(object):
    def describe(self):
        return "UE 5.7 / MyProject"


class TestCheckSkipping(unittest.TestCase):
    """勾选框控制跑不跑；结果刷新不能把用户的选择擦掉。"""

    def setUp(self):
        from mtu_maya.ui.main_window import STEP_CHECK

        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.win._go_to_step(STEP_CHECK)
        self.panel = self.win._check_panel
        self.tree = self.panel._tree

    def _first_two_ids(self):
        return list(self.panel._items_by_id.keys())[:2]

    def _cat_of(self, check_id):
        return self.panel._items_by_id[check_id].parent()

    def test_everything_starts_checked(self):
        self.assertEqual(self.panel.skipped_ids(), set())
        for item in self.panel._items_by_id.values():
            self.assertEqual(item.checkState(0), QtCore.Qt.Checked)

    def test_unchecking_registers_a_skip(self):
        cid = self._first_two_ids()[0]
        self.panel._items_by_id[cid].setCheckState(0, QtCore.Qt.Unchecked)
        self.assertEqual(self.panel.skipped_ids(), {cid})

    def test_category_switch_drives_the_group(self):
        cid = self._first_two_ids()[0]
        cat = self._cat_of(cid)
        cat.setCheckState(0, QtCore.Qt.Unchecked)
        group = [cat.child(i).data(0, QtCore.Qt.UserRole) for i in range(cat.childCount())]
        self.assertTrue(set(group).issubset(self.panel.skipped_ids()))

    def test_partial_group_shows_the_third_state(self):
        cid = self._first_two_ids()[0]
        cat = self._cat_of(cid)
        if cat.childCount() < 2:
            self.skipTest("该分类只有一项，构不成部分选中")
        cat.child(0).setCheckState(0, QtCore.Qt.Unchecked)
        self.assertEqual(cat.checkState(0), QtCore.Qt.PartiallyChecked)

    def test_results_do_not_re_check_a_skipped_row(self):
        cid = self._first_two_ids()[0]
        self.panel._items_by_id[cid].setCheckState(0, QtCore.Qt.Unchecked)
        self.panel.update_results(_report_with_skip(cid))
        self.assertEqual(self.panel._items_by_id[cid].checkState(0), QtCore.Qt.Unchecked)
        self.assertEqual(self.panel.skipped_ids(), {cid})

    def test_skipped_row_shows_no_pass_icon(self):
        cid = self._first_two_ids()[0]
        self.panel.update_results(_report_with_skip(cid))
        self.assertNotEqual(self.panel._items_by_id[cid].text(1), "✅")
        self.assertIn("未执行", self.panel._badge.text())

    def test_detail_says_it_never_ran(self):
        cid = self._first_two_ids()[0]
        report = _report_with_skip(cid)
        self.win._detail_panel.show_result(report.results[0])
        self.assertIn("没有执行", self.win._detail_panel._details.toPlainText())
        self.assertFalse(self.win._detail_panel._fix_btn.isEnabled())


def _report_with_skip(check_id):
    from mtu_maya.checks.registry import CheckResult, RunReport

    return RunReport(results=[
        CheckResult(check_id=check_id, category=check_id.split(".")[0],
                    level="error", passed=False, skipped=True)
    ])


class TestSkipConfirmBeforeExport(unittest.TestCase):
    """拆门可以，但得当着人的面拆。"""

    def setUp(self):
        from mtu_maya.export import fbx_exporter, manifest_writer
        from mtu_maya.ui import main_window as mw

        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.win._push_to_ue = lambda code: None

        _FakeMessageBox.calls = []
        self.dialogs = _FakeMessageBox.calls
        self._mw, self._fbx, self._mfw = mw, fbx_exporter, manifest_writer
        self._orig = (mw.QtWidgets, fbx_exporter.export_animation,
                      manifest_writer.write_all_artifacts)
        mw.QtWidgets = _QtWidgetsShim()
        self.exported = []
        fbx_exporter.export_animation = lambda req: self.exported.append(req) or _export_result()
        manifest_writer.write_all_artifacts = lambda result, write_report=True: None
        self.addCleanup(self._restore)

        self.win._current_preset = object()
        self.win._format_export_summary = lambda result: "已导出"
        self.win._export_panel._fbx_dir.setText("D:/exports")
        self.win._export_panel._fbx_name.setText("hero.fbx")

    def _restore(self):
        self._mw.QtWidgets, self._fbx.export_animation, self._mfw.write_all_artifacts = self._orig

    def _export(self, report):
        self.win._on_run_checks = lambda: setattr(self.win, "_last_report", report)
        self.win._on_export()

    def test_selection_is_carried_in_export_request(self):
        panel = self.win._check_panel
        check_id = next(iter(panel._items_by_id))
        panel._items_by_id[check_id].setCheckState(0, QtCore.Qt.Unchecked)
        self._export(_report_with_skip(check_id))
        self.assertEqual(len(self.exported), 1)
        self.assertEqual(self.exported[0].skipped_checks, {check_id})

    def test_skipped_items_trigger_a_confirmation(self):
        self._export(_report_with_skip("skeleton.naming"))
        self.assertIn("question", self.dialogs)

    def test_no_skips_no_extra_dialog(self):
        self._export(_FakeReport())
        self.assertNotIn("question", self.dialogs)

    def test_declining_stops_the_export(self):
        _FakeMessageBox.answer = _FakeMessageBox.No
        self.addCleanup(setattr, _FakeMessageBox, "answer", _FakeMessageBox.Yes)
        self._export(_report_with_skip("skeleton.naming"))
        self.assertEqual(self.exported, [])

    def test_message_names_the_error_count(self):
        seen = []
        _FakeMessageBox.texts = seen
        self.addCleanup(setattr, _FakeMessageBox, "texts", None)
        self._export(_report_with_skip("skeleton.naming"))
        self.assertTrue(any("1 项属于会阻断导出的错误" in t for t in seen))


class TestDeliveryCollapse(unittest.TestCase):
    """系统自己把活干了，界面就不该再摆"下一步请手动导入"。"""

    def setUp(self):
        from mtu_maya.export import fbx_exporter, manifest_writer
        from mtu_maya.ui import main_window as mw

        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.card = self.win._delivery
        self.win._push_to_ue = lambda code: None

        _FakeMessageBox.calls = []
        self._mw, self._fbx, self._mfw = mw, fbx_exporter, manifest_writer
        self._orig = (mw.QtWidgets, fbx_exporter.export_animation,
                      manifest_writer.write_all_artifacts)
        mw.QtWidgets = _QtWidgetsShim()
        manifest_writer.write_all_artifacts = lambda result, write_report=True: None
        self.addCleanup(self._restore)

        self.win._current_preset = object()
        self.win._format_export_summary = lambda result: "已导出"
        self.win._export_panel._fbx_dir.setText("D:/exports")
        self.win._export_panel._fbx_name.setText("hero.fbx")

    def _restore(self):
        self._mw.QtWidgets, self._fbx.export_animation, self._mfw.write_all_artifacts = self._orig

    def _export(self, result=None):
        result = result if result is not None else _export_result()
        self._fbx.export_animation = lambda req: result
        self.win._on_run_checks = lambda: setattr(self.win, "_last_report", _FakeReport())
        self.win._on_export()
        return result

    def test_auto_push_collapses_the_card(self):
        self._export()
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))
        for row in self.card.rows.values():
            self.assertFalse(row.isVisibleTo(self.card))

    def test_collapsed_card_still_reports_the_push(self):
        self._export()
        self.win._on_push_finished(_FakePushResult(ok=True, message="导入完成", editor=_FakeEditor()))
        self.assertTrue(self.card._push_status.isVisibleTo(self.card))
        self.assertIn("已在 UE 中导入完成", self.card._push_status.text())
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))

    def test_header_stops_saying_import_it_yourself(self):
        # 资产已经进工程了，标题不能还停在"UE 端可以直接导入"。
        self._export()
        self.win._on_push_finished(_FakePushResult(ok=True, editor=_FakeEditor()))
        self.assertIn("已送达 UE", self.card._header.text())

    def test_failed_push_reopens_the_manual_route(self):
        self._export()
        self.win._on_push_finished(
            _FakePushResult(ok=False, message="连接未建立", editor=_FakeEditor())
        )
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))
        self.assertTrue(self.card._push_btn.isVisibleTo(self.card))
        self.assertTrue(self.card._handoff_code.text())

    def test_switch_off_keeps_the_card_open(self):
        self.win._export_panel._auto_push.setChecked(False)
        self._export()
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))
        for row in self.card.rows.values():
            self.assertTrue(row.isVisibleTo(self.card))

    def test_incomplete_delivery_is_never_collapsed(self):
        self._export(_export_result(manifest_path="", errors=["manifest 写入失败"]))
        for row in self.card.rows.values():
            self.assertTrue(row.isVisibleTo(self.card))

    def test_details_button_expands_a_collapsed_card(self):
        self._export()
        self.card._details_btn.click()
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))
        self.assertIn("hero_manifest.json", self.card.rows["manifest"]._detail.text())

    def test_next_export_starts_expanded_again(self):
        self._export()
        self.card.clear()
        self.assertFalse(self.card._collapsed)
        for row in self.card.rows.values():
            self.assertTrue(row.isVisibleTo(self.card))


class TestFormatImportOutcome(unittest.TestCase):
    """纯函数五态：manifest.result → 卡片文案。pending/空 返回 None 走旧文案。"""

    def test_pending_or_none_returns_none(self):
        from mtu_maya.ui.main_window import format_import_outcome
        self.assertIsNone(format_import_outcome(ImportResult(status="pending")))
        self.assertIsNone(format_import_outcome(None))

    def test_success_lists_clips(self):
        from mtu_maya.ui.main_window import format_import_outcome
        status, text = format_import_outcome(
            ImportResult(status="success", imported_clips=["idle", "walk"]))
        self.assertEqual(status, "success")
        self.assertIn("2 个 AnimSequence", text)
        self.assertIn("idle、walk", text)
        self.assertNotIn("骨架", text)  # 复用骨架时不该行

    def test_first_delivery_lists_rig(self):
        from mtu_maya.ui.main_window import format_import_outcome
        status, text = format_import_outcome(ImportResult(
            status="success", imported_clips=["walk"],
            skeleton_path="/Game/Hero/Hero_Skeleton",
            skeletal_mesh_path="/Game/Hero/Hero_SkeletalMesh"))
        self.assertIn("Hero_Skeleton", text)
        self.assertIn("Hero_SkeletalMesh", text)

    def test_partial_lists_skipped(self):
        from mtu_maya.ui.main_window import format_import_outcome
        status, text = format_import_outcome(
            ImportResult(status="partial", imported_clips=["idle"],
                         skipped_clips=["walk"]))
        self.assertEqual(status, "partial")
        self.assertIn("idle", text)
        self.assertIn("跳过 1 个", text)
        self.assertIn("walk", text)

    def test_failed_carries_errors(self):
        from mtu_maya.ui.main_window import format_import_outcome
        status, text = format_import_outcome(
            ImportResult(status="failed", errors=["walk: import failed: boom"]))
        self.assertEqual(status, "failed")
        self.assertIn("walk: import failed: boom", text)


class TestPushReadsBackImportResult(unittest.TestCase):
    """推送成功后卡片报资产清单；读不到 manifest 退回旧文案，不撒谎。"""

    def setUp(self):
        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.card = self.win._delivery

    @staticmethod
    def _manifest_with(result):
        validation = ValidationSummary.from_entries(
            [CheckResultEntry(check="a", level="info", passed=True)])
        return Manifest.new(
            tool_version="0.1.0",
            source=Source(maya_scene="hero.ma", maya_version="2022",
                          preset="ue_mannequin", skeleton_root="root"),
            convention=Convention(up_axis="z", unit="cm", frame_rate=30,
                                  axis_conversion=False),
            clips=[Clip(name="idle", start=1, end=30, root_motion=False)],
            fbx_path="./hero.fbx",
            ue_destination=UEDestination(
                content_root="/Game/Animations/Hero",
                skeleton_path="/Game/Animations/Hero/Hero_Skeleton",
                overwrite_policy="rename"),
            validation=validation,
            result=result,
        )

    def _deliver_and_push(self, manifest_path):
        self.win.show_delivery(_export_result(manifest_path=manifest_path))
        self.win._on_push_finished(_FakePushResult(ok=True, editor=_FakeEditor()))

    def test_success_lists_assets_on_the_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(self._manifest_with(
                ImportResult(status="success", imported_clips=["idle", "walk"])),
                os.path.join(tmp, "hero_manifest.json"))
            self._deliver_and_push(path)
        text = self.card._push_status.text()
        self.assertIn("已在 UE 中导入完成", text)
        self.assertIn("2 个 AnimSequence", text)
        self.assertIn("idle、walk", text)

    def test_first_delivery_card_mentions_rig(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(self._manifest_with(ImportResult(
                status="success", imported_clips=["walk"],
                skeleton_path="/Game/Animations/Hero/Hero_Skeleton")),
                os.path.join(tmp, "hero_manifest.json"))
            self._deliver_and_push(path)
        self.assertIn("Hero_Skeleton", self.card._push_status.text())

    def test_failed_import_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(self._manifest_with(
                ImportResult(status="failed", errors=["walk: boom"])),
                os.path.join(tmp, "hero_manifest.json"))
            self._deliver_and_push(path)
        self.assertIn("导入未成功", self.card._header.text())
        self.assertIn("walk: boom", self.card._push_status.text())
        # 失败时手动路径必须摊开着。
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))

    def test_missing_manifest_falls_back_to_plain_push_ok(self):
        self._deliver_and_push("D:/definitely/not/here.json")
        text = self.card._push_status.text()
        self.assertIn("已在 UE 中导入完成", text)
        self.assertNotIn("AnimSequence", text)

    def test_corrupt_manifest_falls_back_to_plain_push_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hero_manifest.json")
            with open(path, "w", encoding="utf-8") as fp:
                fp.write("not json at all")
            self._deliver_and_push(path)
        text = self.card._push_status.text()
        self.assertIn("已在 UE 中导入完成", text)
        self.assertNotIn("AnimSequence", text)


class TestPushFailureDisplay(unittest.TestCase):
    """失败原因只显示最后一行；整段 traceback 进 tooltip，不许撑爆布局。"""

    def setUp(self):
        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.card = self.win._delivery
        self.win.show_delivery(_export_result())

    def test_traceback_is_cut_to_its_last_line(self):
        tb = ("Traceback (most recent call last):\n"
              '  File "x.py", line 1, in <module>\n'
              "ImportError: cannot import name 'reveal_assets'")
        self.win._on_push_finished(
            _FakePushResult(ok=False, message=tb, editor=_FakeEditor()))
        text = self.card._push_status.text()
        self.assertIn("ImportError: cannot import name 'reveal_assets'", text)
        self.assertNotIn("Traceback", text)
        # 全文不丢：tooltip 里还能看。
        self.assertIn("Traceback", self.card._push_status.toolTip())

    def test_single_line_message_unchanged(self):
        self.win._on_push_finished(
            _FakePushResult(ok=False, message="连接未建立", editor=_FakeEditor()))
        self.assertIn("连接未建立", self.card._push_status.text())

    def test_handoff_code_reloads_launcher(self):
        # 编辑器是长驻进程：推送的代码必须重载 launcher，否则跑的是旧缓存。
        code = self.win._handoff_code(_export_result())
        self.assertIn("importlib.reload(launch_ue_importer)", code)


class TestAutoPushSwitch(unittest.TestCase):
    """开关的初值来自配置，运行期由界面说了算。"""

    def setUp(self):
        self.win = _main_window()
        self.addCleanup(self.win.stop_push)

    def test_defaults_to_on(self):
        self.assertTrue(self.win._export_panel.auto_push())

    def test_reads_the_checkbox(self):
        self.win._export_panel._auto_push.setChecked(False)
        self.assertFalse(self.win._export_panel.auto_push())

    def test_config_off_means_unchecked(self):
        from dataclasses import replace

        self.win._config = replace(
            self.win._config,
            settings=replace(self.win._config.settings, auto_push_after_export=False),
        )
        self.win._apply_export_defaults()
        self.assertFalse(self.win._export_panel.auto_push())

    def test_sits_in_the_ue_handoff_group(self):
        # 它说的是"交付之后怎么送到 UE"，不是导出参数。
        panel = self.win._export_panel
        form = panel.findChild(QtWidgets.QFormLayout)
        rig_row = form.getWidgetPosition(panel._include_rig)[0]
        push_row = form.getWidgetPosition(panel._auto_push)[0]
        self.assertGreater(push_row, rig_row)


class TestThinningControl(unittest.TestCase):
    """抽稀档位：默认关闭，进 ExportRequest，随配置回填。它是本地动作，
    归本地产物组（文件名行之后、UE 交接组之前）。"""

    def setUp(self):
        self.win = _main_window()
        self.addCleanup(self.win.stop_push)

    def test_defaults_to_off(self):
        self.assertEqual(self.win._export_panel.thinning_level(), "off")

    def test_reads_the_combo(self):
        panel = self.win._export_panel
        idx = panel._thinning.findData("medium")
        panel._thinning.setCurrentIndex(idx)
        self.assertEqual(panel.thinning_level(), "medium")

    def test_config_seeds_the_combo(self):
        from dataclasses import replace

        self.win._config = replace(
            self.win._config,
            settings=replace(self.win._config.settings, key_thinning="high"),
        )
        self.win._apply_export_defaults()
        self.assertEqual(self.win._export_panel.thinning_level(), "high")

    def test_sits_in_the_local_output_group(self):
        panel = self.win._export_panel
        form = panel.findChild(QtWidgets.QFormLayout)
        name_row = form.getWidgetPosition(panel._fbx_name)[0]
        thinning_row = form.getWidgetPosition(panel._thinning)[0]
        ue_root_row = form.getWidgetPosition(panel._ue_root)[0]
        self.assertGreater(thinning_row, name_row)
        self.assertGreater(ue_root_row, thinning_row)

    def test_level_reaches_export_request(self):
        panel = self.win._export_panel
        panel._fbx_dir.setText("D:/exports")
        panel._fbx_name.setText("hero.fbx")
        idx = panel._thinning.findData("low")
        panel._thinning.setCurrentIndex(idx)
        # _build_context_from_ui 需要 Maya 场景；这里直接验证面板取值能进
        # ExportRequest 的字段（两处构造点都读 thinning_level()）。
        from mtu_maya.export.fbx_exporter import ExportRequest
        from mtu_maya.core.preset_loader import SkeletonPreset
        req = ExportRequest(
            fbx_path="D:/exports/hero.fbx",
            clips=[Clip("idle", 1, 30)],
            preset=SkeletonPreset(id="custom", display_name="Custom",
                                  skeleton_type="custom"),
            skeleton_root="|root",
            thinning_level=panel.thinning_level(),
        )
        self.assertEqual(req.thinning_level, "low")


class TestCurveCompareWidget(unittest.TestCase):
    """离屏渲染：红蓝两条线都得真的画上。"""

    @staticmethod
    def _panels():
        from mtu_maya.core.curve_thinning import CurvePanel
        before = [(float(t), float(t % 7)) for t in range(60)]
        after = [(0.0, 0.0), (30.0, 2.0), (59.0, 3.0)]
        return [CurvePanel(title="root.translateZ", before=before, after=after,
                           keys_before=60, keys_after=3)]

    def test_paints_both_polylines(self):
        from mtu_maya.ui.curve_plot import CurveCompareWidget
        w = CurveCompareWidget()
        w.set_panels(self._panels())
        w.resize(400, 100)
        img = w.grab().toImage()
        red = blue = 0
        for x in range(0, img.width(), 2):
            for y in range(0, img.height(), 2):
                c = QtGui.QColor(img.pixel(x, y))
                if c.red() > 150 and c.green() < 120 and c.blue() < 140:
                    red += 1
                if c.blue() > 150 and c.red() < 140:
                    blue += 1
        self.assertGreater(red, 0, "原始曲线（红）没画上")
        self.assertGreater(blue, 0, "抽稀后曲线（蓝）没画上")

    def test_empty_panels_hide_the_widget(self):
        from mtu_maya.ui.curve_plot import CurveCompareWidget
        w = CurveCompareWidget()
        w.set_panels(self._panels())
        self.assertFalse(w.isHidden())
        w.set_panels([])
        self.assertTrue(w.isHidden())


class TestDeliveryCardThinningPreview(unittest.TestCase):
    """抽稀证据挂在卡片上：有则显示，收拢不收，没有就不出现。"""

    def setUp(self):
        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.card = self.win._delivery

    @staticmethod
    def _thinned_result():
        from mtu_maya.core.curve_thinning import CurvePanel, ThinningResult
        result = _export_result()
        before = [(float(t), float(t % 5)) for t in range(40)]
        after = [(0.0, 0.0), (39.0, 4.0)]
        result.thinning = ThinningResult(
            level="medium", keys_before=40, keys_after=2, curves_touched=1,
            panels=[CurvePanel(title="root.translateZ", before=before,
                               after=after, keys_before=40, keys_after=2)],
        )
        return result

    def test_preview_shown_when_thinning_ran(self):
        self.win.show_delivery(self._thinned_result())
        self.assertTrue(self.card._curve_preview.isVisibleTo(self.card))

    def test_preview_hidden_without_thinning(self):
        self.win.show_delivery(_export_result())
        self.assertFalse(self.card._curve_preview.isVisibleTo(self.card))

    def test_collapse_keeps_the_preview(self):
        self.win.show_delivery(self._thinned_result())
        self.card.set_collapsed(True)
        self.assertTrue(self.card._curve_preview.isVisibleTo(self.card))

    def test_next_export_without_thinning_resets_it(self):
        self.win.show_delivery(self._thinned_result())
        self.win.show_delivery(_export_result())
        self.assertFalse(self.card._curve_preview.isVisibleTo(self.card))


class TestHandoffRetirement(unittest.TestCase):
    """推送成功 = 手动指引退休；失败或新导出 = 回来。"""

    def setUp(self):
        self.win = _main_window()
        self.addCleanup(self.win.stop_push)
        self.card = self.win._delivery
        self.win.show_delivery(_export_result())

    def test_handoff_visible_before_push(self):
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))

    def test_push_success_retires_the_handoff(self):
        self.win._on_push_finished(_FakePushResult(ok=True, editor=_FakeEditor()))
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))

    def test_retired_handoff_stays_hidden_when_expanding(self):
        self.win._on_push_finished(_FakePushResult(ok=True, editor=_FakeEditor()))
        self.card.set_collapsed(True)
        self.card.set_collapsed(False)   # 用户点「详情」展开
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))

    def test_later_push_failure_brings_it_back(self):
        self.win._on_push_finished(_FakePushResult(ok=True, editor=_FakeEditor()))
        self.assertFalse(self.card._handoff.isVisibleTo(self.card))
        self.win._on_push_finished(
            _FakePushResult(ok=False, message="连接被编辑器关闭", editor=_FakeEditor()))
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))

    def test_new_delivery_resets_retirement(self):
        self.win._on_push_finished(_FakePushResult(ok=True, editor=_FakeEditor()))
        self.win.show_delivery(_export_result())
        self.assertTrue(self.card._handoff.isVisibleTo(self.card))


class _FakePushResult(object):
    """PushResult 的替身 —— 回调只读这几个字段。"""

    def __init__(self, ok, message="", editor=None):
        self.ok = ok
        self.message = message
        self.editor = editor

    def output_text(self):
        return self.message



if __name__ == "__main__":
    unittest.main()
