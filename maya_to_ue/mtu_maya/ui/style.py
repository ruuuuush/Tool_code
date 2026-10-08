"""mtu_maya.ui.style

Dark theme for the Maya→UE pipeline tool.

Design goals:
  * Sit comfortably next to Maya's own dark UI (neutral slate, no neon).
  * Use a single accent color for primary actions; severity gets its own hues.
  * All interactive feedback is done with QSS pseudo-states (:hover/:pressed)
    plus a couple of lightweight QPropertyAnimation helpers — no custom paint.

The theme is a single QSS string (APP_QSS). Palette constants are exported so
code can reference the same colors for badges / icons.
"""

from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from mtu_maya.ui.curve_plot import CurveCompareWidget

# ---------------------------------------------------------------------------
# Palette  —  neutral graphite base + one real accent.
#
# The base stays low-chroma so the tool sits next to Maya without shouting;
# a single blue carries every "this is the thing to look at" signal (primary
# action, current step, selection). Blue reads clearly on Maya's neutral grey
# and — unlike a teal — never gets confused with the green "passed" state.
# ---------------------------------------------------------------------------

BG_DARKEST = "#16181b"   # window background
BG_PANEL = "#1e2124"     # cards / inputs
BG_RAISED = "#282c31"    # buttons, headers
BG_HOVER = "#33383e"
BG_PRESSED = "#191c1f"

BORDER = "#3a3f46"
BORDER_SOFT = "#2a2e33"

TEXT = "#e2e5ea"
TEXT_DIM = "#98a0aa"
TEXT_FAINT = "#5f666e"

# Primary accent.
ACCENT = "#4f8cff"
ACCENT_TEXT = "#ffffff"
ACCENT_HOVER = "#6b9dff"
ACCENT_PRESSED = "#3d74d8"
ACCENT_SOFT = "rgba(79, 140, 255, 0.16)"    # selected rows, current step fill
ACCENT_EDGE = "rgba(79, 140, 255, 0.45)"    # subtle accent borders

# Kept from the old near-white accent: still useful where a neutral high
# contrast surface beats a colored one.
SURFACE_BRIGHT = "#e8e6e1"

FOCUS = ACCENT
SELECTION_BG = "rgba(79, 140, 255, 0.22)"

# Severity colors — a touch brighter than before so they hold up against the
# accent without turning neon.
OK = "#4ec98a"
WARN = "#e0b355"
ERR = "#e0685c"
INFO = "#8fa3b8"

LEVEL_COLORS = {"error": ERR, "warning": WARN, "info": INFO, "ok": OK}


# ---------------------------------------------------------------------------
# Application stylesheet
# ---------------------------------------------------------------------------

