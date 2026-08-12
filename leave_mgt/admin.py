from django.contrib import admin
from .models import (
    LeaveCredit, LeaveCreditLog, LeaveCreditTransaction, LeavePolicy,
    LeaveRequest, SL_Accrual, VL_Accrual,
)

admin.site.register(LeaveCredit)
admin.site.register(SL_Accrual)
admin.site.register(VL_Accrual)
admin.site.register(LeaveRequest)
admin.site.register(LeaveCreditLog)
admin.site.register(LeavePolicy)
admin.site.register(LeaveCreditTransaction)
