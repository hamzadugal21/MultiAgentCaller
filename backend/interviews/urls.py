from django.urls import path

from interviews import views

app_name = "interviews"

urlpatterns = [
    path(
        "applications/<uuid:application_id>/evaluation/start/",
        views.evaluation_start_view,
        name="evaluation_start",
    ),
    path(
        "evaluations/<uuid:evaluation_id>/review/",
        views.evaluation_review_view,
        name="evaluation_review",
    ),
    path(
        "applications/<uuid:application_id>/invite/",
        views.invitation_create_view,
        name="invitation_create",
    ),
    path(
        "schedules/<uuid:schedule_id>/activate/",
        views.pending_activate_view,
        name="pending_activate",
    ),
    path(
        "schedules/<uuid:schedule_id>/reschedule/",
        views.reschedule_request_view,
        name="reschedule_request",
    ),
    path(
        "reschedule-requests/<uuid:request_id>/review/",
        views.reschedule_review_view,
        name="reschedule_review",
    ),
    path(
        "schedules/<uuid:schedule_id>/cancel/",
        views.schedule_cancel_view,
        name="schedule_cancel",
    ),
    path(
        "schedules/<uuid:schedule_id>/expire/",
        views.schedule_expire_view,
        name="schedule_expire",
    ),
]