APP_QSS = f"""
/* ---- base -------------------------------------------------------------- */
QWidget {{
    background-color: transparent;
    color: {TEXT};
    font-size: 13px;
    font-weight: normal;
    selection-background-color: {SELECTION_BG};
    selection-color: #ffffff;
}}
QMainWindow {{ background-color: {BG_DARKEST}; }}
QMainWindow::separator {{ background: {BG_DARKEST}; }}

QLabel {{ background: transparent; }}
QLabel[dim="true"]  {{ color: {TEXT_DIM}; }}
QLabel[faint="true"] {{ color: {TEXT_FAINT}; }}
QLabel[errorText="true"] {{
    color: {ERR};
    background-color: rgba(212, 105, 94, 0.10);
    border: 1px solid rgba(212, 105, 94, 0.35);
    border-radius: 6px;
    padding: 8px 10px;
}}
QLabel[pathText="true"] {{ color: {TEXT_DIM}; }}
QLabel[codeText="true"] {{ font-size: 12px; }}
QLabel[artifactName="true"] {{
    color: {TEXT};
    font-weight: 600;
}}
QLabel[h1="true"] {{
    font-size: 21px;
    font-weight: 700;
}}
QLabel[colHead="true"] {{
    color: {TEXT_DIM};
    font-weight: 600;
    font-size: 12px;
}}
QLabel[gate="true"] {{
    color: {TEXT_DIM};
    padding: 0 2px;
}}

/* ---- surfaces ----------------------------------------------------------- */
QFrame[panel="true"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}
QFrame[card="true"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}
QFrame[cardDivider="true"] {{
    background-color: {BORDER_SOFT};
    border: none;
    max-height: 1px;
}}
QFrame[statusBar="true"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}
QFrame[navBar="true"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}

/* ---- group cards -------------------------------------------------------- */
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {TEXT_DIM};
    background: transparent;
}}

/* ---- buttons ------------------------------------------------------------ */
QPushButton {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
    min-height: 18px;
}}
QPushButton:hover   {{ background-color: {BG_HOVER}; border-color: {FOCUS}; }}
QPushButton:pressed {{ background-color: {BG_PRESSED}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background-color: {BG_PANEL}; border-color: {BORDER_SOFT}; }}

/* primary call-to-action: solid accent, white text */
QPushButton[accent="true"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: {ACCENT_TEXT};
    font-weight: 700;
    padding: 9px 20px;
    border-radius: 6px;
}}
QPushButton[accent="true"]:hover   {{ background-color: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[accent="true"]:pressed {{ background-color: {ACCENT_PRESSED}; }}
QPushButton[accent="true"]:disabled {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER_SOFT};
    color: {TEXT_FAINT};
}}

/* secondary: outlined, no fill */
QPushButton[ghost="true"] {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 7px 16px;
    border-radius: 6px;
}}
QPushButton[ghost="true"]:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton[ghost="true"]:disabled {{ border-color: {BORDER_SOFT}; color: {TEXT_FAINT}; }}

QPushButton[flat="true"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {TEXT_DIM};
}}
QPushButton[flat="true"]:hover {{ color: {TEXT}; background-color: {BG_HOVER}; }}
QPushButton[flat="true"]:disabled {{ color: {TEXT_FAINT}; background: transparent; }}

/* ---- inputs -------------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {BG_DARKEST};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {SELECTION_BG};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {BORDER};
    background-color: {BG_PANEL};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
    background-color: {BG_PANEL};
}}
QLineEdit:disabled, QComboBox:disabled {{ color: {TEXT_FAINT}; }}

QComboBox {{ padding-right: 30px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    selection-background-color: {SELECTION_BG};
    outline: none;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {BG_RAISED};
    border: none;
    border-left: 1px solid {BORDER};
    width: 16px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {BG_HOVER};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT_DIM};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
}}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{ width: 17px; height: 17px; image: none; }}
QTreeView::indicator {{ width: 17px; height: 17px; }}

/* ---- tree / table -------------------------------------------------------- */
QTreeView, QTableView {{
    background-color: {BG_DARKEST};
    alternate-background-color: {BG_PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 6px;
    gridline-color: {BORDER_SOFT};
    outline: none;
}}
/* Vertical breathing room comes from row height / min-height, NOT from item
   padding: padding shrinks the rect a cell editor is given, which is what
   cropped the clip-name editor down to a sliver. */
QTreeView::item, QTableView::item {{ padding: 2px 4px; border: none; }}
/* The tree is read-only, so it can afford roomier rows via min-height. */
QTreeView::item {{ min-height: 28px; }}
QTreeView::item:hover, QTableView::item:hover {{ background-color: {BG_HOVER}; }}
QTreeView::item:selected, QTableView::item:selected {{
    background-color: {SELECTION_BG};
    color: {TEXT};
}}

QHeaderView::section {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: 700;
}}

/* Editors spawned inside a cell: the form-field padding above needs ~34px of
   height, but a table row is 30 — which cropped the text to a sliver. Cell
   editors get their own tight metrics. */
QAbstractItemView QLineEdit,
QAbstractItemView QComboBox,
QAbstractItemView QSpinBox,
QAbstractItemView QDoubleSpinBox {{
    padding: 0 4px;
    border: 1px solid {ACCENT};
    border-radius: 3px;
    background-color: {BG_DARKEST};
    margin: 0;
}}

/* ---- progress ------------------------------------------------------------ */
QProgressBar {{
    background-color: {BG_DARKEST};
    border: 1px solid {BORDER_SOFT};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}
/* ---- splitters / scrollbars --------------------------------------------- */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical {{ height: 10px; }}

QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {TEXT_FAINT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ---- menu / tooltip ------------------------------------------------------- */
QMenuBar {{ background: {BG_DARKEST}; border-bottom: 1px solid {BORDER_SOFT}; }}
QMenuBar::item:selected {{ background: {BG_HOVER}; border-radius: 3px; }}
QMenu {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
}}
QMenu::item {{ padding: 5px 22px; }}
QMenu::item:selected {{ background-color: {SELECTION_BG}; }}

QToolTip {{
    background-color: {BG_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 6px;
}}

QTabWidget::pane {{ border: 1px solid {BORDER_SOFT}; }}
"""


