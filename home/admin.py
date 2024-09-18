from django.contrib import admin
from .models import Leave, LeaveType, LeaveCounter

admin.site.register(Leave)
admin.site.register(LeaveType)
admin.site.register(LeaveCounter)