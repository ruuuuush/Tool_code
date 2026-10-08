"""mtu_maya.ui.main_window

PySide6/PySide2 main window for the Maya→UE animation pipeline tool.

Chinese, dark-themed UI (see style.py / strings.py). All panel classes and
signals keep their previous public API so unit tests remain valid.

Launching inside Maya:
    from mtu_maya.ui import show
    show()
"""

from __future__ import annotations

import os
from html import escape
from typing import List, Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    _QT_BINDING = "PySide6"
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    _QT_BINDING = "PySide2"

from bridge.schema import Clip
from mtu_maya.checks import (
    CheckContext,
    CheckResult,
    RunReport,
    default_registry,
    fix_check,
    fix_all_warnings,
    run_all_checks,
)
from mtu_maya.core.config import (
    ConfigBundle,
    load_all_config,
)
from mtu_maya.core.preset_loader import SkeletonPreset, get_default_registry
from mtu_maya.checks import check_info

from . import strings as S
from . import style as T


# ---------------------------------------------------------------------------
# Icon helpers
# ---------------------------------------------------------------------------

def level_icon(level: str, passed: bool) -> str:
    """Return a unicode glyph for a check result row."""
    if passed:
        return "✅"
    return {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(level, "•")


def format_import_outcome(result) -> "Optional[tuple]":
    """把 UE 回写的 manifest.result 变成卡片文案。

    返回 (status, text)；status 为 "pending"（或 result 为空）时返回 None，
    调用方退回旧的「推送成功」文案。纯函数，不碰 Qt，五态全部可单测。
    """
    if result is None or result.status == "pending":
        return None
    if result.status == "failed":
        reasons = "；".join(result.errors) if result.errors else "原因未知"
        return ("failed", S.IMPORT_FAILED_LINE.format(reasons=reasons))
    lines = []
    if result.imported_clips:
        lines.append(S.IMPORT_CLIPS_LINE.format(
            n=len(result.imported_clips), names="、".join(result.imported_clips)))
    if result.skeleton_path:
        if result.skeletal_mesh_path:
            lines.append(S.IMPORT_RIG_LINE.format(
                skeleton=result.skeleton_path, mesh=result.skeletal_mesh_path))
        else:
            lines.append(S.IMPORT_RIG_LINE_NO_MESH.format(skeleton=result.skeleton_path))
    if result.skipped_clips:
        lines.append(S.IMPORT_SKIPPED_LINE.format(
            n=len(result.skipped_clips), names="、".join(result.skipped_clips)))
    return (result.status, "\n".join(lines))


# ---------------------------------------------------------------------------
# Check list panel
# ---------------------------------------------------------------------------

class CheckListPanel(QtWidgets.QWidget):
    """Left panel: a tree of validators grouped by category with status icons."""

    run_requested = QtCore.Signal()
    fix_selected_requested = QtCore.Signal(str)        # check_id
    fix_all_warnings_requested = QtCore.Signal()
    locate_requested = QtCore.Signal(object)           # CheckResult
    selection_changed = QtCore.Signal(object)          # CheckResult or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results_by_id = {}
        self._items_by_id = {}
        # 本次会话内的跳过选择。刻意不落盘：跳过是临时决定，
        # 不该静静地活到下一个项目。
        self._skipped = set()
        self._syncing = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 面板不写自己的名字：外层的步骤条已经说过一遍了。
        # 表头本身就有"检查/状态"两列，这里只放右侧的统计徽章。
        header = QtWidgets.QHBoxLayout()
        self._badge = T.StatusBadge()
        self._badge.set_state(S.CHECKS_NOT_RUN, "neutral")
        header.addStretch()
        header.addWidget(self._badge)
        layout.addLayout(header)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderLabels([S.COL_CHECK, S.COL_STATUS])
        self._tree.setUniformRowHeights(True)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self._tree.setColumnWidth(1, 96)
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        # 勾选框控制"跑不跑"，与结果无关：勾选变化不该触发重跑，
        # 也不该被下一次结果刷新覆盖。
        self._tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree)

        btn_row = QtWidgets.QHBoxLayout()
        self._run_btn = QtWidgets.QPushButton(S.RUN_CHECKS)
        self._run_btn.setProperty("accent", True)
        self._run_btn.clicked.connect(self.run_requested.emit)
        self._fix_selected_btn = QtWidgets.QPushButton(S.FIX_SELECTED)
        self._fix_selected_btn.setEnabled(False)
        self._fix_selected_btn.clicked.connect(self._emit_fix_selected)
        self._fix_all_btn = QtWidgets.QPushButton(S.FIX_ALL_WARNINGS)
        self._fix_all_btn.setEnabled(False)
        self._fix_all_btn.clicked.connect(self.fix_all_warnings_requested.emit)
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._fix_selected_btn)
        btn_row.addWidget(self._fix_all_btn)
        layout.addLayout(btn_row)

        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

    # -- population ---------------------------------------------------------

    def populate(self, registry):
        """Build the tree from the registry (no results yet)."""
        self._tree.clear()
        self._items_by_id.clear()
        self._results_by_id.clear()
        self._syncing = True
        try:
            self._populate_tree(registry)
        finally:
            self._syncing = False
        self._sync_category_states()

    def _populate_tree(self, registry):
        # Defensive: if the registry is empty (e.g. a module failed to import
        # during an importlib.reload inside Maya), show WHY instead of a blank
        # tree, so the failure is diagnosable instead of silent.
        categories = registry.by_category()
        if not any(categories.values()):
            placeholder = QtWidgets.QTreeWidgetItem(
                ["⚠ 没有加载到任何检查项", ""]
            )
            placeholder.setToolTip(
                0,
                "检查项注册表为空。\n"
                "通常是某个检查模块在 importlib.reload 时导入失败。\n"
                "请查看 Maya 脚本编辑器的历史报错，或直接重启 Maya 后用\n"
                "  from mtu_maya.ui import show; show()\n"
                "重新启动。",
            )
            self._tree.addTopLevelItem(placeholder)
            self._badge.set_state("加载失败", "error")
            return

        for category, validators in categories.items():
            cat_label = S.CATEGORY_NAMES.get(category, category)
            cat_item = QtWidgets.QTreeWidgetItem([cat_label, str(len(validators))])
            f = cat_item.font(0)
            f.setBold(True)
            cat_item.setFont(0, f)
            cat_item.setForeground(0, QtGui.QColor(T.TEXT_DIM))
            cat_item.setFlags(cat_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            cat_item.setCheckState(0, QtCore.Qt.Checked)
            self._tree.addTopLevelItem(cat_item)
            for v in validators:
                # Show the Chinese title as the row label; keep the check id in
                # parentheses-grey so it's still findable. Tooltip explains why.
                title = check_info.title_for(v.id, fallback=v.id)
                zh = check_info.why_for(v.id, fallback=v.description)
                display = title if title == v.id else f"{title}"
                child = QtWidgets.QTreeWidgetItem([display, "—"])
                tip_lines = []
                if title != v.id:
                    tip_lines.append(v.id)
                if zh:
                    tip_lines.append(zh)
                child.setToolTip(0, "\n".join(tip_lines) if tip_lines else v.description)
                child.setData(0, QtCore.Qt.UserRole, v.id)
                child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
                child.setCheckState(
                    0,
                    QtCore.Qt.Unchecked if v.id in self._skipped else QtCore.Qt.Checked,
                )
                cat_item.addChild(child)
                self._items_by_id[v.id] = child
            cat_item.setExpanded(True)
        self._badge.set_state(S.CHECKS_COUNT.format(n=len(self._items_by_id)), "neutral")

    # -- skipping -----------------------------------------------------------

    def skipped_ids(self) -> set:
        """本次不执行的检查 id。跳过状态的唯一读取口。"""
        return set(self._skipped)

    def _on_item_changed(self, item, column):
        if self._syncing or column != 0:
            return
        check_id = item.data(0, QtCore.Qt.UserRole)
        self._syncing = True
        try:
            if check_id is None:
                # 分类行：整组跟着走。用户真正想要的粒度是"骨架那组都不看"。
                state = item.checkState(0)
                if state != QtCore.Qt.PartiallyChecked:
                    for i in range(item.childCount()):
                        item.child(i).setCheckState(0, state)
            self._collect_skipped()
        finally:
            self._syncing = False
        self._sync_category_states()

    def _collect_skipped(self):
        self._skipped = {
            cid
            for cid, it in self._items_by_id.items()
            if it.checkState(0) == QtCore.Qt.Unchecked
        }

    def _sync_category_states(self):
        """分类行三态：全勾 / 全不勾 / 部分。"""
        self._syncing = True
        try:
            for i in range(self._tree.topLevelItemCount()):
                cat = self._tree.topLevelItem(i)
                if cat.childCount() == 0:
                    continue
                checked = sum(
                    1 for c in range(cat.childCount())
                    if cat.child(c).checkState(0) == QtCore.Qt.Checked
                )
                if checked == cat.childCount():
                    cat.setCheckState(0, QtCore.Qt.Checked)
                elif checked == 0:
                    cat.setCheckState(0, QtCore.Qt.Unchecked)
                else:
                    cat.setCheckState(0, QtCore.Qt.PartiallyChecked)
        finally:
            self._syncing = False

    def update_results(self, report: RunReport):
        """Refresh icons/summary from a fresh RunReport."""
        self._results_by_id = {r.check_id: r for r in report.results}
        passed = sum(1 for r in report.results if r.passed and not r.skipped)
        total = len(report.results)
        skipped = len(report.skipped)

        if report.errors:
            kind = "error"
        elif report.warnings:
            kind = "warning"
        else:
            kind = "ok"
        if skipped:
            # 有项没跑就必须说出来，否则 "28/28 通过" 是在骗人。
            text = S.CHECKS_SUMMARY_SKIPPED_FMT.format(
                passed=passed, total=total - skipped, skipped=skipped
            )
        else:
            text = S.CHECKS_SUMMARY_FMT.format(passed=passed, total=total)
        self._badge.set_state(text, kind)
        T.pulse(self._badge)

        self._syncing = True
        for check_id, item in self._items_by_id.items():
            result = self._results_by_id.get(check_id)
            if result is None:
                item.setText(1, "—")
                continue
            if result.skipped:
                item.setText(1, S.SKIPPED_ICON)
                item.setToolTip(1, S.TOOLTIP_SKIPPED)
                item.setForeground(0, QtGui.QColor(T.TEXT_DIM))
                item.setForeground(1, QtGui.QColor(T.TEXT_DIM))
                continue
            item.setText(1, S.STATUS_OK if result.passed else S.LEVEL_LABELS.get(result.level, S.STATUS_FAIL))
            item.setForeground(1, QtGui.QColor(T.OK if result.passed else T.LEVEL_COLORS.get(result.level, T.TEXT)))
            msg = result.message or (S.STATUS_OK if result.passed else S.STATUS_FAIL)
            level_cn = S.LEVEL_LABELS.get(result.level, result.level)
            item.setToolTip(1, S.TOOLTIP_RESULT_FMT.format(level=level_cn, msg=msg))
            if not result.passed:
                item.setForeground(0, QtGui.QColor(T.LEVEL_COLORS.get(result.level, T.TEXT)))
            else:
                item.setForeground(0, QtGui.QColor(T.TEXT))
        self._syncing = False

        has_fixable_warnings = any(
            not r.passed and not r.skipped and r.level == "warning" and r.auto_fixable
            for r in report.results
        )
        self._fix_all_btn.setEnabled(has_fixable_warnings)

    # -- interactions -------------------------------------------------------

    def selected_check_id(self) -> Optional[str]:
        item = self._tree.currentItem()
        if item is None:
            return None
        return item.data(0, QtCore.Qt.UserRole)

    def _on_selection_changed(self):
        check_id = self.selected_check_id()
        if check_id and check_id in self._results_by_id:
            r = self._results_by_id[check_id]
            self._fix_selected_btn.setEnabled(
                r.auto_fixable and not r.passed and not r.skipped
            )
            self.selection_changed.emit(r)          # let the detail panel follow
        else:
            self._fix_selected_btn.setEnabled(False)
            # Emit a bare CheckResult only when we actually have results; if the
            # user clicked a category header (no id), don't blank the panel.
            if check_id is None:
                return
            self.selection_changed.emit(None)

    def _emit_fix_selected(self):
        check_id = self.selected_check_id()
        if check_id:
            self.fix_selected_requested.emit(check_id)

    def _on_double_click(self, item, _column):
        check_id = item.data(0, QtCore.Qt.UserRole)
        if check_id and check_id in self._results_by_id:
            self.locate_requested.emit(self._results_by_id[check_id])


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------

class DetailPanel(QtWidgets.QWidget):
    """Right panel: shows the selected check's details + a fix button."""

    fix_requested = QtCore.Signal(str)  # check_id

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QtWidgets.QLabel(S.DETAIL_SELECT_HINT)
        self._title.setTextFormat(QtCore.Qt.PlainText)
        self._title.setStyleSheet("font-weight: 700; font-size: 13px;")
        layout.addWidget(self._title)

        self._meta = QtWidgets.QLabel("")
        self._meta.setWordWrap(True)
        self._meta.setProperty("dim", True)
        layout.addWidget(self._meta)

        self._details = QtWidgets.QTextEdit()
        self._details.setReadOnly(True)
        self._details.document().setDefaultStyleSheet(
            f"h3 {{ color: {T.TEXT_DIM}; font-size: 12px; margin-top: 12px; margin-bottom: 4px; }}"
            "p { margin-top: 0px; margin-bottom: 8px; }"
        )
        layout.addWidget(self._details)

        self._fix_btn = QtWidgets.QPushButton(S.BTN_FIX)
        self._fix_btn.setEnabled(False)
        self._fix_btn.clicked.connect(self._emit_fix)
        layout.addWidget(self._fix_btn)

        self._current_id: Optional[str] = None
        self._current_fixable = False

    def show_result(self, result: Optional[CheckResult]):
        if result is None:
            self._title.setText(S.DETAIL_SELECT_HINT)
            self._meta.setText("")
            self._details.setText("")
            self._fix_btn.setEnabled(False)
            self._current_id = None
            return

        info = check_info.lookup(result.check_id)
        title = info[0] if info else result.check_id
        self._title.setText(title)

        level_cn = S.LEVEL_LABELS.get(result.level, result.level)
        if result.skipped:
            status = S.DETAIL_STATUS_SKIPPED
        elif result.passed:
            status = S.DETAIL_STATUS_PASSED
        else:
            status = S.DETAIL_STATUS_FAILED.format(level=level_cn)
        fix_info = " · " + S.DETAIL_AUTOFIXABLE if result.auto_fixable else ""
        self._meta.setText(S.DETAIL_META_FMT.format(level=level_cn, fix=fix_info, status=status))

        # Artist-first layout: WHY -> HOW TO PASS -> what the tool found -> id.
        sections = []
        if info and info[1]:
            sections.append((S.DETAIL_WHY_HEADER, info[1]))
        if info and info[2]:
            sections.append((S.DETAIL_HOW_HEADER, info[2]))

        if result.skipped:
            # 不能拿上一次的结论顶替"没跑"这件事。
            found = S.DETAIL_SKIPPED_BODY
        else:
            found = result.message or (S.STATUS_OK if result.passed else S.STATUS_FAIL)
            if result.details:
                found += "\n" + "\n".join(f"- {d}" for d in result.details)
        sections.append((S.DETAIL_DETAILS_HEADER, found))
        body = [
            f"<h3 style='font-size:12px; font-weight:600'>{escape(heading)}</h3>"
            f"<p>{escape(text).replace(chr(10), '<br>')}</p>"
            for heading, text in sections
        ]
        body.append(f"<p style='color:{T.TEXT_DIM}'>{escape(S.DETAIL_CHECK_ID_FMT.format(cid=result.check_id))}</p>")
        self._details.setHtml("".join(body))
        self._details.verticalScrollBar().setValue(0)
        self._current_id = result.check_id
        self._current_fixable = result.auto_fixable and not result.passed and not result.skipped
        self._fix_btn.setEnabled(self._current_fixable)
        T.fade_in(self._details)

    def _emit_fix(self):
        if self._current_id:
            self.fix_requested.emit(self._current_id)


# ---------------------------------------------------------------------------
# Clip table
# ---------------------------------------------------------------------------

class ClipTableModel(QtCore.QAbstractTableModel):
    """Table model backing the clip editor."""

    # Chinese display labels; tests reference these via COLUMNS too.
    COLUMNS = [S.COL_NAME, S.COL_START, S.COL_END, S.COL_ROOT_MOTION]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clips: List[Clip] = []

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._clips)

    def columnCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
            return None
        return section + 1

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._clips)):
            return None
        clip = self._clips[index.row()]
        col = index.column()
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if col == 0:
                return clip.name
            if col == 1:
                return str(clip.start)
            if col == 2:
                return str(clip.end)
        if role in (QtCore.Qt.CheckStateRole,) and col == 3:
            return QtCore.Qt.Checked if clip.root_motion else QtCore.Qt.Unchecked
        if role == QtCore.Qt.TextAlignmentRole:
            if col in (1, 2):
                return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            if col == 3:
                return int(QtCore.Qt.AlignCenter)
        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid() or not (0 <= index.row() < len(self._clips)):
            return False
        clip = self._clips[index.row()]
        col = index.column()
        try:
            if col == 0:
                clip.name = str(value)
            elif col == 1:
                clip.start = int(value)
            elif col == 2:
                clip.end = int(value)
            elif col == 3 and role == QtCore.Qt.CheckStateRole:
                clip.root_motion = (value == QtCore.Qt.Checked)
            else:
                return False
        except (ValueError, TypeError):
            return False
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        base = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if index.column() == 3:
            return base | QtCore.Qt.ItemIsUserCheckable
        return base | QtCore.Qt.ItemIsEditable

    # -- mutation -----------------------------------------------------------

    def set_clips(self, clips: List[Clip]):
        self.beginResetModel()
        self._clips = [Clip(c.name, c.start, c.end, c.root_motion) for c in clips]
        self.endResetModel()

    def clips(self) -> List[Clip]:
        return [Clip(c.name, c.start, c.end, c.root_motion) for c in self._clips]

    def add_clip(self, name: str = S.DEFAULT_CLIP_NAME, start: int = 1, end: int = 30, root_motion: bool = False):
        self.beginInsertRows(QtCore.QModelIndex(), len(self._clips), len(self._clips))
        self._clips.append(Clip(name=name, start=start, end=end, root_motion=root_motion))
        self.endInsertRows()

    def remove_row(self, row: int):
        if 0 <= row < len(self._clips):
            self.beginRemoveRows(QtCore.QModelIndex(), row, row)
            del self._clips[row]
            self.endRemoveRows()


