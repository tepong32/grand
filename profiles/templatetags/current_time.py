from django import template
from datetime import datetime

register = template.Library()

@register.simple_tag
def current_time():
    return datetime.now()


'''
In using this custom template tag on another app while it is store here on users app, you can copy the following format on the template:

<!-- example: home_template.html (in home app) -->
{% load current_time from user %}  <!-- Load the templatetag from the user app -->
<p>Current time: {% current_time %}</p>
OR
<p>Current time: {% now "Y-m-d H:i:s" %}</p> <!-- This will display the current time in the format YYYY-MM-DD HH:MM:SS -->

'''