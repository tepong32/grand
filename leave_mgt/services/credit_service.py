from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from leave_mgt.models import LeaveCredit, LeaveCreditTransaction, LeavePolicy


DEFAULT_MONTHLY_ACCRUAL = Decimal('1.20')


def get_active_policy(on_date=None):
    on_date = on_date or timezone.localdate()
    policy = LeavePolicy.objects.filter(
        is_active=True, effective_from__lte=on_date
    ).order_by('-effective_from', '-pk').first()
    if policy:
        return policy
    return LeavePolicy.objects.filter(is_active=True).order_by('-effective_from', '-pk').first()


def get_accrual_value(accrual_model, default_value):
    """Compatibility helper retained for legacy callers."""
    accrual = accrual_model.objects.first()
    return accrual.accrual_value if accrual else default_value


def reset_accrual_flags(LeaveCreditModel=LeaveCredit):
    """Legacy compatibility only; period transactions now provide idempotence."""
    return LeaveCreditModel.objects.update(credits_accrued_this_month=False)


def _period_start(value=None):
    value = value or timezone.localdate()
    return date(value.year, value.month, 1)


def _balance_for_type(credit, leave_type):
    if leave_type == 'SL':
        return credit.total_sl_credits
    if leave_type == 'VL':
        return credit.total_vl_credits
    return credit.current_year_special_credits


def accrue_leave_instance(leave_credit, policy, period=None):
    period = _period_start(period)
    accruals = {
        'SL': policy.monthly_sick_accrual,
        'VL': policy.monthly_vacation_accrual,
    }
    created_count = 0

    with transaction.atomic():
        credit = LeaveCredit.objects.select_for_update().get(pk=leave_credit.pk)
        for leave_type, amount in accruals.items():
            if LeaveCreditTransaction.objects.filter(
                leave_credit=credit,
                leave_type=leave_type,
                transaction_type='ACCRUAL',
                period=period,
            ).exists():
                continue

            if leave_type == 'SL':
                credit.current_year_sl_credits += amount
                update_field = 'current_year_sl_credits'
            else:
                credit.current_year_vl_credits += amount
                update_field = 'current_year_vl_credits'
            credit.credits_accrued_this_month = True
            credit.save(update_fields=[update_field, 'credits_accrued_this_month'])

            try:
                LeaveCreditTransaction.objects.create(
                    leave_credit=credit,
                    leave_type=leave_type,
                    transaction_type='ACCRUAL',
                    amount=amount,
                    current_delta=amount,
                    balance_after=_balance_for_type(credit, leave_type),
                    period=period,
                    policy=policy,
                    reason=f"Automatic monthly accrual for {period:%B %Y}",
                )
            except IntegrityError:
                # The database constraint is the final guard if two schedulers race.
                raise
            created_count += 1

    return created_count


def accrue_all_leave_credits(LeaveCreditModel=LeaveCredit, SL_Accrual=None, VL_Accrual=None, period=None):
    period = _period_start(period)
    policy = get_active_policy(period)
    if policy is None:
        return 0

    accrued_employees = 0
    for credit_id in LeaveCreditModel.objects.values_list('pk', flat=True).iterator():
        credit = LeaveCreditModel.objects.get(pk=credit_id)
        if accrue_leave_instance(credit, policy, period):
            accrued_employees += 1
    return accrued_employees


def carry_over_leave_instance(leave_credit, policy=None, on_date=None):
    on_date = on_date or timezone.localdate()
    period = date(on_date.year, 1, 1)
    policy = policy or get_active_policy(period)
    created_count = 0

    with transaction.atomic():
        credit = LeaveCredit.objects.select_for_update().get(pk=leave_credit.pk)
        configurations = [
            ('SL', 'current_year_sl_credits', 'sl_credits_from_prev_yr',
             policy.sick_carryover_cap if policy else None),
            ('VL', 'current_year_vl_credits', 'vl_credits_from_prev_yr',
             policy.vacation_carryover_cap if policy else Decimal('20')),
        ]
        for leave_type, current_field, carried_field, cap in configurations:
            if LeaveCreditTransaction.objects.filter(
                leave_credit=credit,
                leave_type=leave_type,
                transaction_type='CARRYOVER',
                period=period,
            ).exists():
                continue
            current_amount = getattr(credit, current_field)
            existing_carried = getattr(credit, carried_field)
            new_carried = existing_carried + current_amount
            if cap is not None:
                new_carried = min(new_carried, cap)
            carried_delta = new_carried - existing_carried
            setattr(credit, current_field, Decimal('0'))
            setattr(credit, carried_field, new_carried)
            credit.save(update_fields=[current_field, carried_field])
            LeaveCreditTransaction.objects.create(
                leave_credit=credit,
                leave_type=leave_type,
                transaction_type='CARRYOVER',
                amount=-current_amount + carried_delta,
                current_delta=-current_amount,
                carried_delta=carried_delta,
                balance_after=_balance_for_type(credit, leave_type),
                period=period,
                policy=policy,
                reason=f"Yearly carry-over for {on_date.year}",
            )
            created_count += 1

        if not LeaveCreditTransaction.objects.filter(
            leave_credit=credit,
            leave_type='SP',
            transaction_type='CARRYOVER',
            period=period,
        ).exists():
            allocation = policy.special_leave_annual_allocation if policy else Decimal('10')
            delta = allocation - credit.current_year_special_credits
            credit.current_year_special_credits = allocation
            credit.save(update_fields=['current_year_special_credits'])
            LeaveCreditTransaction.objects.create(
                leave_credit=credit,
                leave_type='SP',
                transaction_type='CARRYOVER',
                amount=delta,
                current_delta=delta,
                balance_after=allocation,
                period=period,
                policy=policy,
                reason=f"Annual special leave allocation for {on_date.year}",
            )
            created_count += 1
    return created_count


def carry_over_unused_credits(LeaveCreditModel=LeaveCredit, on_date=None):
    on_date = on_date or timezone.localdate()
    policy = get_active_policy(on_date)
    count = 0
    for leave_credit in LeaveCreditModel.objects.all().iterator():
        if carry_over_leave_instance(leave_credit, policy=policy, on_date=on_date):
            count += 1
    return count


def leave_credit_is_first_day(on_date=None):
    today = on_date or timezone.localdate()
    return today.month == 1 and today.day == 1


def update_leave_credits(LeaveCreditModel=LeaveCredit, SL_Accrual=None, VL_Accrual=None, from_cron=False, on_date=None):
    on_date = on_date or timezone.localdate()
    carry_over_count = 0
    if from_cron and leave_credit_is_first_day(on_date):
        carry_over_count = carry_over_unused_credits(LeaveCreditModel, on_date=on_date)

    accrued_count = accrue_all_leave_credits(
        LeaveCreditModel, SL_Accrual, VL_Accrual, period=on_date
    )
    return {'carry_over_count': carry_over_count, 'accrued_count': accrued_count}