class CenteredCheckDelegate(QtWidgets.QStyledItemDelegate):
    """Draw a checkbox-only column with the box centered and on-theme.

    Qt left-aligns the check indicator and ignores TextAlignmentRole for it,
    which leaves the 根运动 column looking misaligned against its header.
    The native indicator also ignores the QSS written for QCheckBox, so it
    comes out as a bright white square — hence painting it by hand.
    """

    _BOX = 15

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        # Drop Qt's own indicator, or we end up with two check boxes per cell.
        opt.features &= ~QtWidgets.QStyleOptionViewItem.HasCheckIndicator
        style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        checked = index.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked
        rect = QtCore.QRect(0, 0, self._BOX, self._BOX)
        rect.moveCenter(option.rect.center())

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if checked:
            painter.setPen(QtGui.QPen(QtGui.QColor(T.ACCENT), 1))
            painter.setBrush(QtGui.QColor(T.ACCENT))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QtGui.QPen(QtGui.QColor(T.ACCENT_TEXT), 2))
            painter.drawLine(
                rect.left() + 4, rect.center().y(),
                rect.center().x() - 1, rect.bottom() - 4,
            )
            painter.drawLine(
                rect.center().x() - 1, rect.bottom() - 4,
                rect.right() - 3, rect.top() + 4,
            )
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor(T.BORDER), 1))
            painter.setBrush(QtGui.QColor(T.BG_DARKEST))
            painter.drawRoundedRect(rect, 4, 4)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Toggle on click anywhere in the cell — the box is small, the cell isn't."""
        if event.type() == QtCore.QEvent.MouseButtonRelease:
            current = index.data(QtCore.Qt.CheckStateRole)
            new = (
                QtCore.Qt.Unchecked
                if current == QtCore.Qt.Checked
                else QtCore.Qt.Checked
            )
            return model.setData(index, new, QtCore.Qt.CheckStateRole)
        return False


