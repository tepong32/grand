"""Bounded, nonpersistent line entry shared by the inventory preparation sheets."""
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet

MAX_DRAFT_LINES = 50


class DraftLines(BaseFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["DELETE"].label = "Leave this line out of the preview (uncheck to include again)"

    def clean(self):
        super().clean()
        if (self.management_form.cleaned_data.get("TOTAL_FORMS", 0) < len(self.initial or [])
                or self.initial_form_count() != len(self.initial or [])):
            raise ValidationError("The line count is invalid. Reopen the preparation sheet and enter the supplied lines again.")


def add_lines(data, line_set, *, initial=None):
    lines = line_set(data, prefix="lines", initial=initial)
    notice = ""
    if lines.management_form.is_valid():
        total = lines.management_form.cleaned_data["TOTAL_FORMS"]
        if len(initial or []) <= total <= MAX_DRAFT_LINES and lines.initial_form_count() == len(initial or []):
            added = min(5, MAX_DRAFT_LINES - total)
            data = data.copy()
            data["lines-TOTAL_FORMS"] = str(total + added)
            lines = line_set(data, prefix="lines", initial=initial)
            notice = (f"Added {added} lines. Your entries are retained; preview when ready." if added
                      else "This sheet has 50 lines. Your entries are retained; preview when ready.")
    return lines, notice
