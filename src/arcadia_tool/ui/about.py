"""Info › Versione corrente: the version of ATLAS running and what it changed (its section of the CHANGELOG, shipped
with the program)."""
import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from arcadia_tool import __version__
from arcadia_tool.ui.theme import icon

SECTION = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\S+))?\s*$", re.M)


def changelog_path():
    """The CHANGELOG: next to the program installed (PyInstaller), else at the root of the sources."""
    bundled = getattr(sys, "_MEIPASS", None)
    candidates = ([Path(bundled) / "CHANGELOG.md"] if bundled else []) + \
        [Path(__file__).resolve().parents[3] / "CHANGELOG.md"]
    return next((p for p in candidates if p.is_file()), None)


def release_notes(text, version=__version__):
    """(version, date, the text of its section): the section of the version; else the first one (e.g. the sources,
    ahead of the last release: «Non rilasciato»). None if the CHANGELOG has no section."""
    sections = list(SECTION.finditer(text or ""))
    if not sections:
        return None
    chosen = next((m for m in sections if m.group("version") == version), sections[0])
    following = next((m.start() for m in sections if m.start() > chosen.start()), None)
    body = text[chosen.end():following]
    body = re.split(r"^\[[^\]]+\]: ", body, maxsplit=1, flags=re.M)[0]  # the links at the end of the file
    return chosen.group("version"), chosen.group("date") or "", body.strip()


class VersionDialog(QDialog):
    """The version of ATLAS and the changes of its release."""

    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        self.setWindowTitle("Versione corrente")
        self.resize(820, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        logo = QLabel()
        logo.setPixmap(icon("mdi6.information-outline").pixmap(36, 36))
        title = QLabel(f"ATLAS {__version__}", objectName="cardTitle")
        subtitle = QLabel("Arcadia Traceability, Logical Architecture Software", objectName="muted")
        heading = QVBoxLayout()
        heading.addWidget(title)
        heading.addWidget(subtitle)
        top = QHBoxLayout()
        top.addWidget(logo)
        top.addLayout(heading, 1)
        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        path = path or changelog_path()
        text = path.read_text(encoding="utf-8") if path is not None else ""
        found = release_notes(text)
        if found is None:
            self.caption = QLabel("Le note della versione non sono disponibili in questa installazione.",
                                  objectName="muted")
            self.notes.setVisible(False)
        else:
            version, date, body = found
            when = f" del {'/'.join(reversed(date.split('-')))}" if date else ""
            self.caption = QLabel(f"Novità della versione {version}{when}" if version == __version__ else
                                  f"Modifiche non ancora rilasciate («{version}»): questa copia è avanti rispetto "
                                  f"all'ultima versione", objectName="formLabel")
            self.notes.setMarkdown(body)
        close = QPushButton("Chiudi")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.caption)
        layout.addWidget(self.notes, 1)
        layout.addLayout(buttons)
