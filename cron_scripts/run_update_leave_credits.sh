#!/bin/bash


####### NC file locs applied

# Activate the virtual environment
source /home/abutdtks/virtualenv/prototype.abutchikikz.online/3.11/bin/activate

# Set the Django settings module
export DJANGO_SETTINGS_MODULE="src.settings"

# Run the Django management command
/home/abutdtks/virtualenv/prototype.abutchikikz.online/3.11/bin/python3 /home/abutdtks/prototype.abutchikikz.online/manage.py update_leave_credits >> /home/abutdtks/prototype.abutchikikz.online/logs/cron.log 2>&1


######################### IN CPANEL
# */5 * * * * = nc only allows every-5-min cron jobs
# export DJANGO_SETTINGS_MODULE="/home/abutdtks/prototype.abutchikikz.online/src/settings" && /home/abutdtks/virtualenv/prototype.abutchikikz.online/3.11/bin/python3 /home/abutdtks/prototype.abutchikikz.online/manage.py crontab run 46b0aaf9a1d1b585bc9e7c0f64ef9d0b # django-cronjobs for src

### please note that the python3 path will be changed to python3.11_bin or something if you add the task thru crontab.
### manually edit the line in cPanel cronjobs UI.
### export line for DJANGO_SETTINGS_MODULE seems to also be required.