# ---------------------------------------------------------------------------
# Small animated widgets / helpers
# ---------------------------------------------------------------------------

class CheckBox(QtWidgets.QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(
            QtWidgets.QStyle.SE_CheckBoxIndicator, option, self
        ).adjusted(1, 1, -1, -1)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        active = self.checkState() != QtCore.Qt.Unchecked
        edge = ACCENT if active or self.underMouse() else BORDER
        painter.setPen(QtGui.QPen(QtGui.QColor(edge), 1))
        painter.setBrush(QtGui.QColor(ACCENT if active else BG_DARKEST))
        painter.drawRoundedRect(rect, 4, 4)
        if active:
            painter.setPen(QtGui.QPen(QtGui.QColor(ACCENT_TEXT), 2))
            if self.checkState() == QtCore.Qt.PartiallyChecked:
                painter.drawLine(rect.left() + 4, rect.center().y(), rect.right() - 4, rect.center().y())
            else:
                painter.drawPolyline(QtGui.QPolygon([
                    QtCore.QPoint(rect.left() + 3, rect.center().y()),
                    QtCore.QPoint(rect.center().x() - 1, rect.bottom() - 3),
                    QtCore.QPoint(rect.right() - 3, rect.top() + 3),
                ]))
        painter.end()


class ComboBox(QtWidgets.QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)
        rect = self.style().subControlRect(
            QtWidgets.QStyle.CC_ComboBox, option, QtWidgets.QStyle.SC_ComboBoxArrow, self
        )
        center = rect.center()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(TEXT_DIM if self.isEnabled() else TEXT_FAINT), 1.6))
        painter.drawPolyline(QtGui.QPolygon([
            QtCore.QPoint(center.x() - 4, center.y() - 2),
            QtCore.QPoint(center.x(), center.y() + 2),
            QtCore.QPoint(center.x() + 4, center.y() - 2),
        ]))
        painter.end()


