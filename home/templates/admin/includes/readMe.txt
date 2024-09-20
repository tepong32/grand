This template folder is for overriding incompatibility of the 'length_is' filter from django5.0 downwards to newer versions
Trick is to change 'length_is:' to 'length =='


see https://stackoverflow.com/questions/78874958/invalid-filter-length-is-error-in-django-template-how-to-fix

Recommended Update

Instead of using length_is:'n', update your template to use the length filter with the == operator:

Old syntax:

{% if value|length_is:'n' %}...{% endif %}
New syntax:

{% if value|length == n %}...{% endif %}
You can also handle alternative outputs like this:

{% if value|length == n %}True{% else %}False{% endif %}
This approach aligns with Django's recommended practices and ensures your templates are forward-compatible.