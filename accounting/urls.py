from django.urls import path

from . import views


app_name = "accounting"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("setup/", views.setup_workspace, name="setup"),
    path("setup/<slug:kind>/new/", views.setup_item_create, name="setup_create"),
    path("setup/<slug:kind>/<int:pk>/edit/", views.setup_item_edit, name="setup_edit"),
    path("setup/<slug:kind>/<int:pk>/toggle/", views.setup_item_toggle, name="setup_toggle"),
    path("setup/periods/<int:pk>/close/", views.period_close, name="period_close"),
    path("journals/new/", views.entry_create, name="entry_create"),
    path("journals/<uuid:public_id>/", views.entry_detail, name="entry_detail"),
    path("journals/<uuid:public_id>/edit/", views.entry_edit, name="entry_edit"),
    path("journals/<uuid:public_id>/lines/new/", views.line_create, name="line_create"),
    path("journals/<uuid:public_id>/lines/<int:pk>/edit/", views.line_edit, name="line_edit"),
    path("journals/<uuid:public_id>/lines/<int:pk>/delete/", views.line_delete, name="line_delete"),
    path("journals/<uuid:public_id>/submit/", views.entry_submit, name="entry_submit"),
    path("journals/<uuid:public_id>/post/", views.entry_post, name="entry_post"),
    path("journals/<uuid:public_id>/return/", views.entry_return, name="entry_return"),
    path("journals/<uuid:public_id>/discard/", views.entry_discard, name="entry_discard"),
    path("ledger/", views.ledger, name="ledger"),
    path("trial-balance/", views.trial_balance, name="trial_balance"),
]
