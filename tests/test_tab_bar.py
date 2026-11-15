"""The tabs of the work area: the wheel of the mouse makes the next or previous tab the current one (the bar follows it
smoothly), they are reordered by dragging them, a tab opened goes right after the current one."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QApplication, QLabel

from arcadia_tool.ui.tab_bar import ScrollingTabBar, TabWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def turn(app, bar, notches, wait=True):
    """A turn of the wheel of a mouse (negative: down), then (wait) the smooth scroll to its end."""
    event = QWheelEvent(QPointF(50, 10), QPointF(50, 10), QPoint(0, 0), QPoint(0, int(120 * notches)), Qt.NoButton,
                        Qt.NoModifier, Qt.NoScrollPhase, False, Qt.MouseEventNotSynthesized,
                        QPointingDevice.primaryPointingDevice())
    app.sendEvent(bar, event)
    for _ in range(200 if wait else 0):
        if not bar._timer.isActive():
            break
        app.processEvents()
        time.sleep(0.01)


def tabs_of(app, n=30):
    tabs = TabWidget()
    for i in range(n):
        tabs.addTab(QLabel(str(i)), f"Scheda numero {i}")
        tabs.setCurrentIndex(tabs.count() - 1)
    tabs.setCurrentIndex(0)
    tabs.resize(600, 300)
    tabs.show()
    app.processEvents()
    return tabs, tabs.tabBar()


def visible(bar, index):
    return bar.rect().contains(bar.tabRect(index).center())


def test_the_wheel_changes_the_current_tab_and_the_bar_follows_it_smoothly(app):
    tabs, bar = tabs_of(app)
    assert isinstance(bar, ScrollingTabBar) and bar.isMovable()
    turn(app, bar, -1)
    assert tabs.currentIndex() == 1  # down: the next tab
    turn(app, bar, -10, wait=False)
    assert tabs.currentIndex() == 11
    assert bar.tabRect(0).x() > -bar.tabRect(0).width() * 5 and bar._timer.isActive()  # not jumped: scrolling
    turn(app, bar, 0)
    assert visible(bar, 11)  # reached
    turn(app, bar, 3)
    assert tabs.currentIndex() == 8  # up: the previous ones
    turn(app, bar, 100)
    assert tabs.currentIndex() == 0 and bar.tabRect(0).x() == 0  # no further than the first
    for _ in range(4):  # a fine wheel: a tab every notch, not every event
        turn(app, bar, -0.25)
    assert tabs.currentIndex() == 1
    bar.moveTab(0, 3)  # dragged: the page goes with its tab
    assert tabs.widget(3).text() == "0"
    tabs.close()


def test_a_tab_opens_right_after_the_current_one(app):
    tabs, _bar = tabs_of(app, 4)
    tabs.setCurrentIndex(1)
    index = tabs.addTab(QLabel("nuova"), "Nuova")
    assert index == 2 and tabs.widget(2).text() == "nuova" and tabs.widget(3).text() == "2"
    empty = TabWidget()
    assert empty.addTab(QLabel("prima"), "Prima") == 0
    tabs.close()
