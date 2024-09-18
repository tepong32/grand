These are the pages that will be shown to authenticated users.
They will be separate for easier future modifications (if needed).




----------------------------------------------------------------------------------------
The mother-html page is the "base.html" located at the root of the "home" folder.
All html pages in here should have the format:

{% extends "home/base.html" %}
{% block content %}
  <your content here>
{% endblock content %}