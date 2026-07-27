"""Tiny shared widget builders."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from nornir.db.template_repo import TemplateRepo


def template_combo(repo: TemplateRepo, *, none_label: str | None = None) -> QComboBox:
    """A combo of active templates (id in userData), optionally with a
    leading 'none' entry whose data is None."""
    combo = QComboBox()
    if none_label is not None:
        combo.addItem(none_label, None)
    for template in repo.list_templates():
        combo.addItem(template.name, template.id)
    return combo