class StatusBadge(QtWidgets.QLabel):
    """A pill-shaped colored badge (e.g. "12 通过 / 2 错误")."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedHeight(26)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        self._set_color(TEXT_DIM)

    def _set_color(self, color: str):
        tint = QtGui.QColor(color)
        self.setStyleSheet(
            f"background-color: rgba({tint.red()}, {tint.green()}, {tint.blue()}, 0.12);"
            f"color: {color};"
            f"border: 1px solid rgba({tint.red()}, {tint.green()}, {tint.blue()}, 0.3);"
            f"border-radius: 13px;"
            f"padding: 2px 12px;"
            f"font-weight: 600;"
        )

    def set_state(self, text: str, kind: str = "info"):
        """kind: ok | warning | error | info | neutral."""
        color = LEVEL_COLORS.get(kind, TEXT_DIM)
        self.setText(text)
        self._set_color(color)


def fade_in(widget: QtWidgets.QWidget, duration: int = 160):
    """Animate a widget fading in (used when swapping detail content)."""
    try:
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QtCore.QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        return anim
    except Exception:
        return None


def pulse(widget: QtWidgets.QWidget, duration: int = 240):
    """Quick opacity pulse — used on the summary badge after a check run."""
    try:
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QtCore.QSequentialAnimationGroup(widget)
        down = QtCore.QPropertyAnimation(effect, b"opacity")
        down.setDuration(duration // 2)
        down.setStartValue(1.0)
        down.setEndValue(0.35)
        up = QtCore.QPropertyAnimation(effect, b"opacity")
        up.setDuration(duration // 2)
        up.setStartValue(0.35)
        up.setEndValue(1.0)
        anim.addAnimation(down)
        anim.addAnimation(up)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        return anim
    except Exception:
        return None


class StepDot(QtWidgets.QLabel):
    """The circle in the step bar. Three states, three looks.

    done    - filled accent with a check mark
    current - accent ring on a tinted fill
    todo    - flat grey ring
    """

    _SIZE = 30

    def __init__(self, number: str, parent=None):
        super().__init__(parent)
        self._number = number
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.set_state("todo")

    def set_state(self, state: str):
        self._state = state
        radius = self._SIZE // 2
        if state == "done":
            self.setText("✓")
            self.setStyleSheet(
                f"background-color: {ACCENT}; color: {ACCENT_TEXT};"
                f"border: 1px solid {ACCENT}; border-radius: {radius}px;"
                f"font-weight: 700; font-size: 12px;"
            )
        elif state == "current":
            self.setText(self._number)
            self.setStyleSheet(
                f"background-color: {ACCENT_SOFT}; color: {ACCENT};"
                f"border: 2px solid {ACCENT}; border-radius: {radius}px;"
                f"font-weight: 800; font-size: 12px;"
            )
        else:
            self.setText(self._number)
            self.setStyleSheet(
                f"background-color: transparent; color: {TEXT_FAINT};"
                f"border: 1px solid {BORDER}; border-radius: {radius}px;"
                f"font-weight: 700; font-size: 12px;"
            )


class StepBar(QtWidgets.QWidget):
    """Horizontal wizard progress: dot + label per step, connected by lines.

    Doubles as navigation — clicking a step jumps to it. Keeping "where am I
    and what's left" pinned to the top means the user never has to hunt for
    the current state inside the content area.
    """

    step_clicked = QtCore.Signal(int)

    def __init__(self, titles, parent=None):
        super().__init__(parent)
        self._dots = []
        self._labels = []
        self._lines = []
        self._current = 0
        self._states = ["todo"] * len(titles)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(0)
        # 两端留白，让三步聚成一组居中，而不是被拉到窗口两角。
        lay.addStretch()

        for i, title in enumerate(titles):
            if i:
                line = QtWidgets.QFrame()
                line.setFrameShape(QtWidgets.QFrame.HLine)
                line.setFixedHeight(1)
                line.setFixedWidth(88)
                line.setStyleSheet(f"background-color: {BORDER}; border: none;")
                self._lines.append(line)
                lay.addWidget(line)

            step = QtWidgets.QWidget()
            step.setCursor(QtCore.Qt.PointingHandCursor)
            step_lay = QtWidgets.QHBoxLayout(step)
            step_lay.setContentsMargins(10, 4, 10, 4)
            step_lay.setSpacing(9)

            dot = StepDot(str(i + 1))
            label = QtWidgets.QLabel(title)
            step_lay.addWidget(dot)
            step_lay.addWidget(label)

            step.mousePressEvent = self._make_click_handler(i)
            self._dots.append(dot)
            self._labels.append(label)
            lay.addWidget(step)

        lay.addStretch()
        self.set_current(0)

    def _make_click_handler(self, index: int):
        def handler(event):
            self.step_clicked.emit(index)
        return handler

    def set_step_state(self, index: int, state: str):
        """state: done | todo. The current step's ring is applied separately."""
        self._states[index] = state
        self._refresh()

    def set_current(self, index: int):
        self._current = index
        self._refresh()

    def current(self) -> int:
        return self._current

    def _refresh(self):
        for i, dot in enumerate(self._dots):
            state = "current" if i == self._current else self._states[i]
            dot.set_state(state)
            if i == self._current:
                color, weight = ACCENT, 700
            elif self._states[i] == "done":
                color, weight = TEXT, 600
            else:
                color, weight = TEXT_FAINT, 600
            self._labels[i].setStyleSheet(
                f"color: {color}; font-weight: {weight}; font-size: 13px;"
            )
        for i, line in enumerate(self._lines):
            done = self._states[i] == "done"
            line.setStyleSheet(
                f"background-color: {ACCENT if done else BORDER}; border: none;"
            )


