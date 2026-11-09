"""Main window for Transparent Killer Sudoku - a minimal, always-on-top, transparent Killer Sudoku player."""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QSize, Signal, QEvent, QObject
from PySide6.QtGui import (
    QAction, QColor, QIcon, QKeySequence, QPainter, QCursor, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from board_widget import KillerSudokuBoard
from puzzle_fetcher import DKSFetcher, KillerSudokuPuzzle


class SettingsPanel(QWidget):
    """Collapsible settings panel."""

    colors_changed = Signal()
    transparency_changed = Signal(float)
    cell_size_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Title
        title = QLabel("⚙ Settings")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # Transparency
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(85)
        self.opacity_slider.setToolTip("Window opacity")
        self.opacity_slider.valueChanged.connect(self.transparency_changed.emit)
        row1.addWidget(self.opacity_slider, 1)
        layout.addLayout(row1)

        # Cell size
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Cell size:"))
        self.cell_size_slider = QSlider(Qt.Horizontal)
        self.cell_size_slider.setRange(25, 80)
        self.cell_size_slider.setValue(45)
        self.cell_size_slider.valueChanged.connect(self.cell_size_changed.emit)
        row2.addWidget(self.cell_size_slider, 1)
        layout.addLayout(row2)

        # Color buttons
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 4)

        self.bg_color_btn = QPushButton("Pick...")
        self.cage_color_btn = QPushButton("Pick...")
        self.number_color_btn = QPushButton("Pick...")
        self.cage_sum_color_btn = QPushButton("Pick...")

        for btn in [self.bg_color_btn, self.cage_color_btn,
                     self.number_color_btn, self.cage_sum_color_btn]:
            btn.setFixedWidth(60)
            btn.clicked.connect(lambda checked, b=btn: self._pick_color(b))

        form.addRow("BG Color:", self.bg_color_btn)
        form.addRow("Cage Outline:", self.cage_color_btn)
        form.addRow("Numbers:", self.number_color_btn)
        form.addRow("Cage Sums:", self.cage_sum_color_btn)
        layout.addLayout(form)

        # Toggle transparency note
        hint = QLabel("💡 Drag across whole cages to see their total (Σ). "
                      "1-9 fills the selection, 0/Del clears. Ctrl+H hides the window.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint)

        self._update_button_colors()

    def _pick_color(self, btn):
        current = self._color_from_button(btn)
        color = QColorDialog.getColor(current, self, "Select Color")
        if color.isValid():
            # Add alpha for bg
            if btn is self.bg_color_btn:
                color.setAlpha(100)  # semi-transparent bg by default
            btn.setProperty("color", color)
            self._update_button_colors()
            self.colors_changed.emit()

    def _color_from_button(self, btn):
        prop = btn.property("color")
        if prop is None:
            return self._default_color(btn)
        return prop

    def _default_color(self, btn):
        if btn is self.bg_color_btn:
            return QColor(255, 255, 255, 100)
        elif btn is self.cage_color_btn:
            return QColor(165, 165, 165, 190)
        elif btn is self.number_color_btn:
            return QColor(60, 60, 60, 225)
        elif btn is self.cage_sum_color_btn:
            return QColor(160, 160, 160, 210)
        return QColor(0, 0, 0)

    def _update_button_colors(self):
        for btn in [self.bg_color_btn, self.cage_color_btn,
                     self.number_color_btn, self.cage_sum_color_btn]:
            c = self._color_from_button(btn)
            btn.setStyleSheet(
                f"background-color: rgba({c.red()},{c.green()},{c.blue()},{c.alpha()}); "
                f"border: 1px solid #666; padding: 2px;"
            )

    def get_colors(self):
        return {
            "bg": self._color_from_button(self.bg_color_btn),
            "cage": self._color_from_button(self.cage_color_btn),
            "number": self._color_from_button(self.number_color_btn),
            "cage_sum": self._color_from_button(self.cage_sum_color_btn),
        }


class TitleBarDragFilter(QObject):
    """Forward left-button press/move on title-bar widgets to window dragging."""

    def __init__(self, window):
        super().__init__(window)
        self._win = window
        self._drag_pos: Optional[QPoint] = None

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
            return True
        if etype == QEvent.MouseMove and self._drag_pos is not None \
                and event.buttons() & Qt.LeftButton:
            self._win.move(event.globalPosition().toPoint() - self._drag_pos)
            return True
        if etype == QEvent.MouseButtonRelease:
            self._drag_pos = None
        return False


class TransparentSudokuWindow(QMainWindow):
    """Main application window - always-on-top, frameless, transparent."""

    def __init__(self):
        super().__init__()
        self._fetcher = DKSFetcher()
        self._puzzle: Optional[KillerSudokuPuzzle] = None
        self._drag_pos: Optional[QPoint] = None
        self._settings_visible = False

        # Cache dir (cross-platform)
        appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
        self._cache_dir = Path(appdata) / "TransparentSudoku"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path = self._cache_dir / "cache.json"

        self._setup_window()
        self._setup_ui()
        self._setup_tray()
        self._load_today_puzzle()

    def _setup_window(self):
        self.setWindowTitle("Transparent Killer Sudoku")
        self.setWindowFlags(
            Qt.FramelessWindowHint |  # no OS titlebar
            Qt.WindowStaysOnTopHint |  # always on top
            Qt.Tool |  # no taskbar entry
            Qt.Window
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setWindowOpacity(0.85)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(4)

        # Title bar (custom)
        title_bar = QHBoxLayout()
        title_bar.setSpacing(4)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet(
            "font-size: 11px; color: rgba(120,120,120,170); background: transparent; "
            "padding: 2px 4px;"
        )
        self.title_label.setCursor(Qt.SizeAllCursor)
        self.title_label.setFixedHeight(26)
        self._title_drag = TitleBarDragFilter(self)
        self.title_label.installEventFilter(self._title_drag)
        title_bar.addWidget(self.title_label, 1)

        # Puzzle controls
        btn_today = QPushButton("Today")
        btn_today.setToolTip("Load today's puzzle")
        btn_today.setStyleSheet(self._small_btn_style())
        btn_today.clicked.connect(self._load_today_puzzle)
        title_bar.addWidget(btn_today)

        lbl_hash = QLabel("#")
        lbl_hash.setCursor(Qt.SizeAllCursor)
        lbl_hash.installEventFilter(self._title_drag)
        title_bar.addWidget(lbl_hash)
        self.puzzle_id_input = QLineEdit()
        self.puzzle_id_input.setFixedWidth(55)
        self.puzzle_id_input.setPlaceholderText("872")
        self.puzzle_id_input.setStyleSheet(
            "border: 1px solid rgba(150,150,150,90); padding: 2px 4px; "
            "background: rgba(255,255,255,35); color: rgba(90,90,90,200);"
        )
        self.puzzle_id_input.returnPressed.connect(self._load_puzzle_by_id)
        title_bar.addWidget(self.puzzle_id_input)

        btn_go = QPushButton("Go")
        btn_go.setStyleSheet(self._small_btn_style())
        btn_go.clicked.connect(self._load_puzzle_by_id)
        title_bar.addWidget(btn_go)

        btn_clear = QPushButton("↺")
        btn_clear.setToolTip("Clear all user entries")
        btn_clear.setStyleSheet(self._small_btn_style())
        btn_clear.clicked.connect(self._clear_board)
        title_bar.addWidget(btn_clear)

        btn_settings = QPushButton("⚙")
        btn_settings.setToolTip("Toggle settings")
        btn_settings.setStyleSheet(self._small_btn_style())
        btn_settings.clicked.connect(self._toggle_settings)
        title_bar.addWidget(btn_settings)

        btn_min = QPushButton("—")
        btn_min.setToolTip("Minimize to tray")
        btn_min.setStyleSheet(self._small_btn_style())
        btn_min.clicked.connect(self.hide)
        title_bar.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setToolTip("Close")
        btn_close.setStyleSheet(self._small_btn_style())
        btn_close.clicked.connect(QApplication.instance().quit)
        title_bar.addWidget(btn_close)

        root_layout.addLayout(title_bar)

        # Board
        self.board = KillerSudokuBoard()
        self.board.cell_clicked.connect(self._on_cell_clicked)
        root_layout.addWidget(self.board, 1)

        # Settings panel (hidden by default)
        self.settings_panel = SettingsPanel()
        self.settings_panel.setVisible(False)
        self.settings_panel.colors_changed.connect(self._apply_colors)
        self.settings_panel.transparency_changed.connect(self._apply_transparency)
        self.settings_panel.cell_size_changed.connect(self._apply_cell_size)
        root_layout.addWidget(self.settings_panel)

        # Apply initial colors
        self._apply_colors()

        # Initial size
        self.resize(450, 520)

    def _small_btn_style(self):
        return """
            QPushButton {
                padding: 1px 5px;
                font-size: 10px;
                color: rgba(110,110,110,150);
                border: none;
                background: transparent;
            }
            QPushButton:hover { color: rgba(40,40,40,220); }
        """

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        # Create a simple colored square as tray icon
        pix = QPixmap(16, 16)
        pix.fill(QColor(50, 100, 150))
        self.tray.setIcon(QIcon(pix))
        self.tray.setToolTip("Transparent Killer Sudoku")

        menu = QMenu(self)
        act_show = QAction("Show/Hide", self)
        act_show.triggered.connect(self._toggle_visible)
        menu.addAction(act_show)

        act_today = QAction("Today's Puzzle", self)
        act_today.triggered.connect(self._load_today_puzzle)
        menu.addAction(act_today)

        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self._toggle_visible() if reason == self.tray.Trigger else None)
        self.tray.show()

        # Panic key: takes the window off screen immediately
        shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        shortcut.activated.connect(self._toggle_visible)

    def _toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    # ---- Puzzle loading ----

    def _save_cache(self):
        if self._puzzle is None:
            return
        try:
            self._cache_path.write_text(
                json.dumps(self._puzzle.to_dict(), indent=2), encoding="utf-8"
            )
        except OSError as exc:
            print(f"[Cache] failed to write: {exc}")

    def _load_cache(self) -> Optional[KillerSudokuPuzzle]:
        if not self._cache_path.exists():
            return None
        try:
            d = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return KillerSudokuPuzzle.from_dict(d)
        except (OSError, ValueError, KeyError) as exc:
            print(f"[Cache] failed to read: {exc}")
            return None

    def _apply_puzzle(self, puzzle: KillerSudokuPuzzle):
        """Plug a puzzle into the UI and update the title / cache."""
        self._puzzle = puzzle
        self.board.set_puzzle(puzzle)
        self.puzzle_id_input.setText(str(puzzle.puzzle_id))
        diff = "★" * puzzle.difficulty
        self.title_label.setText(f"#{puzzle.puzzle_id}")
        self.title_label.setToolTip(
            f"Puzzle #{puzzle.puzzle_id} · {puzzle.date} · difficulty {puzzle.difficulty}/10 "
            f"{diff} · {len(puzzle.cages)} cages"
        )
        self._save_cache()

    def _load_today_puzzle(self):
        self._status("Loading today's puzzle...")
        QApplication.processEvents()
        try:
            puzzle_ids = self._fetcher.fetch_today_puzzle_ids()
        except Exception as e:
            return self._offline_fallback_today(
                f"Today's puzzle failed (site 503 or down): {e}"
            )
        if not puzzle_ids:
            return self._offline_fallback_today("No puzzle published for today yet")
        self._load_puzzle_by_id_int(puzzle_ids[0])

    def _offline_fallback_today(self, error_msg: str):
        cache = self._load_cache()
        if cache is not None:
            self._error(f"{error_msg} — showing last saved (#{cache.puzzle_id})")
            self._apply_puzzle(cache)
        else:
            self._error(error_msg)

    def _load_puzzle_by_id(self):
        text = self.puzzle_id_input.text().strip()
        if not text.isdigit():
            self._error("Please enter a valid puzzle number")
            return
        self._load_puzzle_by_id_int(int(text))

    def _load_puzzle_by_id_int(self, puzzle_id: int):
        self._status(f"Loading puzzle #{puzzle_id}...")
        QApplication.processEvents()
        try:
            puzzle = self._fetcher.fetch_puzzle(puzzle_id)
            self._apply_puzzle(puzzle)
            print(f"[Status] Loaded puzzle #{puzzle_id} ({puzzle.date})")
        except Exception as e:
            self._error(f"Puzzle #{puzzle_id} failed: {e}")

    def _clear_board(self):
        if self._puzzle:
            self.board.clear_user_values()
            self._status("Board cleared")

    # ---- Color/settings application ----

    def _apply_colors(self):
        colors = self.settings_panel.get_colors()
        self.board.set_background_color(colors["bg"])
        self.board.set_cage_border_color(colors["cage"])
        self.board.set_number_color(colors["number"])
        self.board.set_cage_sum_color(colors["cage_sum"])

    def _apply_transparency(self, value: int):
        self.setWindowOpacity(value / 100.0)

    def _apply_cell_size(self, value: int):
        self.board.set_cell_size(value)

    def _toggle_settings(self):
        self._settings_visible = not self._settings_visible
        self.settings_panel.setVisible(self._settings_visible)
        # Resize to accommodate
        if self._settings_visible:
            self.resize(max(self.width(), 450), self.height() + 150)
        else:
            self.resize(max(self.width(), 450), 520)

    # ---- Mouse dragging for frameless window ----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ---- Misc ----

    def _on_cell_clicked(self, row: int, col: int):
        pass  # Board already handles visual feedback

    def _status(self, msg: str):
        """Show progress in the title bar so failures are never silent."""
        self.title_label.setText(f"⏳ {msg}")
        self.title_label.setToolTip(msg)
        QApplication.processEvents()
        print(f"[Status] {msg}")

    def _error(self, msg: str):
        """Show the error in the title bar instead of hiding it in the console."""
        self.title_label.setText(f"⚠ {msg}")
        self.title_label.setToolTip(msg)
        print(f"[Error] {msg}")

    def closeEvent(self, event):
        """Minimize to tray instead of closing."""
        if self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = TransparentSudokuWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
