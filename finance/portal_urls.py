from django.urls import path

from . import portal_views

app_name = "finance_operations"

urlpatterns = [
    path("", portal_views.overview, name="overview"),
    path("my-work/export/", portal_views.my_work_export, name="my_work_export"),
    path("my-work/", portal_views.my_work, name="my_work"),
]
