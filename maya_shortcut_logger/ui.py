# -*- coding: utf-8 -*-
from __future__ import annotations

try:
    from PySide6 import QtWidgets
except Exception:
    from PySide2 import QtWidgets


class ShortcutSummaryDialog(QtWidgets.QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Maya Shortcut Logger Summary")
        self.resize(900, 420)

        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Shortcuts", "Executed actions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)

        clear_btn = QtWidgets.QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch(1)

        self.refresh()

    def _clear_history(self):
        self.manager.store.edges = {}
        self.manager.store.save()
        self.refresh()

    def refresh(self):
        rows = self.manager.store.components()
        self.table.setRowCount(len(rows))
        for r, (shortcuts, actions) in enumerate(rows):
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(", ".join(shortcuts)))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(", ".join(actions)))
        self.table.resizeColumnsToContents()
