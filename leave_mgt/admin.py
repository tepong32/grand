from django.contrib import admin
from .models import LeaveCredit, SL_Accrual, VL_Accrual, LeaveRequest, LeaveCreditLog

admin.site.register(LeaveCredit)
admin.site.register(SL_Accrual)
admin.site.register(VL_Accrual)
admin.site.register(LeaveRequest)
admin.site.register(LeaveCreditLog)