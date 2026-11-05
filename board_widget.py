"""Killer Sudoku board widget with transparent background support."""

from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
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
        self._selected_cells: List[Tuple[int, int]] = []  # drag-selectable cells
        self._anchor_cell: Optional[Tuple[int, int]] = None  # cursor cell
        self._dragging = False
        self._fixed_mask: List[List[bool]] = []  # True for given cells

        # Visual settings
        self._bg_color = QColor(0, 0, 0, 0)  # fully transparent bg
        self._grid_color = QColor(80, 80, 80, 200)
        self._cage_border_color = QColor(40, 40, 40, 255)
        self._cage_border_width = 1.5
        self._thick_grid_width = 1.5
        self._thin_grid_width = 0.8
        self._number_color = QColor(20, 20, 20, 255)
        self._fixed_number_color = QColor(20, 20, 20, 255)
        self._cage_sum_color = QColor(80, 80, 80, 255)
        self._cage_done_color = QColor(40, 160, 80, 255)
        self._cage_error_color = QColor(200, 60, 60, 255)
        self._selected_color = QColor(100, 150, 255, 100)
        self._highlight_color = QColor(200, 220, 255, 60)
        self._error_color = QColor(200, 50, 50, 180)
        self._same_digit_color = QColor(255, 200, 80, 75)
        self._cell_size = 40  # base cell size
        self._cage_sum_font_scale = 0.35
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
        self._fixed_mask = [[puzzle.cells[r][c] != 0 for c in range(size)] for r in range(size)]
        self._selected_cells = []
        self._anchor_cell = None
        self.update()

    def set_background_color(self, color: QColor):
        self._bg_color = color
        self.update()

    def set_grid_color(self, color: QColor):
        self._grid_color = color
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
        self.update()

    def clear_user_values(self):
        if self._puzzle:
            size = self._puzzle.size
            self._user_values = [[0] * size for _ in range(size)]
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    # ---- Painting ----

    def sizeHint(self):
        if self._puzzle is None:
            return super().sizeHint()
        n = self._puzzle.size
        return self._cell_size * n + 2, self._cell_size * n + 2

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

        # Draw cell backgrounds for conflicting cells
        self._draw_conflicts(painter, offset_x, offset_y, cell)

        # Draw thin grid lines
        painter.setPen(QPen(self._grid_color, self._thin_grid_width))
        for i in range(n + 1):
            x = offset_x + i * cell
            y = offset_y + i * cell
            painter.drawLine(QPointF(x, offset_y), QPointF(x, offset_y + n * cell))
            painter.drawLine(QPointF(offset_x, y), QPointF(offset_x + n * cell, y))

        # Draw thick nonet lines
        painter.setPen(QPen(self._grid_color, self._thick_grid_width))
        nr = self._puzzle.num_rows_nonet
        nc = self._puzzle.num_cols_nonet
        for i in range(0, n + 1, nc):
            x = offset_x + i * cell
            painter.drawLine(QPointF(x, offset_y), QPointF(x, offset_y + n * cell))
        for j in range(0, n + 1, nr):
            y = offset_y + j * cell
            painter.drawLine(QPointF(offset_x, y), QPointF(offset_x + n * cell, y))

        # Draw cage borders (thick lines on edges)
        self._draw_cage_borders(painter, offset_x, offset_y, cell)

        # Draw cage sums
        self._draw_cage_sums(painter, offset_x, offset_y, cell)

        # Draw numbers
        self._draw_numbers(painter, offset_x, offset_y, cell)

        # Draw the running total beside the current selection
        self._draw_selection_sum(painter, offset_x, offset_y, cell)

    def _selection_stats(self) -> Tuple[int, int, int]:
        """Return (sum of filled cells, filled count, selected count)."""
        values = [self.user_value(r, c) for r, c in self._selected_cells]
        filled = [v for v in values if v]
        return sum(filled), len(filled), len(values)

    def _draw_selection_sum(self, painter, ox, oy, cell):
        """Draw a small pill with the selection total next to the selection."""
        if self._puzzle is None or len(self._selected_cells) < 2:
            return

        total, filled, count = self._selection_stats()
        text = f"Σ {total}  ({filled}/{count})"

        font = QFont()
        font.setPointSizeF(max(9.0, cell * 0.28))
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
        painter.setBrush(QColor(25, 25, 25, 205))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(pill, Qt.AlignCenter, text)

    def _draw_conflicts(self, painter, ox, oy, cell):
        """Draw red background on conflicting cells."""
        if self._puzzle is None:
            return
        n = self._puzzle.size
        has_conflict = False
        conflict_cells = set()

        for r in range(n):
            for c in range(n):
                v = self.user_value(r, c)
                if v == 0:
                    continue
                # Check row
                for c2 in range(n):
                    if c2 != c and self.user_value(r, c2) == v:
                        conflict_cells.add((r, c))
                        conflict_cells.add((r, c2))
                        has_conflict = True
                # Check column
                for r2 in range(n):
                    if r2 != r and self.user_value(r2, c) == v:
                        conflict_cells.add((r, c))
                        conflict_cells.add((r2, c))
                        has_conflict = True
                # Check cage
                cage_r = self._puzzle.cage_grid[r][c]
                for r2 in range(n):
                    for c2 in range(n):
                        if (r2, c2) != (r, c) and self._puzzle.cage_grid[r2][c2] == cage_r:
                            if self.user_value(r2, c2) == v:
                                conflict_cells.add((r, c))
                                conflict_cells.add((r2, c2))
                                has_conflict = True

        # Check nonet
        nr = self._puzzle.num_rows_nonet
        nc = self._puzzle.num_cols_nonet
        for r in range(n):
            for c in range(n):
                v = self.user_value(r, c)
                if v == 0:
                    continue
                br = (r // nr) * nr
                bc = (c // nc) * nc
                for r2 in range(br, br + nr):
                    for c2 in range(bc, bc + nc):
                        if (r2, c2) != (r, c) and self.user_value(r2, c2) == v:
                            conflict_cells.add((r, c))
                            conflict_cells.add((r2, c2))

        if has_conflict:
            painter.fillRect(self.rect(), Qt.transparent)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._error_color)
            for r, c in conflict_cells:
                cr = QRectF(ox + c * cell + 1, oy + r * cell + 1, cell - 2, cell - 2)
                painter.drawRect(cr)

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
        sum_font_size = max(6, int(cell * self._cage_sum_font_scale))
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

                fm = QFontMetrics(font)
                sum_text = str(cage.sum_value)

                # Colour the sum when the cage is complete / over target
                values = [self.user_value(r, c) for r, c in cage.cells]
                filled = [v for v in values if v]
                current = sum(filled)
                if len(filled) == len(cage.cells) and current == cage.sum_value:
                    painter.setPen(self._cage_done_color)
                elif current > cage.sum_value:
                    painter.setPen(self._cage_error_color)
                else:
                    painter.setPen(self._cage_sum_color)

                painter.drawText(QPointF(tx, ty), sum_text)

    def _draw_numbers(self, painter, ox, oy, cell):
        """Draw numbers in cells."""
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

        for r in range(n):
            for c in range(n):
                val = self.user_value(r, c)
                if val == 0:
                    continue

                cx = ox + c * cell + cell / 2
                cy = oy + r * cell + cell / 2

                if self._fixed_mask[r][c]:
                    painter.setFont(fixed_font)
                    painter.setPen(self._fixed_number_color)
                else:
                    painter.setFont(user_font)
                    painter.setPen(self._number_color)

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
            for r, c in self._selected_cells or [(row, col)]:
                self.set_user_value(r, c, value)
                self.value_entered.emit(r, c, value)
            event.accept()
            return

        # Delete/Backspace/Clear (also plain 0 on the number row)
        if key in (Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_C, Qt.Key_0):
            if key == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                super().keyPressEvent(event)
                return
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
