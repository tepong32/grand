from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Leave, LeaveCounter
from users.models import User
from django.utils import timezone
from datetime import timedelta


@receiver(post_save, sender=Leave)
def check_reset_dates(sender, instance, **kwargs):
    # Check if today's date matches reset dates
    '''
        This function automatically checks for certain dates (every 1st day of the 1st month of the quarter) to trigger the reset_counters() of the LeaveCounter model
        Do not forget to connect signal this to apps.py
    '''
    today = timezone.now().date()
    if today.month in [1, 4, 7, 10] and today.day == 1:
        leave_counter, _ = LeaveCounter.objects.get_or_create(employee=instance.employee)
        leave_counter.reset_counters()


@receiver(post_save, sender=User)
def create_leave_counter(sender, instance, created, **kwargs):
    '''
        Creating a LeaveCounter instance for every User that registers
    '''
    if created:
        LeaveCounter.objects.create(employee=instance)


@receiver(post_save, sender=Leave)
def create_or_update_leave_counter(sender, instance, created, **kwargs):
    '''
        leave_counter counts will increase when a leave is approved,
        decrease when an "approved" leave is "cancelled"
    '''
    leave_counter, created = LeaveCounter.objects.get_or_create(employee=instance.employee)
    leave_duration = (instance.end_date - instance.start_date).days + 1 # include both start and end dates
    if created:
        if instance.status == 'approved':
            ### if created and then auto-approved
            leave_counter.instances_used_this_year += leave_duration
            leave_counter.instances_used_this_quarter += leave_duration
    else:
        original_leave = sender.objects.get(pk=instance.pk)
        original_duration = (original_leave.end_date - original_leave.start_date).days + 1

        if instance.status == 'approved':
            leave_counter.instances_used_this_year += leave_duration
            leave_counter.instances_used_this_quarter += leave_duration

        ### updates counter everytime the status changes from "approved" to any other status
        ### (this may be a cause of exploit so I removed and replaced it with the elif clause below)
        # if original_leave.status == 'approved':
        #     leave_counter.instances_used_this_year -= original_duration
        #     leave_counter.instances_used_this_quarter -= original_duration

        elif original_leave.status == 'approved' and instance.status == 'cancelled':
            ### if the leave was previously "approved" then changed to "cancelled", subtract instances from used instances count
            leave_counter.instances_used_this_year -= original_duration
            leave_counter.instances_used_this_quarter -= original_duration
    leave_counter.save()

@receiver(post_delete, sender=User)
def delete_leave_counter(sender, instance, **kwargs):
    '''
        decreases the counts of LeaveCounter when Leave instances are deleted
    '''
    leave_counter, created = LeaveCounter.objects.get_or_create(user=instance)
    leave_duration = (instance.end_date - instance.start_date).days + 1 # Include both start and end dates
    leave_counter.instances_used_this_year -= leave_duration
    leave_counter.instances_used_this_quarter -= leave_duration
    leave_counter.save()
