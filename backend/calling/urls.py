from django.urls import path

from calling import views

app_name = "calling"

urlpatterns = [
    path("review/bulk-schedule/", views.bulk_schedule_view, name="bulk_schedule"),
    path("", views.candidate_session_list, name="candidate_session_list"),
    path(
        "schedules/<uuid:schedule_id>/prepare/",
        views.prepare_session,
        name="prepare_session",
    ),
    path(
        "sessions/<uuid:session_id>/",
        views.candidate_session_detail,
        name="candidate_session_detail",
    ),
    path(
        "sessions/<uuid:session_id>/start/",
        views.start_or_resume_session,
        name="start_or_resume_session",
    ),
    path(
        "sessions/<uuid:session_id>/pause/",
        views.pause_session,
        name="pause_session",
    ),
    path(
        "sessions/<uuid:session_id>/answer/",
        views.submit_answer,
        name="submit_answer",
    ),
    path(
        "sessions/<uuid:session_id>/transcribe/",
        views.transcribe_answer,
        name="transcribe_answer",
    ),
    path(
        "sessions/<uuid:session_id>/speak-question/",
        views.speak_question,
        name="speak_question",
    ),
    path(
        "sessions/<uuid:session_id>/cancel/",
        views.cancel_candidate_session,
        name="cancel_candidate_session",
    ),
    path(
        "sessions/<uuid:session_id>/request-human/",
        views.request_human_review,
        name="request_human_review",
    ),
    path("review/", views.recruiter_session_list, name="recruiter_session_list"),
    path(
        "review/<uuid:session_id>/",
        views.recruiter_session_detail,
        name="recruiter_session_detail",
    ),
    path(
        "review/<uuid:session_id>/cancel/",
        views.cancel_review_session,
        name="cancel_review_session",
    ),
]
