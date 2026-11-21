"""Killer Sudoku board widget with transparent background support."""

from itertools import combinations
from typing import List, Optional, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from puzzle_fetcher import KillerSudokuPuzzle


class KillerSudokuBoard(QWidget):
    """Custom widget that draws a Killer Sudoku puzzle board."""

    # Signal emitted when a cell is clicked: (row, col)
    cell_clicked = Signal(int, int)
    # Signal emitted when a value is entered on the selected cell
    value_entered = Signal(int, int, int)  # row, col, value (0=clear)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._puzzle: Optional[KillerSudokuPuzzle] = None
        self._user_values: List[List[int]] = []  # user-entered values (0=empty)
        self._pencils: List[List[Set[int]]] = []  # per-cell candidate digits
        self._selected_cells: List[Tuple[int, int]] = []  # drag-selectable cells
        self._anchor_cell: Optional[Tuple[int, int]] = None  # cursor cell
        self._dragging = False
        self._fixed_mask: List[List[bool]] = []  # True for given cells

        # Results are only shown after an explicit check
        self._checked_wrong: Set[Tuple[int, int]] = set()
        self._checked_cage_bad: Set[int] = set()
        self._checked_cage_done: Set[int] = set()

        # Typing session: a single digit commits, several digits become pencils
        self._typing_key = None
        self._typing_digits: List[int] = []
        self._type_timer = QTimer(self)
        self._type_timer.setSingleShot(True)
        self._type_timer.setInterval(900)
        self._type_timer.timeout.connect(self._end_typing_session)

        # Visual settings
        self._bg_color = QColor(0, 0, 0, 0)  # fully transparent bg
        self._cage_border_color = QColor(165, 165, 165, 190)
        self._cage_border_width = 1.0
        self._number_color = QColor(20, 20, 20, 255)
        self._fixed_number_color = QColor(20, 20, 20, 255)
        self._pencil_color = QColor(110, 110, 110, 200)
        self._cage_sum_color = QColor(160, 160, 160, 210)
        self._cage_done_color = QColor(40, 160, 80, 230)
        self._cage_error_color = QColor(200, 60, 60, 230)
        self._check_error_color = QColor(200, 60, 60, 255)
        self._selected_color = QColor(100, 150, 255, 100)
        self._highlight_color = QColor(200, 220, 255, 60)
        self._same_digit_color = QColor(255, 200, 80, 75)
        self._cell_size = 40  # base cell size
        self._cage_sum_font_scale = 0.22
        self._number_font_scale = 0.55
        self._fixed_bold = True

        # Allow focus for keyboard input
        self.setFocusPolicy(Qt.StrongFocus)

        # Transparency support
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    # ---- Public API ----

    def set_puzzle(self, puzzle: KillerSudokuPuzzle):
        """Load a new puzzle."""
        self._puzzle = puzzle
        size = puzzle.size
        self._user_values = [[0] * size for _ in range(size)]
        self._pencils = [[set() for _ in range(size)] for _ in range(size)]
        self._fixed_mask = [[puzzle.cells[r][c] != 0 for c in range(size)] for r in range(size)]
        self._selected_cells = []
        self._anchor_cell = None
        self._reset_check_state()
        self.update()

    def set_background_color(self, color: QColor):
        self._bg_color = color
        self.update()

    def set_cage_border_color(self, color: QColor):
        self._cage_border_color = color
        self.update()

    def set_number_color(self, color: QColor):
        self._number_color = color
        self._fixed_number_color = color
        self.update()

    def set_cage_sum_color(self, color: QColor):
        self._cage_sum_color = color
        self.update()

    def set_cell_size(self, size: int):
        self._cell_size = max(20, size)
        self.updateGeometry()
        self.update()

    def set_font_scale(self, number_scale: float = 0.55, cage_sum_scale: float = 0.35):
        self._number_font_scale = number_scale
        self._cage_sum_font_scale = cage_sum_scale
        self.update()

    def user_value(self, row: int, col: int) -> int:
        """Get the current value at a cell (fixed or user-entered)."""
        if self._fixed_mask[row][col]:
            return self._puzzle.cells[row][col]
        return self._user_values[row][col]

    def set_user_value(self, row: int, col: int, value: int):
        if self._fixed_mask[row][col]:
            return
        self._user_values[row][col] = value
        self._pencils[row][col].clear()
        self._reset_check_state()
        self.update()

    def set_pencils(self, row: int, col: int, digits: Set[int]):
        """Mark a cell with pencil candidates (clears any committed value)."""
        if self._fixed_mask[row][col]:
            return
        self._user_values[row][col] = 0
        self._pencils[row][col] = set(digits)
        self._reset_check_state()
        self.update()

    def pencils(self, row: int, col: int) -> Set[int]:
        return set(self._pencils[row][col]) if self._pencils else set()

    def clear_user_values(self):
        if self._puzzle:
            size = self._puzzle.size
            self._user_values = [[0] * size for _ in range(size)]
            self._pencils = [[set() for _ in range(size)] for _ in range(size)]
            self._reset_check_state()
            self.update()

    def check_board(self) -> Tuple[int, int, int]:
        """Validate entries against the solution and highlight mistakes.

        Results stay invisible until this is called. Returns
        (wrong cells, filled cells, editable cells).
        """
        if self._puzzle is None:
            return (0, 0, 0)

        self._reset_check_state()
        n = self._puzzle.size
        solution = self._puzzle.solution
        wrong = filled = total = 0

        for r in range(n):
            for c in range(n):
                if self._fixed_mask[r][c]:
                    continue
                total += 1
                value = self._user_values[r][c]
                if not value:
                    continue
                filled += 1
                if solution is not None:
                    if solution[r][c] != value:
                        self._checked_wrong.add((r, c))
                        wrong += 1
                elif self._has_conflict(r, c, value):
                    self._checked_wrong.add((r, c))
                    wrong += 1

        # Cage-level verdicts, also only on demand
        for cage in self._puzzle.cages:
            values = [self.user_value(r, c) for r, c in cage.cells]
            if any(v == 0 for v in values):
                continue
            if sum(values) == cage.sum_value:
                self._checked_cage_done.add(cage.index)
            else:
                self._checked_cage_bad.add(cage.index)

        self.update()
        return (wrong, filled, total)

    def _has_conflict(self, row: int, col: int, value: int) -> bool:
        """Rule-based fallback when no solution is embedded in the page."""
        n = self._puzzle.size
        for c2 in range(n):
            if c2 != col and self.user_value(row, c2) == value:
                return True
        for r2 in range(n):
            if r2 != row and self.user_value(r2, col) == value:
                return True
        nr = self._puzzle.num_rows_nonet
        nc = self._puzzle.num_cols_nonet
        br, bc = (row // nr) * nr, (col // nc) * nc
        for r2 in range(br, br + nr):
            for c2 in range(bc, bc + nc):
                if (r2, c2) != (row, col) and self.user_value(r2, c2) == value:
                    return True
        for r2, c2 in self._puzzle.cages[self._puzzle.cage_grid[row][col]].cells:
            if (r2, c2) != (row, col) and self.user_value(r2, c2) == value:
                return True
        return False

    def _reset_check_state(self):
        self._checked_wrong.clear()
        self._checked_cage_bad.clear()
        self._checked_cage_done.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    # ---- Painting ----

    def sizeHint(self):
        if self._puzzle is None:
            return super().sizeHint()
        n = self._puzzle.size
        return QSize(self._cell_size * n + 2, self._cell_size * n + 2)

    def paintEvent(self, event):
        if self._puzzle is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        n = self._puzzle.size

        # Calculate board size to fit widget, keeping square cells
        side = min(rect.width(), rect.height())
        cell = side / n
        offset_x = (rect.width() - side) / 2
        offset_y = (rect.height() - side) / 2

        # Draw background
        painter.fillRect(rect, self._bg_color)

        # Draw selection highlight first (so grid/cages appear over it)
        for r, c in self._selected_cells:
            sel_rect = QRectF(offset_x + c * cell, offset_y + r * cell, cell, cell)
            painter.fillRect(sel_rect, self._selected_color)

        # Highlight every cell that holds the same digit as the cursor cell
        anchor_value = self.user_value(*self._anchor_cell) if self._anchor_cell else 0
        if anchor_value:
            for r in range(n):
                for c in range(n):
                    if self.user_value(r, c) == anchor_value and (r, c) not in self._selected_cells:
                        cr = QRectF(offset_x + c * cell, offset_y + r * cell, cell, cell)
                        painter.fillRect(cr, self._same_digit_color)

        # Draw cage highlights (same cage as the cursor cell)
        if self._anchor_cell is not None:
            sel_cage = self._puzzle.cage_grid[self._anchor_cell[0]][self._anchor_cell[1]]
            for r in range(n):
                for c in range(n):
                    if self._puzzle.cage_grid[r][c] == sel_cage and (r, c) != self._anchor_cell:
                        cr = QRectF(offset_x + c * cell, offset_y + r * cell, cell, cell)
                        painter.fillRect(cr, self._highlight_color)

        # Draw cage borders (the only visible lines on the board)
        self._draw_cage_borders(painter, offset_x, offset_y, cell)

        # Draw cage sums
        self._draw_cage_sums(painter, offset_x, offset_y, cell)

        # Draw numbers
        self._draw_numbers(painter, offset_x, offset_y, cell)

        # Single cage selected: list the possible digit combinations
        self._draw_cage_combinations(painter, offset_x, offset_y, cell)

        # Several cages selected: show their combined target
        self._draw_selection_sum(painter, offset_x, offset_y, cell)

    def _complete_cages(self):
        """Return the cages fully covered by the selection, or [] if it is partial."""
        if self._puzzle is None or not self._selected_cells:
            return []
        selected = set(self._selected_cells)
        cages = []
        for cage_id in {self._puzzle.cage_grid[r][c] for r, c in self._selected_cells}:
            cage = self._puzzle.cages[cage_id]
            if not set(cage.cells).issubset(selected):
                return []
            cages.append(cage)
        if sum(len(c.cells) for c in cages) != len(selected):
            return []
        return sorted(cages, key=lambda c: c.index)

    def _draw_selection_sum(self, painter, ox, oy, cell):
        """Show the sum of cage totals when several whole cages are selected."""
        cages = self._complete_cages()
        if len(cages) < 2:
            return

        total = sum(c.sum_value for c in cages)
        text = f"Σ {total} · {len(cages)} cages"

        font = QFont()
        font.setPointSizeF(max(8.0, cell * 0.22))
        painter.setFont(font)
        metrics = QFontMetrics(font)

        pad_x, pad_y = 6.0, 3.0
        box_w = metrics.horizontalAdvance(text) + pad_x * 2
        box_h = metrics.height() + pad_y * 2

        cols = [c for _, c in self._selected_cells]
        rows = [r for r, _ in self._selected_cells]
        left = ox + min(cols) * cell
        right = ox + (max(cols) + 1) * cell
        top = oy + min(rows) * cell
        bottom = oy + (max(rows) + 1) * cell

        board_left = ox
        board_right = ox + self._puzzle.size * cell

        # Prefer the right side of the selection, fall back to the left
        if right + 4 + box_w <= board_right:
            box_x = right + 4
        elif left - 4 - box_w >= board_left:
            box_x = left - 4 - box_w
        else:
            box_x = max(board_left, board_right - box_w)

        box_y = top - box_h - 3
        if box_y < oy:
            box_y = bottom + 3
        if box_y + box_h > oy + self._puzzle.size * cell:
            box_y = max(oy, top + 3)

        pill = QRectF(box_x, box_y, box_w, box_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(70, 70, 70, 150))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(245, 245, 245, 210))
        painter.drawText(pill, Qt.AlignCenter, text)

    def _draw_cage_combinations(self, painter, ox, oy, cell):
        """List every digit combination that still fits the selected cage.

        Drawn as a tiny box in the bottom-left corner of the board.
        """
        cages = self._complete_cages()
        if len(cages) != 1:
            return

        cage = cages[0]
        lines = self._cage_combination_lines(cage)

        font = QFont()
        font.setPointSizeF(max(5.0, cell * 0.19))
        painter.setFont(font)
        metrics = QFontMetrics(font)

        max_lines = 5
        shown = lines[:max_lines]
        if len(lines) > max_lines:
            shown.append(f"… +{len(lines) - max_lines}")

        line_h = metrics.height() + 1
        box_w = max(metrics.horizontalAdvance(t) for t in shown) + 8
        box_h = line_h * len(shown) + 4

        n = self._puzzle.size
        box_x = ox + 3
        box_y = oy + n * cell - box_h - 3

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 30, 140))
        painter.drawRoundedRect(QRectF(box_x, box_y, box_w, box_h), 3, 3)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(240, 240, 240, 225))

        y = box_y + 2 + metrics.ascent()
        for line in shown:
            painter.drawText(QPointF(box_x + 4, y), line)
            y += line_h

    def _cage_combination_lines(self, cage) -> List[str]:
        """All distinct-digit combinations that still fill the cage."""
        values = [self.user_value(r, c) for r, c in cage.cells]
        used = {v for v in values if v}
        empty = len([v for v in values if not v])
        remaining = cage.sum_value - sum(used)

        if empty == 0:
            return ["✓" if remaining == 0 else f"✗ {remaining:+d}"]
        if remaining <= 0:
            return ["✗"]

        digits = [d for d in range(1, 10) if d not in used]
        combos = [c for c in combinations(digits, empty) if sum(c) == remaining]
        return [" ".join(str(d) for d in combo) for combo in combos] or ["—"]

    def _draw_cage_borders(self, painter, ox, oy, cell):
        """Draw thick borders between cells of different cages."""
        if self._puzzle is None:
            return
        n = self._puzzle.size
        pen = QPen(self._cage_border_color, self._cage_border_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        # For each cell, check if each edge needs a cage border
        for r in range(n):
            for c in range(n):
                my_cage = self._puzzle.cage_grid[r][c]

                # Top edge
                if r == 0 or self._puzzle.cage_grid[r - 1][c] != my_cage:
                    painter.drawLine(
                        QPointF(ox + c * cell, oy + r * cell),
                        QPointF(ox + (c + 1) * cell, oy + r * cell)
                    )
                # Bottom edge
                if r == n - 1 or self._puzzle.cage_grid[r + 1][c] != my_cage:
                    painter.drawLine(
                        QPointF(ox + c * cell, oy + (r + 1) * cell),
                        QPointF(ox + (c + 1) * cell, oy + (r + 1) * cell)
                    )
                # Left edge
                if c == 0 or self._puzzle.cage_grid[r][c - 1] != my_cage:
                    painter.drawLine(
                        QPointF(ox + c * cell, oy + r * cell),
                        QPointF(ox + c * cell, oy + (r + 1) * cell)
                    )
                # Right edge
                if c == n - 1 or self._puzzle.cage_grid[r][c + 1] != my_cage:
                    painter.drawLine(
                        QPointF(ox + (c + 1) * cell, oy + r * cell),
                        QPointF(ox + (c + 1) * cell, oy + (r + 1) * cell)
                    )

    def _draw_cage_sums(self, painter, ox, oy, cell):
        """Draw cage sum numbers at the top-left of the first cell of each cage."""
        if self._puzzle is None:
            return
        n = self._puzzle.size
        sum_font_size = max(5, int(cell * self._cage_sum_font_scale))
        font = QFont()
        font.setPointSizeF(sum_font_size)
        painter.setFont(font)
        painter.setPen(self._cage_sum_color)

        # Track which cages we've drawn
        drawn_cages = set()
        for r in range(n):
            for c in range(n):
                ci = self._puzzle.cage_grid[r][c]
                if ci in drawn_cages:
                    continue
                drawn_cages.add(ci)

                # Find the top-leftmost cell of this cage
                top_left = None
                for cr in range(n):
                    for cc in range(n):
                        if self._puzzle.cage_grid[cr][cc] == ci:
                            if top_left is None or cr < top_left[0] or (cr == top_left[0] and cc < top_left[1]):
                                top_left = (cr, cc)

                cage = self._puzzle.cages[ci]
                tr, tc = top_left
                tx = ox + tc * cell + 2
                ty = oy + tr * cell + sum_font_size + 1

                sum_text = str(cage.sum_value)

                # Verdicts appear only after the user presses Check
                if ci in self._checked_cage_bad:
                    painter.setPen(self._cage_error_color)
                elif ci in self._checked_cage_done:
                    painter.setPen(self._cage_done_color)
                else:
                    painter.setPen(self._cage_sum_color)

                painter.drawText(QPointF(tx, ty), sum_text)

    def _draw_numbers(self, painter, ox, oy, cell):
        """Draw committed values and pencil marks."""
        if self._puzzle is None:
            return
        n = self._puzzle.size
        font_size = max(10, int(cell * self._number_font_scale))

        fixed_font = QFont()
        fixed_font.setPointSizeF(font_size)
        if self._fixed_bold:
            fixed_font.setBold(True)

        user_font = QFont()
        user_font.setPointSizeF(font_size)

        pencil_font = QFont()
        pencil_font.setPointSizeF(max(4.0, cell * 0.21))

        for r in range(n):
            for c in range(n):
                val = self.user_value(r, c)

                if val == 0:
                    # Pencil candidates in a small 3x3 grid
                    digits = self._pencils[r][c]
                    if digits:
                        painter.setFont(pencil_font)
                        painter.setPen(self._pencil_color)
                        slot = cell / 3.0
                        for d in sorted(digits):
                            idx = d - 1
                            dr, dc = divmod(idx, 3)
                            sub = QRectF(
                                ox + c * cell + dc * slot,
                                oy + r * cell + dr * slot,
                                slot, slot,
                            )
                            painter.drawText(sub, Qt.AlignCenter, str(d))
                    continue

                if self._fixed_mask[r][c]:
                    painter.setFont(fixed_font)
                    painter.setPen(self._fixed_number_color)
                else:
                    painter.setFont(user_font)
                    painter.setPen(
                        self._check_error_color
                        if (r, c) in self._checked_wrong
                        else self._number_color
                    )

                text_rect = QRectF(ox + c * cell, oy + r * cell, cell, cell)
                painter.drawText(text_rect, Qt.AlignCenter, str(val))

    # ---- Mouse & Keyboard ----

    def _cell_from_pos(self, pos):
        """Convert widget position to (row, col) cell coordinates."""
        if self._puzzle is None:
            return None
        rect = self.rect()
        n = self._puzzle.size
        side = min(rect.width(), rect.height())
        cell = side / n
        offset_x = (rect.width() - side) / 2
        offset_y = (rect.height() - side) / 2

        x = pos.x() - offset_x
        y = pos.y() - offset_y
        if x < 0 or y < 0 or x >= side or y >= side:
            return None
        col = int(x / cell)
        row = int(y / cell)
        if 0 <= row < n and 0 <= col < n:
            return (row, col)
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        cell = self._cell_from_pos(event.position())
        if cell is not None:
            self._selected_cells = [cell]
            self._anchor_cell = cell
            self._dragging = True
            self.setFocus()
            self.cell_clicked.emit(cell[0], cell[1])
        else:
            self._selected_cells = []
            self._anchor_cell = None
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            cell = self._cell_from_pos(event.position())
            if cell is not None and cell not in self._selected_cells:
                self._selected_cells.append(cell)
                self._anchor_cell = cell
                self.cell_clicked.emit(cell[0], cell[1])
                self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._anchor_cell is None or self._puzzle is None:
            super().keyPressEvent(event)
            return

        row, col = self._anchor_cell
        key = event.key()

        # Number keys 1-9 (top row and keypad) fill every selected cell
        value = 0
        if Qt.Key_1 <= key <= Qt.Key_9:
            value = key - Qt.Key_0
        elif Qt.Key_0 <= key <= Qt.Key_9:
            value = key - Qt.Key_0

        if value:
            self._type_digit(value)
            event.accept()
            return

        # Delete/Backspace/Clear (also plain 0 on the number row)
        if key in (Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_C, Qt.Key_0):
            if key == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                super().keyPressEvent(event)
                return
            self._end_typing_session()
            for r, c in self._selected_cells or [(row, col)]:
                self.set_user_value(r, c, 0)
                self.value_entered.emit(r, c, 0)
            event.accept()
            return

        # Arrow keys
        row_move = 0
        col_move = 0
        if key == Qt.Key_Up:
            row_move = -1
        elif key == Qt.Key_Down:
            row_move = 1
        elif key == Qt.Key_Left:
            col_move = -1
        elif key == Qt.Key_Right:
            col_move = 1

        if row_move or col_move:
            n = self._puzzle.size
            new_r = (row + row_move) % n
            new_c = (col + col_move) % n
            self._anchor_cell = (new_r, new_c)
            self._selected_cells = [self._anchor_cell]
            self.cell_clicked.emit(new_r, new_c)
            self.update()
            event.accept()
            return

        super().keyPressEvent(event)

    def _type_digit(self, digit: int):
        """Commit a lone digit; accumulate several digits into pencil marks."""
        cells = [(r, c) for r, c in (self._selected_cells or [self._anchor_cell])
                 if r is not None and not self._fixed_mask[r][c]]
        if not cells:
            return

        signature = tuple(sorted(cells))
        same_session = self._type_timer.isActive() and self._typing_key == signature

        if same_session:
            if digit not in self._typing_digits:
                self._typing_digits.append(digit)
        else:
            self._typing_digits = [digit]
        self._typing_key = signature

        if len(self._typing_digits) == 1:
            for r, c in cells:
                self.set_user_value(r, c, digit)
                self.value_entered.emit(r, c, digit)
        else:
            digits = set(self._typing_digits)
            for r, c in cells:
                self.set_pencils(r, c, digits)
                self.value_entered.emit(r, c, 0)

        self._type_timer.start()

    def _end_typing_session(self):
        self._typing_key = None
        self._typing_digits = []
