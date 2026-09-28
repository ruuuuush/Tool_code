"""mtu_maya.ui.curve_plot

In-card before/after curve preview for keyframe thinning.

Same CurvePanel data as the report's SVG, second renderer: that one is for
GitHub, this one is for the person standing in front of Maya. QPainter only —
no QtSvg dependency to gamble on across Maya versions.
"""

from __future__ import annotations

from typing import List

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from mtu_maya.core.curve_thinning import CurvePanel

_RED = QtGui.QColor("#e05252")
_BLUE = QtGui.QColor("#4f9cf9")
_DIM = QtGui.QColor("#8a8a8a")
_AXIS = QtGui.QColor("#555555")
_BG = QtGui.QColor("#1e1e1e")

_HEADER_H = 22
_PANEL_H = 62
_PAD_L = 12
_PAD_R = 8
_PAD_T = 14   # panel title line
_PAD_B = 4
_MAX_PANELS = 3


class CurveCompareWidget(QtWidgets.QWidget):
    """Compact stacked curve panels: red original vs blue thinned."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panels: List[CurvePanel] = []
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum
        )
        self.setVisible(False)

    def set_panels(self, panels) -> None:
        self._panels = list(panels or [])[:_MAX_PANELS]
        if self._panels:
            h = _HEADER_H + len(self._panels) * _PANEL_H
            self.setMinimumHeight(h)
            self.setMaximumHeight(h)
        self.setVisible(bool(self._panels))
        self.update()

    def panels(self) -> List[CurvePanel]:
        return list(self._panels)

    # -- painting -------------------------------------------------------------

    def _panel_rect(self, index: int):
        top = _HEADER_H + index * _PANEL_H
        return top, _PAD_L, self.width() - _PAD_L - _PAD_R, _PANEL_H - _PAD_T - _PAD_B

    def _map_points(self, points, t_range, v_range, top):
        tmin, tmax = t_range
        vmin, vmax = v_range
        left = _PAD_L
        width = self.width() - _PAD_L - _PAD_R
        height = _PANEL_H - _PAD_T - _PAD_B
        y0 = top + _PAD_T
        tspan = (tmax - tmin) or 1.0
        vspan = (vmax - vmin) or 1.0
        out = []
        for t, v in points:
            x = left + (t - tmin) / tspan * width
            y = y0 + height - (v - vmin) / vspan * height
            out.append(QtCore.QPointF(x, y))
        return out

    def paintEvent(self, event):
        if not self._panels:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.fillRect(self.rect(), _BG)

        # Legend.
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        p.setPen(_RED)
        p.drawLine(_PAD_L, 10, _PAD_L + 18, 10)
        p.setPen(_DIM)
        p.drawText(_PAD_L + 24, 14, "original")
        p.setPen(_BLUE)
        p.drawLine(_PAD_L + 90, 10, _PAD_L + 108, 10)
        p.setPen(_DIM)
        p.drawText(_PAD_L + 114, 14, "thinned")

        for i, panel in enumerate(self._panels):
            top, left, width, height = self._panel_rect(i)
            both = list(panel.before) + list(panel.after)
            if not both:
                continue
            t_range = (min(t for t, _ in both), max(t for t, _ in both))
            v_range = (min(v for _, v in both), max(v for _, v in both))

            p.setPen(_DIM)
            p.drawText(left, top + 10, f"{panel.title}  ({panel.keys_before} → {panel.keys_after} keys)")

            # Baseline axis.
            p.setPen(_AXIS)
            axis_y = top + _PAD_T + height
            p.drawLine(left, axis_y, left + width, axis_y)

            for pts, color in ((panel.before, _RED), (panel.after, _BLUE)):
                if not pts:
                    continue
                mapped = self._map_points(pts, t_range, v_range, top)
                pen = QtGui.QPen(color)
                pen.setWidthF(1.5)
                p.setPen(pen)
                p.drawPolyline(mapped)
        p.end()


__all__ = ["CurveCompareWidget"]
