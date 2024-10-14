from django.urls import path, include
from .views import *

urlpatterns = [
    path('<username>/', MyLeaveView.as_view(), name="my-leaves"),

    ]