class ClipTablePanel(QtWidgets.QWidget):
    """Clip editor with add/remove and "fill the animation range" buttons."""

    def __init__(self, range_fill_callback=None, parent=None):
        super().__init__(parent)
        self._range_fill = range_fill_callback

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._model = ClipTableModel()
        self._view = QtWidgets.QTableView()
        self._view.setModel(self._model)
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        self._view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.setShowGrid(False)
        self._view.verticalHeader().setDefaultSectionSize(38)
        self._view.verticalHeader().setVisible(False)
        self._view.setColumnWidth(0, 200)
        self._view.setColumnWidth(1, 90)
        self._view.setColumnWidth(2, 90)
        self._view.setColumnWidth(3, 90)
        self._view.setItemDelegateForColumn(3, CenteredCheckDelegate(self._view))
        layout.addWidget(self._view)

        btn_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton(S.BTN_ADD_CLIP)
        add_btn.clicked.connect(self._on_add)
        fill_btn = QtWidgets.QPushButton(S.BTN_FILL_RANGE)
        fill_btn.clicked.connect(self._on_fill)
        rm_btn = QtWidgets.QPushButton(S.BTN_REMOVE_CLIP)
        rm_btn.setProperty("flat", True)
        rm_btn.clicked.connect(self._on_remove)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(fill_btn)
        btn_row.addStretch()
        btn_row.addWidget(rm_btn)
        layout.addLayout(btn_row)

    def _on_add(self):
        self._model.add_clip()

    def _on_fill(self):
        if self._range_fill is not None:
            start, end = self._range_fill()
            self._model.add_clip(name=S.DEFAULT_CLIP_NAME, start=start, end=end)

    def _on_remove(self):
        idx = self._view.currentIndex()
        if idx.isValid():
            self._model.remove_row(idx.row())

    def clips(self) -> List[Clip]:
        return self._model.clips()

    def set_clips(self, clips: List[Clip]):
        self._model.set_clips(clips)


# ---------------------------------------------------------------------------
# Export panel
# ---------------------------------------------------------------------------

class _PushWorker(QtCore.QThread):
    """Run the UE push off the UI thread.

    Discovery and import together can take tens of seconds; doing that on
    the UI thread would freeze Maya. Every wait inside has a ceiling, so
    this thread always terminates.
    """

    finished_with = QtCore.Signal(object)   # PushResult

    def __init__(self, code: str, parent=None):
        super().__init__(parent)
        self._code = code

    def run(self):
        from bridge import ue_remote

        self.finished_with.emit(ue_remote.push(self._code))


def _repo_root() -> str:
    """Absolute path of the repo, for the UE-side sys.path line.

    Derived rather than asked for: the user should not have to retype a
    path the tool already knows.
    """
    here = os.path.dirname(os.path.abspath(__file__))          # mtu_maya/ui
    return os.path.dirname(os.path.dirname(here)).replace("\\", "/")


def _section_label(text: str) -> QtWidgets.QLabel:
    """A group heading inside a form — states where the values below go.

    This is ownership, not instruction: it says who consumes these fields,
    which is exactly what was missing when users expected the export to
    reach into UE by itself.
    """
    label = QtWidgets.QLabel(text)
    label.setProperty("colHead", True)
    label.setContentsMargins(0, 8, 0, 0)
    return label


def _form_label(text: str) -> QtWidgets.QLabel:
    """Dimmed form label — the value the user types should out-read its caption."""
    label = QtWidgets.QLabel(text)
    label.setProperty("dim", True)
    return label


