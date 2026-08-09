from __future__ import annotations

from decimal import Decimal

from leave_mgt.models import LeaveCredit


def get_accrual_value(accrual_model, default_value):
    accrual = accrual_model.objects.first()
    return accrual.accrual_value if accrual else default_value


def reset_accrual_flags(LeaveCreditModel=LeaveCredit):
    return LeaveCreditModel.objects.update(credits_accrued_this_month=False)


def accrue_leave_instance(leave_credit, sl_accrual_value, vl_accrual_value):
    leave_credit.current_year_sl_credits += sl_accrual_value
    leave_credit.current_year_vl_credits += vl_accrual_value
    leave_credit.credits_accrued_this_month = True
    leave_credit.save()


def accrue_all_leave_credits(LeaveCreditModel, SL_Accrual, VL_Accrual):
    from leave_mgt.models import LeaveCreditLog

    default_sl_accrual = Decimal('1.2')
    default_vl_accrual = Decimal('1.2')

    sl_accrual_value = get_accrual_value(SL_Accrual, default_sl_accrual)
    vl_accrual_value = get_accrual_value(VL_Accrual, default_vl_accrual)

    leave_credits = LeaveCreditModel.objects.filter(credits_accrued_this_month=False)
    for leave_credit in leave_credits:
        accrue_leave_instance(leave_credit, sl_accrual_value, vl_accrual_value)
        LeaveCreditLog.objects.create(action_type='Monthly credit accruals', leave_credits=leave_credit)

    return leave_credits.count()


def carry_over_unused_credits(LeaveCreditModel):
    count = 0
    for leave_credit in LeaveCreditModel.objects.all():
        leave_credit.carry_over_credits()
        count += 1
    return count


def leave_credit_is_first_day():
    from django.utils import timezone

    today = timezone.now().date()
    return today.month == 1 and today.day == 1


def update_leave_credits(LeaveCreditModel, SL_Accrual, VL_Accrual, from_cron=False):
    reset_accrual_flags(LeaveCreditModel)

    carry_over_count = 0
    if from_cron and leave_credit_is_first_day():
        carry_over_count = carry_over_unused_credits(LeaveCreditModel)

    accrued_count = accrue_all_leave_credits(LeaveCreditModel, SL_Accrual, VL_Accrual)

    return {
        'carry_over_count': carry_over_count,
        'accrued_count': accrued_count,
    }