class ArtifactRow(QtWidgets.QWidget):
    """One line of the delivery card: status dot + name + path/reason + action.

    States:
        ok      - written, path shown, action button enabled
        failed  - not written, reason shown in the error hue
        pending - not attempted yet (e.g. report turned off)
    """

    action_clicked = QtCore.Signal(str)   # the path this row is showing

    _DOTS = {"ok": "●", "failed": "●", "pending": "○"}
    _COLORS = {"ok": OK, "failed": ERR, "pending": TEXT_FAINT}

    def __init__(self, name: str, action_text: str = "", parent=None):
        super().__init__(parent)
        self._path = ""

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(9)

        self._dot = QtWidgets.QLabel("○")
        self._dot.setFixedWidth(10)
        self._dot.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(self._dot)

        self._name = QtWidgets.QLabel(name)
        self._name.setProperty("artifactName", True)
        self._name.setFixedWidth(74)
        lay.addWidget(self._name)

        self._detail = QtWidgets.QLabel("—")
        self._detail.setTextFormat(QtCore.Qt.PlainText)
        self._detail.setProperty("pathText", True)
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._detail.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        lay.addWidget(self._detail, stretch=1)

        self._action = QtWidgets.QPushButton(action_text or "打开")
        self._action.setProperty("flat", True)
        self._action.setVisible(False)
        self._action.clicked.connect(lambda: self.action_clicked.emit(self._path))
        lay.addWidget(self._action, alignment=QtCore.Qt.AlignTop)

        self.set_state("pending")

    def set_state(self, state: str, detail: str = "", path: str = ""):
        self._path = path
        color = self._COLORS.get(state, TEXT_FAINT)
        self._dot.setText(self._DOTS.get(state, "○"))
        self._dot.setStyleSheet(f"color: {color}; font-size: 13px;")
        self._detail.setText(detail or "—")
        self._detail.setToolTip(detail)
        self._detail.setStyleSheet(
            f"color: {ERR};" if state == "failed" else f"color: {TEXT_DIM};"
        )
        # 只在真有东西可开的时候才出现按钮：一个点不动的灰按钮只是噪音。
        can_open = state == "ok" and bool(path)
        self._action.setEnabled(can_open)
        self._action.setVisible(can_open)


