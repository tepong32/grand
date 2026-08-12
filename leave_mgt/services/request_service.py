from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


def calculate_request_days(start_date, end_date, day_portion='FULL'):
    """
    Return working days between two dates, inclusive.
    """
    if not start_date or not end_date:
        raise ValidationError("Start date and end date are required.")

    if end_date < start_date:
        raise ValidationError("Start date cannot be greater than end date.")

    total_days = (end_date - start_date).days + 1
    weekend_days = sum(
        1
        for day in range(total_days)
        if (start_date + timedelta(days=day)).weekday() >= 5
    )
    working_days = total_days - weekend_days
    if day_portion in ('AM', 'PM'):
        if start_date != end_date:
            raise ValidationError("Half-day leave must cover one working day only.")
        if working_days != 1:
            raise ValidationError("Half-day leave must fall on a working day.")
        return Decimal('0.5')
    return Decimal(working_days)


def calculate_yearly_leave_usage(leave_requests):
    """
    Calculate aggregate leave usage statistics for the current year.
    """
    if leave_requests is None:
        return {
            'total_leave_taken': 0,
            'average_leave_per_month': 0,
            'sl_vs_vl_usage': {'SL': 0, 'VL': 0},
        }

    current_year = timezone.now().year
    total_days = 0
    leave_per_month = defaultdict(int)
    sl_vs_vl = {'SL': 0, 'VL': 0}

    approved = leave_requests.filter(status='APPROVED', start_date__year=current_year)
    for req in approved:
        req_days = req.number_of_days or 0
        total_days += req_days
        leave_per_month[req.start_date.month] += req_days

        if req.leave_type in sl_vs_vl:
            sl_vs_vl[req.leave_type] += req_days

    months_used = len(leave_per_month)
    average_per_month = round(total_days / months_used, 2) if months_used else 0

    return {
        'total_leave_taken': total_days,
        'average_leave_per_month': average_per_month,
        'sl_vs_vl_usage': sl_vs_vl,
    }