class ExportPanel(QtWidgets.QWidget):
    """Export settings + the big Export button + progress."""

    run_export_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(4)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.addRow(_section_label(S.GROUP_LOCAL_OUTPUT))

        # —— 保存目录（文件夹，不带 .fbx）——
        self._fbx_dir = QtWidgets.QLineEdit()
        self._fbx_dir.setPlaceholderText(S.PH_FBX_DIR)
        browse_btn = QtWidgets.QPushButton(S.BTN_BROWSE)
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._on_browse)
        dir_row = QtWidgets.QHBoxLayout()
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.addWidget(self._fbx_dir)
        dir_row.addWidget(browse_btn)
        form.addRow(_form_label(S.LBL_FBX_DIR), _wrap(dir_row))

        # —— 文件名（才以 .fbx 结尾）——
        self._fbx_name = QtWidgets.QLineEdit()
        self._fbx_name.setPlaceholderText(S.PH_FBX_NAME)
        form.addRow(_form_label(S.LBL_FBX_NAME), self._fbx_name)

        # —— 关键帧抽稀：本地动作，导出前执行，可撤销 ——
        self._thinning = T.ComboBox()
        for label, key in S.THINNING_CHOICES:
            self._thinning.addItem(label, key)
        self._thinning.setToolTip(S.TIP_THINNING)
        form.addRow(_form_label(S.LBL_THINNING), self._thinning)

        self._root_joint = T.ComboBox()
        self._root_joint.setEditable(False)
        form.addRow(_form_label(S.LBL_SKEL_ROOT), self._root_joint)

        # 下面这些不是 Maya 端会执行的动作，而是写进 manifest 的约定，
        # 由 UE 侧导入时读取——分组标题点明去向，免得以为导出就进 UE 了。
        form.addRow(_section_label(S.GROUP_UE_HANDOFF))

        self._ue_root = QtWidgets.QLineEdit("/Game/Animations")
        form.addRow(_form_label(S.LBL_UE_ROOT), self._ue_root)

        self._ue_skeleton_path = QtWidgets.QLineEdit()
        self._ue_skeleton_path.setPlaceholderText(S.PH_UE_SKELETON)
        form.addRow(_form_label(S.LBL_UE_SKELETON), self._ue_skeleton_path)

        # First delivery: ship the rig so UE can build the Skeleton itself.
        self._include_rig = T.CheckBox(S.CHK_INCLUDE_RIG)
        form.addRow(_form_label(S.LBL_INCLUDE_RIG), self._include_rig)

        self._ue_import_scale = QtWidgets.QDoubleSpinBox()
        self._ue_import_scale.setRange(0.001, 10000.0)
        self._ue_import_scale.setDecimals(3)
        self._ue_import_scale.setValue(1.0)
        # 步进箭头在深色主题下只会挤出两个小方块，数值直接键入更干净。
        self._ue_import_scale.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self._ue_import_scale.setToolTip(S.TIP_UE_IMPORT_SCALE)
        self._ue_import_scale.setEnabled(False)
        self._include_rig.toggled.connect(self._ue_import_scale.setEnabled)
        form.addRow(_form_label(S.LBL_UE_IMPORT_SCALE), self._ue_import_scale)

        # 导出的意图就是送进 UE——默认替用户走完最后一步。
        self._auto_push = T.CheckBox(S.CHK_AUTO_PUSH)
        self._auto_push.setChecked(True)
        self._auto_push.setToolTip(S.TIP_AUTO_PUSH)
        form.addRow(_form_label(S.LBL_AUTO_PUSH), self._auto_push)

        self._overwrite = T.ComboBox()
        for label, policy in S.OVERWRITE_CHOICES:
            self._overwrite.addItem(label, policy)
        form.addRow(_form_label(S.LBL_OVERWRITE), self._overwrite)

        layout.addLayout(form)

        # 导出动作只有一个入口，在第③步检查通过之后——这一页只管填设置。
        self._gate_open = True

        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)   # 只在真的在导出时才占位置
        layout.addWidget(self._progress)

        self._status = QtWidgets.QLabel(S.STATUS_READY)
        self._status.setWordWrap(True)
        self._status.setProperty("dim", True)
        layout.addWidget(self._status)

        # 失败原因显示区：平时隐藏，导出失败时列出具体错误。
        self._errors_box = QtWidgets.QLabel("")
        self._errors_box.setWordWrap(True)
        self._errors_box.setProperty("errorText", True)
        self._errors_box.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._errors_box.setVisible(False)
        layout.addWidget(self._errors_box)
        # 交付清单不在这里——它是整次会话的产出，由主窗口常驻展示。
        # 曾经放在本面板里，等导出按钮挪到检查步之后，动作和结果就分到了
        # 两页上，点完导出什么也看不见。
        layout.addStretch()

    def set_status(self, text: str):
        self._status.setText(text)

    def _on_browse(self):
        # 选的是【目录】，不是文件 —— 文件名在下一个框里填。
        start = self._fbx_dir.text().strip() or ""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, S.DIALOG_BROWSE_TITLE, start
        )
        if directory:
            self._fbx_dir.setText(directory)

    # -- accessors ----------------------------------------------------------

    def set_export_enabled(self, allowed: bool):
        """Gate the export action from outside (checks decide, not this panel)."""
        self._gate_open = allowed

    def commit_edits(self):
        """Flush any in-progress typing in editable widgets.

        Editable combo boxes can hold text the user typed but never committed
        (no Enter / focus-out). Reading them before a check run must force the
        pending text through, otherwise a manually-typed value is silently
        dropped and the check still sees the old value.
        """
        for combo in (self._overwrite,):
            if combo.isEditable():
                le = combo.lineEdit()
                if le is not None:
                    combo.setCurrentText(le.text())

    def fbx_path(self) -> str:
        """完整导出路径 = 保存目录 + 文件名。

        文件名没带 .fbx 后缀时自动补上 —— 用户只填名字（walk），
        工具负责存成 walk.fbx，不把后缀当用户要自己管的事。
        目录或名字任一空就返回空串（交给检查项提示"还没设置"）。
        """
        directory = self._fbx_dir.text().strip()
        name = self._fbx_name.text().strip()
        if not directory or not name:
            return ""
        if not name.lower().endswith(".fbx"):
            name += ".fbx"
        return os.path.join(directory, name)

    def set_fbx_path(self, path: str):
        """把一条完整路径拆回【目录】和【文件名】两个框。"""
        path = (path or "").strip()
        if not path:
            self._fbx_dir.setText("")
            self._fbx_name.setText("")
            return
        self._fbx_dir.setText(os.path.dirname(path))
        self._fbx_name.setText(os.path.basename(path))

    def ue_root(self) -> str:
        return self._ue_root.text().strip()

    def ue_skeleton_path(self) -> str:
        return self._ue_skeleton_path.text().strip()

    def include_rig(self) -> bool:
        return self._include_rig.isChecked()

    def ue_import_scale(self) -> float:
        return float(self._ue_import_scale.value())

    def auto_push(self) -> bool:
        return self._auto_push.isChecked()

    def thinning_level(self) -> str:
        """当前抽稀档位的内部 key：off/low/medium/high。"""
        return self._thinning.currentData() or "off"

    def overwrite_policy(self) -> str:
        return self._overwrite.currentData()

    def skeleton_root(self) -> str:
        """当前选中关节的【长路径】（存 userData 里）。没选就空串。"""
        data = self._root_joint.currentData()
        return (data or "").strip()

    def set_joint_options(self, joints: List[str]):
        """填充下拉：显示短名（Hips），userData 存长路径（|Hips）。

        把根关节（没有关节父级、层级最浅）排最前面并默认选中，
        让制作人员一眼看到该选哪个，不用自己翻一长串。
        """
        prev = self.skeleton_root()
        self._root_joint.clear()
        # 层级从浅到深排序：根排最前。
        ordered = sorted(joints, key=lambda j: (j.count("|"), j))
        for j in ordered:
            short = j.rsplit("|", 1)[-1]
            depth = j.count("|") - 1  # |Hips -> 0, |Hips|Spine -> 1
            indent = "　" * min(depth, 6)  # 全角空格做层级缩进
            self._root_joint.addItem(f"{indent}{short}", userData=j)
        # 恢复之前选的；否则默认选第一项（= 根）。
        if prev:
            idx = self._root_joint.findData(prev)
            if idx >= 0:
                self._root_joint.setCurrentIndex(idx)
                return
        if self._root_joint.count() > 0:
            self._root_joint.setCurrentIndex(0)

    def set_busy(self, busy: bool, status: str = ""):
        self._progress.setVisible(busy)
        self._progress.setRange(0, 0 if busy else 1)
        if not busy:
            self._progress.setValue(1)
        if status:
            self._status.setText(status)
        if busy:
            self.clear_errors()  # 开始新一轮导出时清掉上次的错误

    def show_errors(self, reasons: List[str]):
        """在导出面板里列出失败原因（可选中复制）。空列表 -> 显示兜底提示。"""
        lines = [r for r in (reasons or []) if r and r.strip()]
        if lines:
            body = "\n".join(f"• {r}" for r in lines)
        else:
            body = S.MSG_EXPORT_NO_REASON
        self._errors_box.setText(f"{S.EXPORT_ERRORS_HEADER}\n{body}")
        self._errors_box.setVisible(True)

    def clear_errors(self):
        self._errors_box.setText("")
        self._errors_box.setVisible(False)

    def reset_progress(self):
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._status.setText(S.STATUS_READY)
        self.clear_errors()


def _wrap(widget) -> QtWidgets.QWidget:
    """Wrap a layout/widget so QFormLayout accepts it as a row."""
    if isinstance(widget, QtWidgets.QLayout):
        w = QtWidgets.QWidget()
        w.setLayout(widget)
        return w
    return widget


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

# Wizard step indices. Named because the order carries meaning: checks run
# LAST, since their verdict depends on the clips and paths entered before.
# Referring to them by number is what let the order silently drift once.
STEP_CLIPS = 0
STEP_EXPORT = 1
STEP_CHECK = 2
STEP_COUNT = 3


