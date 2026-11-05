"""Long operations on the project (saving, publishing): run in a thread, with the input of the user suspended meanwhile
and, only if they take time, a window saying what is going on."""
from PySide6.QtCore import QEventLoop, QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QProgressDialog

SHOW_AFTER_MS = 300  # shorter operations show nothing


class _Worker(QThread):
    report = Signal(str)

    def __init__(self, work):
        super().__init__()
        self.work, self.result, self.error = work, None, None

    def run(self):
        try:
            self.result = self.work(self.report.emit)
        except Exception as exc:  # raised again by run_busy, in the thread of the interface
            self.error = exc


class _Window(QObject):
    """The window of the operation, created when it is late. A QObject: its slots run in the thread of the interface."""

    def __init__(self, parent, text):
        super().__init__()
        self.parent_widget, self.text, self.dialog = parent, text, None

    @Slot()
    def show(self):
        self.dialog = QProgressDialog(self.text, None, 0, 0, self.parent_widget)
        self.dialog.setWindowTitle("Attendere")
        self.dialog.setWindowModality(Qt.WindowModal)
        self.dialog.setMinimumDuration(0)
        self.dialog.show()

    @Slot(str)
    def set_text(self, text):
        self.text = text
        if self.dialog is not None:
            self.dialog.setLabelText(text)

    def close(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog.deleteLater()


def run_busy(parent, text, work):
    """The result of work(report), a function run in a thread: it must not touch the widgets; report(text) changes what
    the window says. Returns when it ends, raising its exception if any; the window appears after SHOW_AFTER_MS. The
    input of the user waits meanwhile, so the model does not change under it."""
    worker, window = _Worker(work), _Window(parent, text)
    timer = QTimer(singleShot=True, interval=SHOW_AFTER_MS)
    timer.timeout.connect(window.show)
    worker.report.connect(window.set_text)
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    worker.start()
    timer.start()
    loop.exec(QEventLoop.ExcludeUserInputEvents)
    timer.stop()
    worker.wait()
    window.close()
    if worker.error is not None:
        raise worker.error
    return worker.result


def save_project(parent, project, only=None):
    """Project.save, with the window if it takes time; only: see Project.save."""
    def work(report):
        project.save(lambda done, total: report(f"Salvataggio in corso… {done} di {total} schede"), only)
    run_busy(parent, "Salvataggio in corso…", work)
