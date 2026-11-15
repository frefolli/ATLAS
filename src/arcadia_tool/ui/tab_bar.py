"""The bar of the tabs of the work area.

- A turn of the wheel of the mouse makes the next tab (down) or the previous one (up) the current one; the bar follows
  it smoothly, instead of jumping to show it.
- The tabs are reordered by dragging them.
- A tab opened goes right after the current one.

Qt keeps the scroll offset of the bar private: the bar is scrolled by giving it a turn of the wheel as pixels, from a
device scrolling by pixels (Qt scrolls the bar for those, see QTabBar::wheelEvent).
"""
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QInputDevice, QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QTabBar, QTabWidget

NOTCH = 120  # one notch of the wheel, in eighths of a degree
TICK_MS = 15  # the smooth scroll: a part of what is left at each tick
EASING = 0.3


def _pixel_mouse():
    caps = (QInputDevice.Capability.Position | QInputDevice.Capability.Scroll
            | QInputDevice.Capability.PixelScroll)
    return QPointingDevice("ATLAS smooth wheel", 0, QInputDevice.DeviceType.Mouse,
                           QPointingDevice.PointerType.Generic, caps, 1, 3)


class ScrollingTabBar(QTabBar):
    _device = None  # one for every bar (made when the first one is)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)  # reordered by dragging them
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideRight)
        self._remaining = 0.0  # pixels still to scroll (positive: towards the last tab)
        self._turned = 0  # eighths of a degree of the wheel not yet a notch (fine wheels, touchpads)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        if ScrollingTabBar._device is None:
            ScrollingTabBar._device = _pixel_mouse()

    def wheelEvent(self, event):
        delta = event.angleDelta()
        self._turned += delta.y() if abs(delta.y()) >= abs(delta.x()) else delta.x()
        steps = int(self._turned / NOTCH)
        event.accept()
        if not steps:
            return
        self._turned -= steps * NOTCH
        self.step(-steps)  # the wheel down: the next tab

    def step(self, offset):
        """The tab `offset` places after the current one (before, if negative) made current, within the bar; the bar
        scrolls to it smoothly."""
        if not self.count():
            return
        target = max(0, min(self.count() - 1, self.currentIndex() + offset))
        if target == self.currentIndex():
            return
        before = self.tabRect(0).topLeft()
        self.setCurrentIndex(target)  # Qt scrolls the bar at once to show it: brought back, then scrolled smoothly
        after = self.tabRect(0).topLeft()
        jump = (before.x() - after.x()) if self._horizontal() else (before.y() - after.y())
        if jump:
            self.scroll_by(-jump)
            self._remaining += jump
            self._timer.start()

    def _horizontal(self):
        return self.shape() in (QTabBar.RoundedNorth, QTabBar.RoundedSouth, QTabBar.TriangularNorth,
                                QTabBar.TriangularSouth)

    def _tick(self):
        if abs(self._remaining) < 1:
            self._remaining = 0.0
            self._timer.stop()
            return
        move = int(self._remaining * EASING) or (1 if self._remaining > 0 else -1)
        self._remaining -= move
        self.scroll_by(move)

    def scroll_by(self, pixels):
        """The bar scrolled by pixels (positive: towards the last tab), as far as it can go."""
        if not pixels:
            return
        amount = QPoint(-pixels, 0) if self._horizontal() else QPoint(0, -pixels)
        centre = QPointF(self.rect().center())
        event = QWheelEvent(centre, QPointF(self.mapToGlobal(centre.toPoint())), amount, amount, Qt.NoButton,
                            Qt.NoModifier, Qt.NoScrollPhase, False, Qt.MouseEventNotSynthesized,
                            ScrollingTabBar._device)
        super().wheelEvent(event)
        if not event.isAccepted():  # at an end: nothing left to scroll
            self._remaining = 0.0
            self._timer.stop()


class TabWidget(QTabWidget):
    """A QTabWidget with the ScrollingTabBar, whose new tabs go right after the current one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(ScrollingTabBar(self))

    def addTab(self, *args):
        return self.insertTab(self.currentIndex() + 1, *args)  # no tab: the first one
