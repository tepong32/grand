Since there should not be information displayed when the user is not logged-in yet,
the "unauthed" folder will contain login, logout and sign-up pages.
+ some other information the admins want to convey to their users such as Announcements, perhaps?



----------------------------------------------------------------------------------------
The mother-html page is the "base.html" located at the root of the "home" folder.
All html pages in here should have the format:

{% extends "home/base.html" %}
{% block content %}
  <your content here>
{% endblock content %}