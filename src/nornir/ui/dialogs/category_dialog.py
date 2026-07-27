"""Create/edit dialog for a category: name + color."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from nornir.ui.theming import category_icon

DEFAULT_COLOR = "#4A90D9"


class CategoryDialog(QDialog):
    """Small form dialog; use :meth:`get_values` for the common flow."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "New Category",
        name: str = "",
        color: str = DEFAULT_COLOR,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._color = color

        self._name_edit = QLineEdit(name)
        self._color_button = QPushButton()
        self._color_button.clicked.connect(self._pick_color)
        self._update_color_button()

        form = QFormLayout(self)
        form.addRow("Name:", self._name_edit)
        form.addRow("Color:", self._color_button)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    # -- interaction ---------------------------------------------------------

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(parent=self, title="Category color")
        if chosen.isValid():
            self._color = chosen.name()
            self._update_color_button()

    def _update_color_button(self) -> None:
        self._color_button.setIcon(category_icon(self._color))
        self._color_button.setText(self._color)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Nornir", "Category name must not be empty.")
            return
        self.accept()

    # -- results -------------------------------------------------------------

    def values(self) -> tuple[str, str]:
        """(name, color) as currently entered."""
        return self._name_edit.text().strip(), self._color

    @classmethod
    def get_values(
        cls,
        parent: QWidget | None,
        *,
        title: str = "New Category",
        name: str = "",
        color: str = DEFAULT_COLOR,
    ) -> tuple[str, str] | None:
        """Run modally; returns (name, color) or None when cancelled."""
        dialog = cls(parent, title=title, name=name, color=color)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.values()
        return None
