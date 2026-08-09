from __future__ import annotations

from .credit_service import update_leave_credits as run_credit_update


def run_leave_credit_cron_update(leave_credit_model, sl_accrual_model, vl_accrual_model):
    """Cron wrapper used by scheduled task entrypoints."""
    return run_credit_update(leave_credit_model, sl_accrual_model, vl_accrual_model, from_cron=True)