class DeliveryCard(QtWidgets.QFrame):
    """Post-export summary: which delivery artifacts actually reached disk.

    An FBX without its manifest is not a delivery — UE has nothing to read.
    Showing the three artifacts as separate lines makes a partial export
    impossible to mistake for a complete one.
    """

    open_requested = QtCore.Signal(str)   # path to reveal
    copy_requested = QtCore.Signal(str)   # the handoff snippet to copy
    push_requested = QtCore.Signal(str)   # run the snippet in a live editor

    def __init__(self, titles=("FBX", "Manifest", "报告"), parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.setVisible(False)
        # 卡片只占内容的高度：否则布局会把剩余空间摊给各行，
        # 行距被撑开，产物清单看起来松垮且随内容多少变形。
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(2)

        # 状态条 + 标题：颜色本身就是结论，不用读完文字才知道成没成。
        head_row = QtWidgets.QHBoxLayout()
        head_row.setContentsMargins(12, 0, 12, 6)
        head_row.setSpacing(8)
        self._stripe = QtWidgets.QFrame()
        self._stripe.setFixedWidth(3)
        self._stripe.setMinimumHeight(16)
        head_row.addWidget(self._stripe)
        self._header = QtWidgets.QLabel()
        self._header.setWordWrap(True)
        self._header.setTextFormat(QtCore.Qt.PlainText)
        self._header.setStyleSheet("font-weight: 700;")
        head_row.addWidget(self._header, stretch=1)
        # 收拢态是"系统已经办完"的默认视图，不是把信息藏起来——路径随时可查。
        self._details_btn = QtWidgets.QPushButton("详情")
        self._details_btn.setProperty("flat", True)
        self._details_btn.setVisible(False)
        self._details_btn.clicked.connect(
            lambda: self.set_collapsed(not self._collapsed)
        )
        head_row.addWidget(self._details_btn)
        lay.addLayout(head_row)

        self._divider = QtWidgets.QFrame()
        self._divider.setProperty("cardDivider", True)
        self._divider.setFixedHeight(1)
        lay.addWidget(self._divider)
        self._collapsed = False
        # 推送成功后交接区退休：系统已办完，不再摆"下一步请手动导入"。
        # 新一轮导出或推送失败时复位。
        self._handoff_retired = False

        self.rows = {}
        for key, title in zip(("fbx", "manifest", "report"), titles):
            row = ArtifactRow(title, action_text="打开位置")
            row.action_clicked.connect(self.open_requested.emit)
            self.rows[key] = row
            lay.addWidget(row)

        # ---- handoff -------------------------------------------------------
        # Maya writes the FBX and the manifest; UE builds the assets. Nothing
        # on this side can do that second half, so the card has to say so and
        # hand over a command that is ready to run.
        self._handoff = QtWidgets.QWidget()
        self._handoff.setVisible(False)
        ho = QtWidgets.QVBoxLayout(self._handoff)
        ho.setContentsMargins(0, 8, 0, 0)
        ho.setSpacing(6)

        ho_divider = QtWidgets.QFrame()
        ho_divider.setProperty("cardDivider", True)
        ho_divider.setFixedHeight(1)
        ho.addWidget(ho_divider)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(12, 4, 12, 0)
        self._handoff_title = QtWidgets.QLabel()
        self._handoff_title.setStyleSheet(f"font-weight: 700; color: {ACCENT};")
        title_row.addWidget(self._handoff_title)
        title_row.addStretch()
        # 直推是便利路径；复制永远保留，它同时是降级路径和跨机器交付的出路。
        self._push_btn = QtWidgets.QPushButton()
        self._push_btn.setProperty("accent", True)
        self._push_btn.clicked.connect(
            lambda: self.push_requested.emit(self._handoff_code.text())
        )
        title_row.addWidget(self._push_btn)
        self._copy_btn = QtWidgets.QPushButton()
        self._copy_btn.setProperty("flat", True)
        self._copy_btn.clicked.connect(
            lambda: self.copy_requested.emit(self._handoff_code.text())
        )
        title_row.addWidget(self._copy_btn)
        ho.addLayout(title_row)

        self._handoff_code = QtWidgets.QLabel()
        self._handoff_code.setProperty("codeText", True)
        self._handoff_code.setTextFormat(QtCore.Qt.PlainText)
        self._handoff_code.setContentsMargins(12, 0, 12, 4)
        self._handoff_code.setWordWrap(True)
        self._handoff_code.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._handoff_code.setStyleSheet(
            f"color: {TEXT_DIM}; background-color: {BG_DARKEST};"
            f"border: 1px solid {BORDER_SOFT}; border-radius: 6px; padding: 8px;"
        )
        code_scroll = QtWidgets.QScrollArea()
        code_scroll.setWidgetResizable(True)
        code_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        code_scroll.setFixedHeight(112)
        code_scroll.setWidget(self._handoff_code)
        ho.addWidget(code_scroll)

        self._push_status = QtWidgets.QLabel()
        self._push_status.setTextFormat(QtCore.Qt.PlainText)
        self._push_status.setContentsMargins(12, 0, 12, 2)
        self._push_status.setWordWrap(True)
        self._push_status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._push_status.setVisible(False)
        # 状态挂在卡片层而不是交接区里：收拢时交接区整块隐藏，
        # 状态跟着消失就等于推送结果没人告诉用户。
        lay.addWidget(self._handoff)
        lay.addWidget(self._push_status)

        # 抽稀曲线对比：证据也是"系统已经办完"的一部分，收拢不收它。
        self._curve_preview = CurveCompareWidget()
        lay.addWidget(self._curve_preview)

    def set_thinning_panels(self, panels):
        """Show the thinning curve comparison; empty list hides it."""
        self._curve_preview.set_panels(panels)

    def set_collapsed(self, collapsed: bool):
        """收拢：只留状态行。用在系统已经代劳、无需用户动手的时候。"""
        self._collapsed = bool(collapsed)
        self._divider.setVisible(not self._collapsed)
        for row in self.rows.values():
            row.setVisible(not self._collapsed)
        if self._collapsed or self._handoff_retired:
            self._handoff.setVisible(False)
        elif self._handoff_code.text():
            self._handoff.setVisible(True)
        self._details_btn.setVisible(True)
        self._details_btn.setText("详情" if self._collapsed else "收起")

    def retire_handoff(self):
        """推送成功 = 手动指引退休。失败或新交付时由别处复位。"""
        self._handoff_retired = True
        self._handoff.setVisible(False)

    def restore_handoff(self):
        """推送失败的复位：手动路径重新可见（只要这次交付真有代码可给）。"""
        self._handoff_retired = False
        if self._handoff_code.text():
            self._handoff.setVisible(True)

    def set_handoff(self, title: str, code: str, copy_text: str, push_text: str = ""):
        self._handoff_title.setText(title)
        self._handoff_code.setText(code)
        self._copy_btn.setText(copy_text)
        self._push_btn.setText(push_text or "推送到 UE")
        self._push_btn.setEnabled(True)
        self._push_status.setVisible(False)
        # 新交付 = 新的手动路径，退休标记只在推送成功后重新置上。
        self._handoff_retired = False
        self._handoff.setVisible(not self._collapsed)

    def set_push_state(self, text: str, kind: str = "info", busy: bool = False,
                       tooltip: str = ""):
        """Report the push outcome next to the snippet.

        The snippet and its copy button stay live no matter what: a failed
        push must never strand the user without the manual route. Long detail
        (a traceback) belongs in the tooltip — a multi-line label would grow
        the card without bound and crush the pages above it.
        """
        self._push_btn.setEnabled(not busy)
        color = {"ok": OK, "error": ERR}.get(kind, TEXT_DIM)
        self._push_status.setText(text)
        self._push_status.setToolTip(tooltip)
        self._push_status.setStyleSheet(f"color: {color};")
        self._push_status.setVisible(bool(text))

    def hide_handoff(self):
        self._handoff.setVisible(False)

    def set_header(self, text: str, kind: str = "ok"):
        color = LEVEL_COLORS.get(kind, TEXT)
        self._header.setText(text)
        self._header.setStyleSheet(f"font-weight: 700; color: {color};")
        self._stripe.setStyleSheet(f"background-color: {color}; border-radius: 1px;")


    def clear(self):
        for row in self.rows.values():
            row.set_state("pending")
            row.setVisible(True)
        self.hide_handoff()
        self._collapsed = False
        self._handoff_retired = False
        self._divider.setVisible(True)
        self._details_btn.setVisible(False)
        self._push_status.setVisible(False)
        self._handoff_code.setText("")
        self._curve_preview.set_panels([])
        self.setVisible(False)


def apply_theme(app_or_widget):
    """Install the dark theme QSS on a QApplication or a top-level widget."""
    database = QtGui.QFontDatabase if QtCore.qVersion().startswith("6.") else QtGui.QFontDatabase()
    families = set(database.families())
    font = QtGui.QFont(app_or_widget.font())
    for family in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI"):
        if family in families:
            font.setFamily(family)
            break
    font.setPixelSize(13)
    app_or_widget.setFont(font)
    app_or_widget.setStyleSheet(APP_QSS)
    widgets = app_or_widget.findChildren(QtWidgets.QWidget)
    for widget in widgets:
        if widget.property("codeText"):
            code_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            if "Consolas" in families:
                code_font.setFamily("Consolas")
            code_font.setPixelSize(12)
            widget.setFont(code_font)
        elif widget.property("pathText"):
            widget.setFont(font)


__all__ = [
    "APP_QSS",
    "CheckBox",
    "ComboBox",
    "StatusBadge",
    "StepDot",
    "StepBar",
    "ArtifactRow",
    "DeliveryCard",
    "fade_in",
    "pulse",
    "apply_theme",
    # palette
    "BG_DARKEST", "BG_PANEL", "BG_RAISED", "BG_HOVER", "BORDER", "BORDER_SOFT",
    "TEXT", "TEXT_DIM", "TEXT_FAINT", "ACCENT", "ACCENT_TEXT", "ACCENT_SOFT",
    "ACCENT_EDGE", "SURFACE_BRIGHT", "FOCUS",
    "OK", "WARN", "ERR", "INFO",
    "LEVEL_COLORS",
]
