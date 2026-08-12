from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction

from django.shortcuts import render, redirect
from django.urls import reverse_lazy

from .forms import LeaveApplicationForm, LeaveCreditAdjustmentForm, LeavePolicyForm
from .models import LeaveRequest, LeaveCredit, LeaveCreditTransaction, LeavePolicy
from .services.request_service import (
    build_leave_dashboard_context,
    validate_request_payload,
    revert_leave_credit_for_deleted_request,
)
from .services.policy_service import apply_manual_adjustment, can_manage_leave_credits
from .utils import calculate_yearly_leave_usage

from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    )

from django.utils import timezone

from profiles.models import EmployeeProfile


class RoleBasedTemplateMixin(UserPassesTestMixin):
    '''
        This mixin is used to determine what template to display to the user depending on roles:
        Normal user vs Superuser/Admin.
        Add more logic to test_func() as needed.
        Create separate html pages as needed.
    '''
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def get_template_names(self):
        if self.test_func():
            return ['leave_mgt/leave_summary_admin.html']  # template for admins
        return ['leave_mgt/leave_summary.html']            # template for normal users #########################not used atm


class MyLeaveView(LoginRequiredMixin, ListView):
    """
    View for displaying the logged-in user's leave requests and related stats.
    """
    model = LeaveRequest
    template_name = 'leave_mgt/leave_summary.html'
    ordering = ['-date_filed']
    context_object_name = 'leave_requests'  # optional: so you can just use {{ leave_requests }}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            leave_credit = self.request.user.employeeprofile.leavecredit
            status_filter = self.request.GET.get('status') or None
            context.update(build_leave_dashboard_context(leave_credit, status_filter=status_filter))
            context['active_leave_policy'] = LeavePolicy.objects.filter(is_active=True).first()
            context['can_manage_leave_credits'] = can_manage_leave_credits(self.request.user)

        except (EmployeeProfile.DoesNotExist, LeaveCredit.DoesNotExist):
            # Fallback context in case of missing data
            context.update({
                'leave_credits': None,
                'cy_sl': 0,
                'cy_vl': 0,
                'approved_leaves': [],
                'approved_leave_count': 0,
                'current_year': timezone.now().year,
                'current_yr_leave_usage': 0,
                'total_leave_taken': 0,
                'average_leave_per_month': 0,
                'sl_vs_vl_usage': {},
                'accrual_logs': [],
                'leave_requests': [],
            })

        return context



class HRLeaveDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'leave_mgt/hr_dashboard.html'

    def test_func(self):
        return can_manage_leave_credits(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_requests = LeaveRequest.objects.select_related('employee').all()

        # Example: usage stats across employees
        context['all_leave_usage'] = calculate_yearly_leave_usage(all_requests)

        return context


class LeaveDashboardContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            credit = self.request.user.employeeprofile.leavecredit
            context.update(build_leave_dashboard_context(credit))
        except (EmployeeProfile.DoesNotExist, LeaveCredit.DoesNotExist):
            pass
        context['active_leave_policy'] = LeavePolicy.objects.filter(is_active=True).first()
        context['can_manage_leave_credits'] = can_manage_leave_credits(self.request.user)
        return context


class LeaveApplicationCreateView(LoginRequiredMixin, LeaveDashboardContextMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application.html'
    success_url = "leave_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        employee = self.request.user.employeeprofile.leavecredit
        leave_type = form.cleaned_data['leave_type']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        day_portion = form.cleaned_data['day_portion']

        try:
            number_of_days = validate_request_payload(
                leave_credit=employee,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                day_portion=day_portion,
            )
            form.instance.number_of_days = number_of_days
        except ValidationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        # If checks pass, create the leave record
        form.instance.employee = employee  # Set the employee field
        super().form_valid(form)

        messages.success(self.request, "Leave application submitted successfully.")
        return redirect('leave_list')  # Redirect to a success page

class OwnedLeaveRequestMixin:
    def get_queryset(self):
        return LeaveRequest.objects.filter(
            employee__employee__user=self.request.user,
            status='PENDING',
        )


class LeaveApplicationUpdateView(LoginRequiredMixin, OwnedLeaveRequestMixin, LeaveDashboardContextMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application.html'
    success_url = "leave_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        leave_type = form.cleaned_data['leave_type']
        employee = self.request.user.employeeprofile.leavecredit
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        day_portion = form.cleaned_data['day_portion']

        try:
            number_of_days = validate_request_payload(
                leave_credit=employee,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                exclude_pk=form.instance.pk,
                current_status=form.instance.status,
                current_request=form.instance,
                day_portion=day_portion,
            )
            form.instance.number_of_days = number_of_days
        except ValidationError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)

        super().form_valid(form)
        messages.success(self.request, "Leave application updated successfully.")
        return redirect('leave_list')  # Redirect to a success page


class LeaveApplicationDetailView(LoginRequiredMixin, OwnedLeaveRequestMixin, LeaveDashboardContextMixin, DetailView):
    model = LeaveRequest
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application_detail.html'


class LeaveApplicationDeleteView(LoginRequiredMixin, OwnedLeaveRequestMixin, LeaveDashboardContextMixin, DeleteView):
    model = LeaveRequest
    template_name = 'leave_mgt/leave_application_delete.html'
    success_url = reverse_lazy('leave_list')  # Redirect to leave_mgt/ (MyLeaveView) view after deletion

    def delete(self, request, *args, **kwargs):
        leave = self.get_object()
        revert_leave_credit_for_deleted_request(leave)

        # Call the superclass delete method
        response = super().delete(request, *args, **kwargs)
        # Add a success message
        messages.success(self.request, "Leave application deleted.")

        return response


class LeaveManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'leave_mgt/leave_management.html'
    raise_exception = True

    def test_func(self):
        return can_manage_leave_credits(self.request.user)

    def _context(self, **kwargs):
        return {
            'policy_form': kwargs.get('policy_form') or LeavePolicyForm(
                instance=LeavePolicy.objects.filter(is_active=True).first()
            ),
            'adjustment_form': kwargs.get('adjustment_form') or LeaveCreditAdjustmentForm(),
            'active_policy': LeavePolicy.objects.filter(is_active=True).first(),
            'recent_transactions': LeaveCreditTransaction.objects.select_related(
                'leave_credit__employee__user', 'actor'
            )[:30],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._context())
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'policy':
            policy_form = LeavePolicyForm(request.POST)
            if policy_form.is_valid():
                with transaction.atomic():
                    LeavePolicy.objects.filter(is_active=True).update(is_active=False)
                    policy = policy_form.save(commit=False)
                    policy.is_active = True
                    policy.created_by = request.user
                    policy.save()
                messages.success(request, "The new leave policy is now active.")
                return redirect('leave_manage')
            context = self._context(policy_form=policy_form)
        elif action == 'adjustment':
            adjustment_form = LeaveCreditAdjustmentForm(request.POST)
            if adjustment_form.is_valid():
                try:
                    apply_manual_adjustment(
                        leave_credit=adjustment_form.cleaned_data['leave_credit'],
                        leave_type=adjustment_form.cleaned_data['leave_type'],
                        amount=adjustment_form.cleaned_data['amount'],
                        actor=request.user,
                        reason=adjustment_form.cleaned_data['reason'],
                    )
                except ValidationError as exc:
                    adjustment_form.add_error('amount', exc)
                else:
                    messages.success(request, "Leave credit adjustment recorded.")
                    return redirect('leave_manage')
            context = self._context(adjustment_form=adjustment_form)
        else:
            messages.error(request, "Unknown leave management action.")
            return redirect('leave_manage')
        return render(request, self.template_name, context)
