from django.urls import path

from .views import department_detail, department_index, internal_howto_step_completion

app_name = "departments"

urlpatterns = [
    path("", department_index, name="list"),
    path("internal-how-tos/steps/<int:step_id>/completion/", internal_howto_step_completion, name="internal_howto_step_completion"),
    path("<slug:slug>/", department_detail, name="detail"),
]
