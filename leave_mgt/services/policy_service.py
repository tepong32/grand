from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from leave_mgt.models import LeaveCredit, LeaveCreditTransaction
from .credit_service import get_active_policy


def can_manage_leave_credits(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.has_perm('leave_mgt.manage_leave_credits'):
        return True
    return user.managed_departments.filter(slug='hr').exists()


def validate_increment(amount, increment):
    amount = Decimal(amount)
    increment = Decimal(increment)
    if amount == 0:
        raise ValidationError("Adjustment amount cannot be zero.")
    if increment <= 0 or abs(amount) % increment != 0:
        raise ValidationError(f"Amount must be in increments of {increment} day.")
    return amount


def apply_manual_adjustment(*, leave_credit, leave_type, amount, actor, reason):
    if not can_manage_leave_credits(actor):
        raise PermissionDenied("You cannot adjust employee leave credits.")
    policy = get_active_policy()
    increment = policy.minimum_request_increment if policy else Decimal('0.50')
    amount = validate_increment(amount, increment)

    with transaction.atomic():
        credit = LeaveCredit.objects.select_for_update().get(pk=leave_credit.pk)
        if leave_type == 'SL':
            if credit.total_sl_credits + amount < 0:
                raise ValidationError("Adjustment would make sick leave credits negative.")
            current_delta, carried_delta = amount, Decimal('0')
            if amount < 0:
                carried_used = min(credit.sl_credits_from_prev_yr, abs(amount))
                carried_delta = -carried_used
                current_delta = amount - carried_delta
                credit.sl_credits_from_prev_yr += carried_delta
            credit.current_year_sl_credits += current_delta
            fields = ['current_year_sl_credits', 'sl_credits_from_prev_yr']
            balance = credit.total_sl_credits
        elif leave_type == 'VL':
            if credit.total_vl_credits + amount < 0:
                raise ValidationError("Adjustment would make vacation leave credits negative.")
            current_delta, carried_delta = amount, Decimal('0')
            if amount < 0:
                carried_used = min(credit.vl_credits_from_prev_yr, abs(amount))
                carried_delta = -carried_used
                current_delta = amount - carried_delta
                credit.vl_credits_from_prev_yr += carried_delta
            credit.current_year_vl_credits += current_delta
            fields = ['current_year_vl_credits', 'vl_credits_from_prev_yr']
            balance = credit.total_vl_credits
        elif leave_type == 'SP':
            new_value = credit.current_year_special_credits + amount
            if new_value < 0:
                raise ValidationError("Adjustment would make special leave credits negative.")
            credit.current_year_special_credits = new_value
            current_delta, carried_delta = amount, Decimal('0')
            fields = ['current_year_special_credits']
            balance = new_value
        else:
            raise ValidationError("Unsupported leave type.")

        credit.save(update_fields=fields)
        return LeaveCreditTransaction.objects.create(
            leave_credit=credit,
            leave_type=leave_type,
            transaction_type='ADJUSTMENT',
            amount=amount,
            current_delta=current_delta,
            carried_delta=carried_delta,
            balance_after=balance,
            policy=policy,
            actor=actor,
            reason=reason,
        )
