from django.urls import path

from . import views

app_name = "social_welfare"

urlpatterns = [
    path("", views.program_list, name="program_list"),
    path("new/", views.program_create, name="program_create"),
    path("<int:pk>/", views.program_detail, name="program_detail"),
    path("<int:pk>/edit/", views.program_update, name="program_update"),
    path("<int:program_pk>/activities/new/", views.activity_create, name="activity_create"),
    path("activities/<int:pk>/edit/", views.activity_update, name="activity_update"),
]
