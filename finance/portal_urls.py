from django.urls import path

from . import portal_views

app_name = "finance_operations"

urlpatterns = [
    path("", portal_views.overview, name="overview"),
]
