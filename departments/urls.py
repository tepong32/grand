from django.urls import path

from .views import department_detail, department_index

app_name = "departments"

urlpatterns = [
    path("", department_index, name="list"),
    path("<slug:slug>/", department_detail, name="detail"),
]
