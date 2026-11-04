"""Info › Versione Corrente: the version of ATLAS and the changes of its release; «Chiudi Progetto» next to «Salva»."""
import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool import __version__
from arcadia_tool.ui.about import VersionDialog, changelog_path, release_notes

CHANGELOG = """# Changelog

## [Non rilasciato]

### Aggiunto
- Una novità in arrivo.

## [9.9.9] - 2026-11-05

### Aggiunto
- **Discussioni** sulle ADR.

## [9.9.8] - 2026-11-02

- Altro.

[Non rilasciato]: https://github.com/salvodesi/ATLAS/compare/v9.9.9...main
[9.9.9]: https://github.com/salvodesi/ATLAS/compare/v9.9.8...v9.9.9
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_notes_of_a_version_are_its_section_of_the_changelog():
    version, date, body = release_notes(CHANGELOG, "9.9.9")
    assert (version, date) == ("9.9.9", "2026-11-05") and body == "### Aggiunto\n- **Discussioni** sulle ADR."
    assert release_notes(CHANGELOG, "9.9.8")[2] == "- Altro."  # without the links at the end
    assert release_notes(CHANGELOG, "1.0.0")[0] == "Non rilasciato"  # the sources ahead of the releases
    assert release_notes("nessuna sezione", "9.9.9") is None
    assert changelog_path() is not None  # the sources: at their root (installed: next to the program)


def test_the_window_shows_the_version_and_its_notes(app, tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG.replace("9.9.9", __version__), encoding="utf-8")
    dialog = VersionDialog(path=path)
    texts = [w.text() for w in dialog.findChildren(type(dialog.caption))]
    assert f"ATLAS {__version__}" in texts
    assert dialog.caption.text() == f"Novità della versione {__version__} del 05/11/2026"
    assert "Discussioni" in dialog.notes.toPlainText()
    (tmp_path / "vuoto.md").write_text("", encoding="utf-8")
    empty = VersionDialog(path=tmp_path / "vuoto.md")  # no notes: said so
    assert "non sono disponibili" in empty.caption.text() and not empty.notes.isVisibleTo(empty)


def test_the_menu_info_and_the_button_to_close_the_project(app, tmp_path, monkeypatch):
    from arcadia_tool.storage.project import Project
    from arcadia_tool.ui import about
    from arcadia_tool.ui.main_window import MainWindow

    window = MainWindow()
    window._set_project(Project.create(tmp_path / "p", "Prova"))
    menus = [a.text() for a in window.menuBar().actions()]
    assert "&Info" in menus and "&Aiuto" not in menus
    info = next(a.menu() for a in window.menuBar().actions() if a.text() == "&Info")
    assert [a.text() for a in info.actions() if a.text()][0] == "Versione Corrente…"
    monkeypatch.setattr(about.VersionDialog, "exec", lambda d: None)
    assert window.show_version().windowTitle() == "Versione corrente"
    bar = next(b for b in window.findChildren(type(window.addToolBar("x"))) if b.windowTitle() == "Principale")
    labels = [a.text() for a in bar.actions() if a.text()]
    assert labels[labels.index("Salva") + 1] == "Chiudi Progetto"  # next to «Salva»
    window.close()
