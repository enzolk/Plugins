# -*- coding: utf-8 -*-
from __future__ import annotations

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    from PySide2 import QtWidgets, QtCore


class ShortcutSummaryDialog(QtWidgets.QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Maya Shortcut Logger Summary")
        self.resize(980, 460)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Shortcuts", "Executed actions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
            | QtWidgets.QAbstractItemView.SelectedClicked
        )
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)

        add_separator_btn = QtWidgets.QPushButton("Add separator")
        add_separator_btn.clicked.connect(self._add_separator)
        btn_row.addWidget(add_separator_btn)

        up_btn = QtWidgets.QPushButton("Up")
        up_btn.clicked.connect(self._move_selected_up)
        btn_row.addWidget(up_btn)

        down_btn = QtWidgets.QPushButton("Down")
        down_btn.clicked.connect(self._move_selected_down)
        btn_row.addWidget(down_btn)

        rename_btn = QtWidgets.QPushButton("Rename action")
        rename_btn.clicked.connect(self._rename_selected_action)
        btn_row.addWidget(rename_btn)

        delete_btn = QtWidgets.QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch(1)

        self._is_refreshing = False
        self._row_to_select = None
        self.refresh()

    def _selected_row_index(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return -1
        return indexes[0].row()

    def _add_separator(self):
        self.manager.store.add_separator()

    def _move_selected_up(self):
        row = self._selected_row_index()
        if row <= 0:
            return
        self._row_to_select = row - 1
        self.manager.store.move_row(row, row - 1)

    def _move_selected_down(self):
        row = self._selected_row_index()
        row_count = self.table.rowCount()
        if row < 0 or row >= row_count - 1:
            return
        self._row_to_select = row + 1
        self.manager.store.move_row(row, row + 1)

    def _delete_selected(self):
        row = self._selected_row_index()
        if row < 0:
            return
        self.manager.store.delete_row(row)

    def _rename_selected_action(self):
        row = self._selected_row_index()
        if row < 0:
            return
        data = self.manager.store.table_rows()
        if row >= len(data):
            return
        entry = data[row]
        if entry.get("type") != "entry":
            return

        current_name = entry.get("action_display") or ""
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename executed action",
            "Displayed action name:",
            text=current_name,
        )
        if not ok:
            return
        self.manager.store.rename_action(row, new_name)

    def _on_item_changed(self, item):
        if self._is_refreshing:
            return
        row = item.row()
        col = item.column()
        data = self.manager.store.table_rows()
        if row < 0 or row >= len(data):
            return
        entry = data[row]

        if entry.get("type") == "separator":
            if col == 1:
                self.manager.store.rename_separator(row, item.text())
            else:
                self.refresh()
            return

        if entry.get("type") == "entry" and col == 1:
            self.manager.store.rename_action(row, item.text())

    def refresh(self):
        rows = self.manager.store.table_rows()
        self._is_refreshing = True
        try:
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                if row.get("type") == "separator":
                    left = QtWidgets.QTableWidgetItem("────────")
                    left.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    right = QtWidgets.QTableWidgetItem(row.get("label") or "──────────")
                    right.setFlags(
                        QtCore.Qt.ItemIsEnabled
                        | QtCore.Qt.ItemIsSelectable
                        | QtCore.Qt.ItemIsEditable
                    )
                else:
                    left = QtWidgets.QTableWidgetItem(row.get("shortcut") or "")
                    left.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    right = QtWidgets.QTableWidgetItem(row.get("action_display") or row.get("action_original") or "")
                    right.setToolTip("Original action: {}".format(row.get("action_original") or ""))
                    right.setFlags(
                        QtCore.Qt.ItemIsEnabled
                        | QtCore.Qt.ItemIsSelectable
                        | QtCore.Qt.ItemIsEditable
                    )
                self.table.setItem(r, 0, left)
                self.table.setItem(r, 1, right)

            if self._row_to_select is not None and rows:
                target = max(0, min(self._row_to_select, len(rows) - 1))
                self.table.selectRow(target)
            self._row_to_select = None
            self.table.resizeColumnsToContents()
        finally:
            self._is_refreshing = False