class MainWindow(QtWidgets.QMainWindow):
    """Top-level tool window. Owns the config bundle and orchestrates panels."""

    def __init__(self, config: Optional[ConfigBundle] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(S.WINDOW_TITLE)
        self.setMinimumSize(860, 600)
        self.resize(1040, 760)

        self._config = config or load_all_config()
        self._registry = default_registry()
        self._preset_registry = get_default_registry()
        self._current_preset: Optional[SkeletonPreset] = None

        self._build_ui()
        self._connect_signals()
        self._initial_state()

    # -- construction -------------------------------------------------------

    def _build_ui(self):
        central = QtWidgets.QWidget()
        shell = QtWidgets.QVBoxLayout(central)
        shell.setContentsMargins(18, 14, 18, 14)
        shell.setSpacing(12)
        content = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)
        # 交付卡片的高度随结果内容变化（失败详情、资产清单）。超高时给内容
        # 一个滚动条兜底，导航固定在内容之外。
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        self._content_scroll = scroll
        shell.addWidget(scroll, stretch=1)
        self.setCentralWidget(central)

        # ---- Header: product title + preset picker -------------------------
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Maya → UE 动画交付")
        title.setProperty("h1", True)
        title_row.addWidget(title)
        title_row.addStretch()

        preset_lbl = QtWidgets.QLabel(S.SKELETON_PRESET)
        preset_lbl.setProperty("dim", True)
        title_row.addWidget(preset_lbl)
        self._preset_combo = T.ComboBox()
        self._preset_combo.setMinimumWidth(200)
        for p in self._preset_registry.all():
            self._preset_combo.addItem(p.display_name, userData=p.id)
        title_row.addWidget(self._preset_combo)
        reload_btn = QtWidgets.QPushButton(S.RELOAD_CONFIG)
        reload_btn.setProperty("flat", True)
        reload_btn.clicked.connect(self._reload_config)
        title_row.addWidget(reload_btn)
        outer.addLayout(title_row)

        # ---- Scene status bar (always visible) ------------------------------
        scene_bar = QtWidgets.QFrame()
        scene_bar.setProperty("statusBar", True)
        sb = QtWidgets.QHBoxLayout(scene_bar)
        sb.setContentsMargins(12, 8, 12, 8)
        self._scene_info = QtWidgets.QLabel(S.SCENE_NOT_READ)
        self._scene_info.setTextFormat(QtCore.Qt.PlainText)
        self._scene_info.setWordWrap(True)
        self._scene_info.setProperty("dim", True)
        sb.addWidget(self._scene_info, stretch=1)
        outer.addWidget(scene_bar)

        # ---- Step bar: the only place step names appear ---------------------
        self._step_bar = T.StepBar(S.STEP_TITLES)
        self._step_bar.step_clicked.connect(self._go_to_step)
        outer.addWidget(self._step_bar)

        # ---- Pages: clips → export settings → checks -------------------------
        # Checks last: they judge the clips and paths entered above them.
        self._pages = QtWidgets.QStackedWidget()
        self._check_panel = CheckListPanel()
        self._detail_panel = DetailPanel()
        self._clip_panel = ClipTablePanel(range_fill_callback=self._animation_range_from_maya)
        self._export_panel = ExportPanel()

        self._pages.addWidget(self._build_clip_page())     # STEP_CLIPS
        self._pages.addWidget(self._build_export_page())   # STEP_EXPORT
        self._pages.addWidget(self._build_check_page())    # STEP_CHECK
        outer.addWidget(self._pages, stretch=1)

        # ---- Delivery result: session-level, not part of any step -----------
        # It used to live inside the export form. Once the export button moved
        # to the check step, the action and its result sat on different pages
        # and finishing an export showed nothing at all. The result belongs to
        # the session, so it hangs beside the pages rather than inside one.
        self._delivery = T.DeliveryCard(S.DELIVERY_TITLES)
        self._delivery.open_requested.connect(self._reveal_path)
        self._delivery.copy_requested.connect(self._copy_to_clipboard)
        self._delivery.push_requested.connect(self._push_to_ue)
        self._push_worker = None
        self._last_manifest_path = ""
        outer.addWidget(self._delivery)

        # ---- Bottom nav ------------------------------------------------------
        nav = QtWidgets.QFrame()
        nav.setProperty("navBar", True)
        nav_lay = QtWidgets.QHBoxLayout(nav)
        nav_lay.setContentsMargins(12, 9, 12, 9)
        nav_lay.setSpacing(8)

        self._gate_label = QtWidgets.QLabel("")
        self._gate_label.setWordWrap(True)
        self._gate_label.setProperty("gate", True)
        nav_lay.addWidget(self._gate_label, stretch=1)
        nav_lay.addStretch()

        self._prev_btn = QtWidgets.QPushButton(S.NAV_PREV)
        self._prev_btn.setProperty("ghost", True)
        self._prev_btn.clicked.connect(lambda: self._go_to_step(self._pages.currentIndex() - 1))
        self._next_btn = QtWidgets.QPushButton(S.NAV_NEXT)
        self._next_btn.setProperty("ghost", True)
        self._next_btn.clicked.connect(lambda: self._go_to_step(self._pages.currentIndex() + 1))
        nav_lay.addWidget(self._prev_btn)
        nav_lay.addWidget(self._next_btn)

        # 导出设置在第②步，但检查结果在第③步。通过检查后还要退回一步才能
        # 按导出太蠢，所以检查步的导航条上直接给一个同样的入口。
        self._nav_export_btn = QtWidgets.QPushButton(S.BTN_EXPORT)
        self._nav_export_btn.setProperty("accent", True)
        self._nav_export_btn.clicked.connect(self._export_panel.run_export_requested.emit)
        self._nav_export_btn.setVisible(False)
        nav_lay.addWidget(self._nav_export_btn)
        shell.addWidget(nav)

        self._apply_export_defaults()
        self._go_to_step(0)

        # Menu
        menu = self.menuBar().addMenu(S.MENU_TOOLS)
        action_class = QtGui.QAction if _QT_BINDING == "PySide6" else QtWidgets.QAction
        view_log = action_class(S.MENU_OPEN_EXPORT_FOLDER, self)
        view_log.triggered.connect(self._open_export_folder)
        menu.addAction(view_log)

    # -- page builders ------------------------------------------------------

    @staticmethod
    def _panel(widget, margins=(12, 12, 12, 12)) -> QtWidgets.QFrame:
        """Wrap content in an untitled card. The step bar names the section."""
        frame = QtWidgets.QFrame()
        frame.setProperty("panel", True)
        lay = QtWidgets.QVBoxLayout(frame)
        lay.setContentsMargins(*margins)
        lay.addWidget(widget)
        return frame

    def _build_check_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)
        split.addWidget(self._panel(self._check_panel))
        split.addWidget(self._panel(self._detail_panel))
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([600, 400])
        lay.addWidget(split)
        return page

    def _build_clip_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._panel(self._clip_panel))
        return page

    def _build_export_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        host = QtWidgets.QWidget()
        host_lay = QtWidgets.QVBoxLayout(host)
        host_lay.setContentsMargins(0, 0, 0, 0)
        host_lay.addWidget(self._panel(self._export_panel))
        host_lay.addStretch()   # 表单顶对齐，不被拉成一整屏
        scroll.setWidget(host)
        lay.addWidget(scroll)
        return page

    def _apply_export_defaults(self):
        default_export_dir = self._config.settings.fbx_export_dir
        if default_export_dir:
            self._export_panel._fbx_dir.setText(default_export_dir)
        self._export_panel._ue_root.setText(self._config.settings.ue_content_root)
        policy_index = self._export_panel._overwrite.findData(self._config.settings.overwrite_policy)
        if policy_index >= 0:
            self._export_panel._overwrite.setCurrentIndex(policy_index)
        self._export_panel._auto_push.setChecked(
            self._config.settings.auto_push_after_export
        )
        thinning_index = self._export_panel._thinning.findData(
            self._config.settings.key_thinning
        )
        if thinning_index >= 0:
            self._export_panel._thinning.setCurrentIndex(thinning_index)

    # -- delivery result ----------------------------------------------------

    @staticmethod
    def _handoff_code(result) -> str:
        """UE 侧要跑的那段导入代码。自动推送与交接区共用，保证推的就是看到的。"""
        return S.HANDOFF_CODE.format(repo=_repo_root(), manifest=result.manifest_path)

    def show_delivery(self, result) -> None:
        """把这次导出的三个产物逐项摊开：写没写出来、在哪、为什么没有。"""
        card = self._delivery
        # 推送成功后回读导入结果要用它；推送与交付看的是同一份 manifest。
        self._last_manifest_path = result.manifest_path or ""
        # 抽稀证据就地可见：卡片收拢也不收它。
        card.set_thinning_panels(
            result.thinning.panels if result.thinning else []
        )

        if result.fbx_written:
            card.rows["fbx"].set_state("ok", result.fbx_path, result.fbx_path)
        else:
            # 失败原因必须就地说——「见下方原因」指向的是第②步的错误框，
            # 而导出后人站在第③步，那个承诺永远兑现不了。
            fbx_error = next((e for e in (result.errors or []) if e), "")
            card.rows["fbx"].set_state("failed", fbx_error or S.DELIVERY_BLOCKED)

        manifest_error = next(
            (e for e in (result.errors or []) if "manifest" in e), ""
        )
        if result.manifest_path:
            card.rows["manifest"].set_state(
                "ok", result.manifest_path, result.manifest_path
            )
        else:
            card.rows["manifest"].set_state(
                "failed", manifest_error or S.DELIVERY_NOT_WRITTEN
            )

        report_error = next(
            (e for e in (result.errors or []) if "报告" in e), ""
        )
        if result.report_path:
            card.rows["report"].set_state("ok", result.report_path, result.report_path)
        elif report_error:
            card.rows["report"].set_state("failed", report_error)
        else:
            card.rows["report"].set_state("pending", S.DELIVERY_SKIPPED)

        if result.is_complete():
            card.set_header(S.DELIVERY_OK, "ok")
            # 只有交付齐全才引导去 UE：缺 manifest 时 UE 侧无从读起，
            # 让用户跑一趟拿个报错只会更糊涂。
            card.set_handoff(
                S.HANDOFF_TITLE,
                self._handoff_code(result),
                S.HANDOFF_COPY,
                S.HANDOFF_PUSH,
            )
        elif result.fbx_written:
            card.set_header(S.DELIVERY_PARTIAL, "error")
            card.hide_handoff()
        else:
            card.set_header(S.DELIVERY_FAILED, "error")
            card.hide_handoff()
        # 不做淡入：这块是交付结果，不能因为动画没跑完就看不见。
        card.setVisible(True)
        QtCore.QTimer.singleShot(0, self._focus_delivery)

    def _focus_delivery(self):
        if self._delivery.isVisibleTo(self):
            self._content_scroll.ensureWidgetVisible(self._delivery)

    def _reveal_path(self, path: str):
        """在系统文件管理器里打开该产物所在目录。"""
        folder = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(folder):
            return
        try:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
        except Exception:
            pass

    def _copy_to_clipboard(self, text: str):
        if not text:
            return
        QtWidgets.QApplication.clipboard().setText(text)
        self._export_panel.set_status(S.HANDOFF_COPIED)

    def _push_to_ue(self, code: str):
        if not code or (self._push_worker and self._push_worker.isRunning()):
            return
        self._delivery.set_push_state(S.PUSH_BUSY, "info", busy=True)
        QtCore.QTimer.singleShot(0, self._focus_delivery)
        worker = _PushWorker(code, self)
        worker.finished_with.connect(self._on_push_finished)
        self._push_worker = worker
        worker.start()

    def _read_back_import_outcome(self):
        """回读本次 manifest 的 result 字段。任何失败都返回 None，走旧文案。

        推送是同步语义：ue_remote 返回时 UE 侧 run() 已结束、result 已落盘。
        """
        if not self._last_manifest_path:
            return None
        try:
            from bridge.manifest import read_manifest
            return format_import_outcome(read_manifest(self._last_manifest_path).result)
        except Exception:
            return None

    def _on_push_finished(self, result):
        self._push_worker = None
        QtCore.QTimer.singleShot(0, self._focus_delivery)
        if result.ok:
            editor = result.editor.describe() if result.editor else ""
            outcome = self._read_back_import_outcome()
            if outcome is not None and outcome[0] == "failed":
                # 推送到了但导入砸了：「已送达」不能写成「资产已就位」，
                # 卡片摊开，手动路径留着。
                self._delivery.set_collapsed(False)
                self._delivery.restore_handoff()
                self._delivery.set_header(S.DELIVERY_IMPORT_FAILED, "error")
                self._delivery.set_push_state(outcome[1], "error")
                self._export_panel.set_status(outcome[1])
                return
            # 已经进 UE 了，标题不能还停在"可以直接导入"。
            # 推送成功 = 系统已办完，"下一步请手动导入"的指引退休；
            # 之后推送失败或新一轮导出，它会自己回来。
            self._delivery.retire_handoff()
            self._delivery.set_header(S.DELIVERY_PUSHED, "ok")
            push_text = S.PUSH_OK.format(editor=editor)
            if outcome is not None and outcome[1]:
                push_text = push_text + "\n" + outcome[1]
            self._delivery.set_push_state(push_text, "ok")
            self._export_panel.set_status(
                result.output_text() or S.PUSH_OK.format(editor=editor)
            )
            return
        # 失败只是失败——代码块和复制按钮还在，手动那条路一直通。
        # 收拢是"系统已经办完"的形态；办砸了就得把手动路径重新摊开。
        self._delivery.set_collapsed(False)
        # 上一轮推送可能成功过并把交接区退休了；这次失败，手动路径得回来。
        self._delivery.restore_handoff()
        if result.editor is None:
            self._delivery.set_push_state(S.PUSH_NO_EDITOR, "error")
        else:
            # 编辑器回传的可能是一整段 traceback：真正的错误在最后一行，
            # 全文放进 tooltip。多行标签会把卡片撑到看不见页面。
            lines = [ln for ln in (result.message or "").strip().splitlines() if ln.strip()]
            short = lines[-1].strip() if lines else "未知原因"
            self._delivery.set_push_state(
                S.PUSH_FAILED.format(reason=short), "error",
                tooltip=result.message or "",
            )

    def stop_push(self):
        """Wait for any in-flight push before the window goes away.

        The worker holds sockets and emits back into these widgets; letting
        it outlive them crashes the interpreter on shutdown.
        """
        worker = self._push_worker
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        self._push_worker = None

    # -- navigation ---------------------------------------------------------

    def _go_to_step(self, index: int):
        index = max(0, min(index, self._pages.count() - 1))
        self._pages.setCurrentIndex(index)
        self._content_scroll.verticalScrollBar().setValue(0)
        self._step_bar.set_current(index)
        self._prev_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < self._pages.count() - 1)
        self._nav_export_btn.setVisible(index == STEP_CHECK)
        self._update_step_progress()
        self._update_gate()

    # -- export gate --------------------------------------------------------

    def _update_step_progress(self):
        """Mark the first two steps done once they hold usable input.

        Lets the step bar answer "what's still missing" without the user
        having to walk into each step to find out.
        """
        has_clips = bool(self._clip_panel.clips())
        self._step_bar.set_step_state(STEP_CLIPS, "done" if has_clips else "todo")

        paths_ready = all([
            self._export_panel._fbx_dir.text().strip(),
            self._export_panel._fbx_name.text().strip(),
            self._export_panel._ue_root.text().strip(),
        ])
        self._step_bar.set_step_state(STEP_EXPORT, "done" if paths_ready else "todo")

    def _update_gate(self):
        """Single place that decides whether exporting is allowed, and says why.

        Every event that can change the answer routes through here so the
        button state, the reason text and the step bar can never disagree.
        """
        report = getattr(self, "_last_report", None)
        if report is None:
            allowed, text = False, S.GATE_NOT_RUN
        elif report.errors:
            allowed, text = False, S.GATE_BLOCKED.format(n=len(report.errors))
        elif report.warnings:
            allowed, text = True, S.GATE_READY_WARN.format(n=len(report.warnings))
        else:
            allowed, text = True, S.GATE_READY

        self._export_panel.set_export_enabled(allowed)
        self._nav_export_btn.setEnabled(allowed)
        self._step_bar.set_step_state(STEP_CHECK, "done" if allowed else "todo")
        # 门禁理由只在检查步说得通：别的步骤上检查还没跑，说了也没意义。
        on_check_step = self._pages.currentIndex() == STEP_CHECK
        self._gate_label.setText(text if on_check_step else "")
        self._gate_label.setStyleSheet("" if allowed else f"color: {T.WARN};")

    def _connect_signals(self):
        self._check_panel.run_requested.connect(self._on_run_checks)
        self._check_panel.fix_selected_requested.connect(self._on_fix_selected)
        self._check_panel.fix_all_warnings_requested.connect(self._on_fix_all_warnings)
        self._check_panel.locate_requested.connect(self._on_locate)
        self._check_panel.selection_changed.connect(self._detail_panel.show_result)
        self._detail_panel.fix_requested.connect(self._on_fix_selected)
        self._export_panel.run_export_requested.connect(self._on_export)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)

        # 步骤条的完成度跟着输入走，用户不进那一步也知道还差什么。
        model = self._clip_panel._model
        model.rowsInserted.connect(self._update_step_progress)
        model.rowsRemoved.connect(self._update_step_progress)
        model.modelReset.connect(self._update_step_progress)
        for field in (
            self._export_panel._fbx_dir,
            self._export_panel._fbx_name,
            self._export_panel._ue_root,
        ):
            field.textChanged.connect(self._update_step_progress)

    def _initial_state(self):
        self._check_panel.populate(self._registry)
        self._populate_default_clips()
        default_preset_id = self._config.settings.default_preset_id
        default_index = self._preset_combo.findData(default_preset_id)
        if default_index >= 0:
            self._preset_combo.setCurrentIndex(default_index)
        else:
            fallback_index = self._preset_combo.findData("custom")
            if fallback_index >= 0:
                self._preset_combo.setCurrentIndex(fallback_index)
        self._on_preset_changed()
        self._refresh_scene_info_safe()
        self._update_step_progress()
        self._start_scene_watch()

    # -- preset -------------------------------------------------------------

    def _on_preset_changed(self, *_):
        preset_id = self._preset_combo.currentData()
        self._current_preset = self._preset_registry.get(preset_id) if preset_id else None
        self._refresh_joint_options(prefer_preset_root=True)
        if self._current_preset is None:
            return
        report = getattr(self, "_last_report", None)
        if report is not None:
            self._on_run_checks()

    def _refresh_joint_options(self, prefer_preset_root: bool = False):
        """把场景里的关节填进【骨架根节点】下拉，并按预设自动选中根。

        每次跑检查前也会调，保证列表是最新的（不再只在切预设时刷一次，
        否则场景变了 / Maya 侧刷新失败时下拉就是空的，看起来像"没有下拉框"）。
        """
        try:
            from mtu_maya.core import maya_utils
            joints = maya_utils.list_joints()
        except Exception:
            return
        self._export_panel.set_joint_options(joints)
        if not prefer_preset_root or self._current_preset is None or not self._current_preset.root_bone:
            return
        preferred_index = -1
        for joint in joints:
            short_name = joint.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
            if short_name == self._current_preset.root_bone:
                preferred_index = self._export_panel._root_joint.findData(joint)
                if joint.count("|") <= 1:
                    break
        if preferred_index >= 0:
            self._export_panel._root_joint.setCurrentIndex(preferred_index)

    def _reload_config(self):
        from mtu_maya.core.config import load_all_config
        from mtu_maya.core.preset_loader import reload_default_registry

        previous_id = self._preset_combo.currentData()
        self._config = load_all_config()
        self._preset_registry = reload_default_registry()
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        for p in self._preset_registry.all():
            self._preset_combo.addItem(p.display_name, userData=p.id)
        self._export_panel._ue_root.setText(self._config.settings.ue_content_root)
        if self._export_panel._fbx_dir.text().strip() in ("", "./exports"):
            self._export_panel._fbx_dir.setText(self._config.settings.fbx_export_dir)
        policy_index = self._export_panel._overwrite.findData(self._config.settings.overwrite_policy)
        if policy_index >= 0:
            self._export_panel._overwrite.setCurrentIndex(policy_index)
        self._export_panel._auto_push.setChecked(
            self._config.settings.auto_push_after_export
        )
        thinning_index = self._export_panel._thinning.findData(
            self._config.settings.key_thinning
        )
        if thinning_index >= 0:
            self._export_panel._thinning.setCurrentIndex(thinning_index)
        selected_id = previous_id if previous_id in self._preset_registry else self._config.settings.default_preset_id
        index = self._preset_combo.findData(selected_id)
        if index >= 0:
            self._preset_combo.setCurrentIndex(index)
        self._preset_combo.blockSignals(False)
        self._on_preset_changed()

    # -- scene info ---------------------------------------------------------

    def _refresh_scene_info_safe(self):
        try:
            from mtu_maya.core import maya_utils
            name = maya_utils.current_scene_name()
            unit = maya_utils.scene_units()
            up = maya_utils.scene_up_axis()
            fps = maya_utils.scene_fps()
            start, end = maya_utils.timeline_range()
            text = S.SCENE_INFO_FMT.format(
                name=name, up=up, unit=unit, fps=fps, start=start, end=end
            )
        except ImportError:
            text = S.MAYA_UNAVAILABLE
        except Exception as exc:
            text = S.SCENE_READ_FAILED.format(exc=exc)

        # 轮询每秒来一次，值没变就别碰控件。
        if text != getattr(self, "_scene_info_text", None):
            self._scene_info_text = text
            self._scene_info.setText(text)

    def _start_scene_watch(self, interval_ms: int = 1000):
        """Poll the scene so unit/axis/fps stay true without re-running checks.

        Maya has no single "scene settings changed" signal, and wiring one
        scriptJob per property means one more callback to kill on close —
        miss one and it fires into a destroyed window. These are all O(1)
        property queries, so polling costs nothing.
        """
        self._scene_timer = QtCore.QTimer(self)
        self._scene_timer.setInterval(interval_ms)
        self._scene_timer.timeout.connect(self._refresh_scene_info_safe)
        self._scene_timer.start()

    def closeEvent(self, event):
        timer = getattr(self, "_scene_timer", None)
        if timer is not None:
            timer.stop()
        self.stop_push()
        super().closeEvent(event)

    def _animation_range_from_maya(self):
        """Frame range of the actual animation, for pre-filling a clip.

        Reads keys off the skeleton rather than the playback range: the time
        slider is a view setting, so a downloaded 0-35 clip routinely sits
        inside a default 1-120 timeline and the old fill handed back a span
        that was mostly empty air.

        Candidates are tried in order, first one with keys wins:
            hips (per the active preset) -> chosen root + its subtree
            -> every joint in the scene -> the playback range
        hips leads because an in-place clip often leaves the root joint
        without a single key, which would make the rig look unanimated.
        """
        try:
            from mtu_maya.core import maya_utils
        except Exception:
            return (1, 30)

        for candidate in self._keyframe_candidates(maya_utils):
            try:
                found = maya_utils.keyframe_range(candidate)
            except Exception:
                continue
            if found:
                return found

        try:
            return maya_utils.timeline_range()
        except Exception:
            return (1, 30)

    def _keyframe_candidates(self, maya_utils):
        """Yield node lists to look for keys on, best guess first."""
        # 1) hips / pelvis via the active preset's bone map.
        try:
            preset = self._current_preset
            hips_name = preset.bone_map.get("pelvis") if preset else None
            hips = maya_utils.resolve_joint(hips_name) if hips_name else None
            if hips:
                yield [hips]
        except Exception:
            pass

        # 2) the root the user picked, plus everything under it.
        try:
            root = self._export_panel.skeleton_root()
            if root:
                subtree = maya_utils.subtree_joints(root)
                if subtree:
                    yield subtree
        except Exception:
            pass

        # 3) anything in the scene that is a joint.
        try:
            joints = maya_utils.list_joints()
            if joints:
                yield joints
        except Exception:
            pass

    # -- checks -------------------------------------------------------------

    def _build_context_from_ui(self) -> Optional[CheckContext]:
        """Build a CheckContext by reading the live scene + UI inputs."""
        try:
            from mtu_maya.export.fbx_exporter import build_context, ExportRequest
        except ImportError as exc:
            QtWidgets.QMessageBox.warning(self, S.MSG_MAYA_REQUIRED_TITLE, str(exc))
            return None

        clips = self._clip_panel.clips()
        req = ExportRequest(
            # Empty means empty — do NOT substitute a "<unset>" placeholder.
            # A literal "<unset>" would make the path check treat the CWD as a
            # valid, writable dir and then complain about the bogus "filename".
            fbx_path=self._export_panel.fbx_path(),
            clips=clips,
            preset=self._current_preset or self._preset_registry.require("custom"),
            skeleton_root=self._export_panel.skeleton_root(),
            ue_content_root=self._export_panel.ue_root(),
            ue_skeleton_path=self._export_panel.ue_skeleton_path(),
            include_rig=self._export_panel.include_rig(),
            create_skeleton_if_missing=self._export_panel.include_rig(),
            ue_import_scale=self._export_panel.ue_import_scale(),
            overwrite_policy=self._export_panel.overwrite_policy(),
            thinning_level=self._export_panel.thinning_level(),
            settings=self._config.settings,
            fbx_preset=self._config.fbx_preset,
        )
        return build_context(req)

    def _on_run_checks(self):
        # Flush any in-progress typing (editable combos / line edits) so the
        # freshly-typed values are what the checks actually see.
        self._export_panel.commit_edits()
        # Refresh the joint dropdown so it reflects the current scene —
        # otherwise it can look empty / stale and users can't pick a root.
        self._refresh_joint_options()
        ctx = self._build_context_from_ui()
        if ctx is None:
            return
        report = run_all_checks(ctx, skipped=self._check_panel.skipped_ids())
        self._last_report = report
        self._check_panel.update_results(report)
        self._update_gate()
        self._refresh_scene_info_safe()
        # Keep the user's current selection in the detail panel if it still has
        # a result; only auto-jump to the first failure when nothing valid is
        # selected. (Previously this always jumped, which felt like the detail
        # panel ignored the user's clicks.)
        current_id = self._check_panel.selected_check_id()
        current_result = self._check_panel._results_by_id.get(current_id) if current_id else None
        if current_result is not None:
            self._detail_panel.show_result(current_result)
        else:
            first_fail = next((r for r in report.results if not r.passed), None)
            self._detail_panel.show_result(first_fail or (report.results[0] if report.results else None))

    def _on_fix_selected(self, check_id: str):
        ctx = self._build_context_from_ui()
        if ctx is None:
            return
        try:
            fix_check(check_id, ctx)
            self._status(S.MSG_FIXED_ONE.format(cid=check_id))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, S.MSG_FIX_FAILED_TITLE, str(exc))
        self._on_run_checks()

    def _on_fix_all_warnings(self):
        ctx = self._build_context_from_ui()
        if ctx is None:
            return
        fixed = fix_all_warnings(ctx, skipped=self._check_panel.skipped_ids())
        self._status(S.MSG_FIXED_N.format(n=len(fixed), ids=", ".join(fixed)))
        self._on_run_checks()

    def _on_locate(self, result: CheckResult):
        """Select the nodes the check flagged, in Maya."""
        if not result.select_on_locate:
            return
        try:
            from mtu_maya.core import maya_utils
            maya_utils.select(result.select_on_locate)
        except Exception:
            pass

    # -- export -------------------------------------------------------------

    def _on_export(self):
        self._export_panel.commit_edits()
        if not self._export_panel.fbx_path():
            QtWidgets.QMessageBox.warning(self, S.MSG_NO_FBX_PATH_TITLE, S.MSG_NO_FBX_PATH)
            return
        if self._current_preset is None:
            QtWidgets.QMessageBox.warning(self, S.MSG_NO_PRESET_TITLE, S.MSG_NO_PRESET)
            return

        self._on_run_checks()
        report = getattr(self, "_last_report", None)
        if report is None:
            return
        if report.errors:
            QtWidgets.QMessageBox.critical(
                self, S.MSG_EXPORT_BLOCKED_TITLE,
                S.MSG_EXPORT_BLOCKED.format(n=len(report.errors)),
            )
            return
        skipped = list(getattr(report, "skipped", []))
        if skipped:
            # 跳过比警告重：先确认这个，且必须点名有几项是 error 级——
            # 否则用户不会意识到自己拆掉的是哪道门。
            confirm = QtWidgets.QMessageBox.question(
                self, S.MSG_SKIPPED_TITLE,
                S.MSG_SKIPPED.format(
                    n=len(skipped),
                    errors=sum(1 for r in skipped if r.level == "error"),
                ),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if confirm != QtWidgets.QMessageBox.Yes:
                return
        if report.warnings:
            confirm = QtWidgets.QMessageBox.question(
                self, S.MSG_WARNINGS_TITLE,
                S.MSG_WARNINGS.format(n=len(report.warnings)),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if confirm != QtWidgets.QMessageBox.Yes:
                return
        self._export_panel.set_busy(True, S.STATUS_EXPORTING)
        # 唯一的导出入口在导航栏，导出期间它得关上，否则能连点两次。
        self._nav_export_btn.setEnabled(False)
        self._delivery.clear()   # 上一轮的交付结果不该跨到这一轮
        QtWidgets.QApplication.processEvents()
        try:
            from mtu_maya.export.fbx_exporter import export_animation, ExportRequest
            from mtu_maya.export.manifest_writer import write_all_artifacts
            req = ExportRequest(
                fbx_path=self._export_panel.fbx_path(),
                clips=self._clip_panel.clips(),
                preset=self._current_preset,
                skeleton_root=self._export_panel.skeleton_root(),
                ue_content_root=self._export_panel.ue_root(),
                ue_skeleton_path=self._export_panel.ue_skeleton_path(),
                include_rig=self._export_panel.include_rig(),
                create_skeleton_if_missing=self._export_panel.include_rig(),
                ue_import_scale=self._export_panel.ue_import_scale(),
                overwrite_policy=self._export_panel.overwrite_policy(),
                thinning_level=self._export_panel.thinning_level(),
                settings=self._config.settings,
                fbx_preset=self._config.fbx_preset,
                skipped_checks=self._check_panel.skipped_ids(),
            )
            result = export_animation(req)
            write_all_artifacts(result, write_report=self._config.settings.write_markdown_report)
            self._export_panel.set_busy(False, self._format_export_summary(result))
            self.show_delivery(result)
            reasons = list(result.errors or [])
            if result.is_complete():
                self._export_panel.clear_errors()
                # 推送先发车：弹窗是模态的，让线程趁用户读弹窗时把活干了。
                if self._export_panel.auto_push():
                    # 系统自己去送了，就别再摆一套"下一步请手动导入"的指引。
                    self._delivery.set_collapsed(True)
                    self._push_to_ue(self._handoff_code(result))
                QtWidgets.QMessageBox.information(
                    self, S.MSG_EXPORT_DONE_TITLE,
                    S.MSG_EXPORT_DONE.format(
                        summary=self._format_export_summary(result),
                        manifest=result.manifest_path,
                    ),
                )
            elif result.fbx_written:
                # FBX 出来了但 manifest 没有 —— 这次交付 UE 端用不了，
                # 不能因为"文件生成了"就报成功。
                self._export_panel.show_errors(reasons)
                body = "\n".join(f"• {r}" for r in reasons) if reasons else S.MSG_EXPORT_NO_REASON
                QtWidgets.QMessageBox.warning(
                    self, S.MSG_EXPORT_PARTIAL_TITLE,
                    S.MSG_EXPORT_PARTIAL.format(reasons=body),
                )
            else:
                # 把真正的原因亮出来：导出面板 + 弹窗都显示，不再是一句死话。
                self._export_panel.show_errors(reasons)
                body = "\n".join(f"• {r}" for r in reasons) if reasons else S.MSG_EXPORT_NO_REASON
                QtWidgets.QMessageBox.warning(
                    self, S.MSG_EXPORT_INCOMPLETE_TITLE,
                    S.MSG_EXPORT_INCOMPLETE.format(reasons=body),
                )
        except Exception as exc:
            self._export_panel.set_busy(False, f"{S.MSG_EXPORT_FAILED_TITLE}: {exc}")
            self._export_panel.show_errors([f"{type(exc).__name__}: {exc}"])
            QtWidgets.QMessageBox.critical(self, S.MSG_EXPORT_FAILED_TITLE, str(exc))
        finally:
            self._update_gate()

    def _format_export_summary(self, result) -> str:
        r = result.report
        if result.export_range:
            rng = S.SUMMARY_RANGE_FMT.format(start=result.export_range[0], end=result.export_range[1])
        else:
            rng = S.SUMMARY_NO_RANGE
        status_cn = S.STATUS_LABELS.get(r.status, r.status)
        fbx = S.SUMMARY_FBX_OK if result.fbx_written else S.SUMMARY_FBX_FAIL
        return S.SUMMARY_FMT.format(
            status=status_cn,
            errors=len(r.errors),
            warnings=len(r.warnings),
            infos=len(r.infos),
            fbx=fbx,
            rng=rng,
            clips=len(result.manifest.clips),
        )

    # -- helpers ------------------------------------------------------------

    def _populate_default_clips(self):
        self._clip_panel.set_clips([Clip(name="idle", start=1, end=30, root_motion=False)])

    def _status(self, message: str):
        self._export_panel._status.setText(message)

    def _open_export_folder(self):
        path = os.path.dirname(os.path.abspath(self._export_panel.fbx_path() or "."))
        if not os.path.isdir(path):
            QtWidgets.QMessageBox.information(self, S.MENU_OPEN_EXPORT_FOLDER, f"目录尚不存在：\n{path}")
            return
        try:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Maya entry point
# ---------------------------------------------------------------------------

_WINDOW: Optional[MainWindow] = None


def show():
    """Create and show the tool window inside Maya (or a standalone Qt app).

    Safe to call repeatedly: reuses the existing window if present.
    """
    global _WINDOW
    parent = None
    try:
        import maya.OpenMayaUI as omui  # type: ignore
        if _QT_BINDING == "PySide6":
            import shiboken6 as shiboken  # type: ignore
        else:
            import shiboken2 as shiboken  # type: ignore
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            parent = shiboken.wrapInstance(int(ptr), QtWidgets.QMainWindow)
    except Exception:
        parent = None

    # NOTE: never touch the shared QApplication's stylesheet — inside Maya the
    # tool shares the app with Maya's own UI, and a global QSS would repaint
    # Maya itself. Apply the theme ONLY to our top-level window; Qt cascades
    # it to all of the window's children automatically.
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    if _WINDOW is not None:
        _WINDOW.close()
        _WINDOW.deleteLater()
        _WINDOW = None

    _WINDOW = MainWindow(parent=parent)
    T.apply_theme(_WINDOW)
    _WINDOW.show()
    return _WINDOW


__all__ = ["MainWindow", "show", "CheckListPanel", "DetailPanel", "ClipTablePanel", "ExportPanel"]