def has_request_conflict(employee, start_date, end_date, exclude_pk=None):
    from leave_mgt.models import LeaveRequest

    base_q = LeaveRequest.objects.filter(
        employee=employee,
        status__in=['PENDING', 'APPROVED'],
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    if exclude_pk:
        base_q = base_q.exclude(pk=exclude_pk)

    return base_q.exists()


def get_leave_credit_balance(leave_credit, leave_type):
    if leave_type == 'SL':
        return leave_credit.total_sl_credits
    if leave_type == 'VL':
        return leave_credit.total_vl_credits
    if leave_type == 'SP':
        return leave_credit.current_year_special_credits
    return None


def validate_request_payload(
    leave_credit,
    leave_type,
    start_date,
    end_date,
    exclude_pk: Optional[int] = None,
    current_status: Optional[str] = None,
    current_request=None,
    day_portion='FULL',
):
    """
    Validate request draft payload before persistence.
    """
    if not leave_credit:
        raise ValidationError("Employee leave credit record is required.")

    if leave_type not in ['SL', 'VL', 'SP']:
        raise ValidationError("Unsupported leave type.")

    number_of_days = calculate_request_days(start_date, end_date, day_portion)
    if number_of_days <= 0:
        raise ValidationError("Leave period must include at least one day.")
    from .credit_service import get_active_policy
    policy = get_active_policy(start_date)
    increment = policy.minimum_request_increment if policy else Decimal('0.50')
    if number_of_days % increment != 0:
        raise ValidationError(f"Leave must be requested in increments of {increment} day.")

    # Keep overlapping leaves blocked for all statuses except canceled requests.
    if current_status != 'CANCELLED' and has_request_conflict(
        leave_credit,
        start_date,
        end_date,
        exclude_pk=exclude_pk
    ):
        raise ValidationError("This leave period overlaps with another pending or approved request.")

    balance = get_leave_credit_balance(leave_credit, leave_type)
    if current_request and current_status == 'APPROVED':
        # If updating an already-approved request, its existing days should be rolled back
        # before checking the new period to keep validation aligned with the transition logic.
        if current_request.leave_type == leave_type:
            balance += current_request.number_of_days
    if balance is None:
        raise ValidationError("Unsupported leave type.")

    if balance < 0:
        raise ValidationError("Leave credit balance is invalid.")
    if balance - number_of_days < 0:
        raise ValidationError("Insufficient leave credits.")

    return number_of_days
def sync_leave_credit_for_status_change(leave_request, old_status=None, old_leave_type=None, old_number_of_days=None):
    """
    Update LeaveCredit balances when request status/type/duration changes.
    """
    from leave_mgt.models import LeaveCredit, LeaveCreditTransaction, LeaveRequest

    if not isinstance(leave_request, LeaveRequest):
        raise ValidationError("Invalid leave request provided.")

    old_status = old_status or None
    old_leave_type = old_leave_type or leave_request.leave_type
    old_number_of_days = 0 if old_number_of_days is None else old_number_of_days

    if old_number_of_days < 0:
        raise ValidationError("Request day count cannot be negative.")

    old_number_of_days = Decimal(old_number_of_days)

    def _bucket_names(leave_type):
        if leave_type == 'SL':
            return 'current_year_sl_credits', 'sl_credits_from_prev_yr'
        if leave_type == 'VL':
            return 'current_year_vl_credits', 'vl_credits_from_prev_yr'
        if leave_type == 'SP':
            return 'current_year_special_credits', None
        raise ValidationError("Unsupported leave type.")

    def _balance(credit, leave_type):
        return get_leave_credit_balance(credit, leave_type)

    def _reverse_previous(credit):
        previous = LeaveCreditTransaction.objects.filter(
            leave_request=leave_request,
            transaction_type='DEDUCTION',
            reversal__isnull=True,
        ).order_by('-created_at', '-pk').first()
        current_field, carried_field = _bucket_names(old_leave_type)
        if previous:
            setattr(credit, current_field, getattr(credit, current_field) - previous.current_delta)
            if carried_field:
                setattr(credit, carried_field, getattr(credit, carried_field) - previous.carried_delta)
            credit.save(update_fields=[field for field in (current_field, carried_field) if field])
            LeaveCreditTransaction.objects.create(
                leave_credit=credit,
                leave_type=old_leave_type,
                transaction_type='REVERSAL',
                amount=-previous.amount,
                current_delta=-previous.current_delta,
                carried_delta=-previous.carried_delta,
                balance_after=_balance(credit, old_leave_type),
                leave_request=leave_request,
                reversal_of=previous,
                reason='Reversed an earlier approved leave deduction.',
            )
            return

        # Existing approved records predate the transaction ledger.
        setattr(credit, current_field, getattr(credit, current_field) + old_number_of_days)
        credit.save(update_fields=[current_field])

    def _deduct(credit, leave_type, amount):
        amount = Decimal(amount)
        current_field, carried_field = _bucket_names(leave_type)
        available = _balance(credit, leave_type)
        if available < amount:
            raise ValidationError("Insufficient leave credits.")

        carried_used = Decimal('0')
        if carried_field:
            carried_used = min(getattr(credit, carried_field), amount)
            setattr(credit, carried_field, getattr(credit, carried_field) - carried_used)
        current_used = amount - carried_used
        setattr(credit, current_field, getattr(credit, current_field) - current_used)
        credit.save(update_fields=[field for field in (current_field, carried_field) if field])

        LeaveCreditTransaction.objects.create(
            leave_credit=credit,
            leave_type=leave_type,
            transaction_type='DEDUCTION',
            amount=-amount,
            current_delta=-current_used,
            carried_delta=-carried_used,
            balance_after=_balance(credit, leave_type),
            leave_request=leave_request,
            reason=f"Approved leave request #{leave_request.pk}",
        )

    with transaction.atomic():
        credit = LeaveCredit.objects.select_for_update().get(pk=leave_request.employee.pk)
        if (
            old_status == 'APPROVED'
            and leave_request.status == 'APPROVED'
            and old_leave_type == leave_request.leave_type
            and old_number_of_days == Decimal(leave_request.number_of_days)
        ):
            return

        # Revert old approved snapshot first so status/type changes and duration edits are consistent.
        if old_status == 'APPROVED':
            _reverse_previous(credit)

        # Apply new state if request ends in approved state.
        if leave_request.status == 'APPROVED':
            _deduct(credit, leave_request.leave_type, leave_request.number_of_days)


def revert_leave_credit_for_deleted_request(leave_request):
    """
    Return leave credits for approved requests before deletion.
    """
    if leave_request.status != 'APPROVED':
        return

    from leave_mgt.models import LeaveCredit, LeaveCreditTransaction

    with transaction.atomic():
        credit = LeaveCredit.objects.select_for_update().get(pk=leave_request.employee.pk)
        previous = LeaveCreditTransaction.objects.filter(
            leave_request=leave_request,
            transaction_type='DEDUCTION',
            reversal__isnull=True,
        ).order_by('-created_at', '-pk').first()
        if previous:
            if leave_request.leave_type == 'SL':
                current_field, carried_field = 'current_year_sl_credits', 'sl_credits_from_prev_yr'
            elif leave_request.leave_type == 'VL':
                current_field, carried_field = 'current_year_vl_credits', 'vl_credits_from_prev_yr'
            else:
                current_field, carried_field = 'current_year_special_credits', None
            setattr(credit, current_field, getattr(credit, current_field) - previous.current_delta)
            if carried_field:
                setattr(credit, carried_field, getattr(credit, carried_field) - previous.carried_delta)
            credit.save(update_fields=[field for field in (current_field, carried_field) if field])
            LeaveCreditTransaction.objects.create(
                leave_credit=credit,
                leave_type=leave_request.leave_type,
                transaction_type='REVERSAL',
                amount=-previous.amount,
                current_delta=-previous.current_delta,
                carried_delta=-previous.carried_delta,
                balance_after=get_leave_credit_balance(credit, leave_request.leave_type),
                leave_request=leave_request,
                reversal_of=previous,
                reason='Approved request deleted.',
            )


def build_leave_dashboard_context(employee_leave_credit, status_filter=None):
    """
    Centralized context for user leave dashboards.
    """
    from leave_mgt.models import LeaveCreditTransaction, LeaveRequest

    leave_requests = LeaveRequest.objects.filter(employee=employee_leave_credit).order_by('-date_filed')
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)

    approved_requests = LeaveRequest.objects.filter(employee=employee_leave_credit, status='APPROVED')

    current_year = timezone.now().year
    current_yr_leave_usage = approved_requests.filter(start_date__year=current_year).count()

    stats = calculate_yearly_leave_usage(approved_requests)

    sl_used = approved_requests.filter(leave_type='SL', start_date__year=current_year).aggregate(
        total=Sum('number_of_days')
    ).get('total') or 0
    vl_used = approved_requests.filter(leave_type='VL', start_date__year=current_year).aggregate(
        total=Sum('number_of_days')
    ).get('total') or 0

    monthly_leave_data = []
    for month in range(1, 13):
        monthly_leave_data.append(
            approved_requests.filter(start_date__month=month).aggregate(
                total=Sum('number_of_days')
            ).get('total') or 0
        )

    return {
        'leave_credits': employee_leave_credit,
        'cy_sl': employee_leave_credit.total_sl_credits,
        'cy_vl': employee_leave_credit.total_vl_credits,
        'approved_leaves': approved_requests,
        'approved_leave_count': approved_requests.count(),
        'current_year': current_year,
        'current_yr_leave_usage': current_yr_leave_usage,
        'total_leave_taken': stats['total_leave_taken'],
        'average_leave_per_month': stats['average_leave_per_month'],
        'sl_vs_vl_usage': stats['sl_vs_vl_usage'],
        'sl_used': sl_used,
        'vl_used': vl_used,
        'sl_earned': employee_leave_credit.current_year_sl_credits + (sl_used or 0),
        'vl_earned': employee_leave_credit.current_year_vl_credits + (vl_used or 0),
        'monthly_leave_data': monthly_leave_data,
        'accrual_logs': LeaveCreditTransaction.objects.filter(
            leave_credit=employee_leave_credit
        ).order_by('-created_at', '-pk')[:50],
        'leave_requests': leave_requests,
    }
