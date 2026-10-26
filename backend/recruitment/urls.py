from django.urls import path

from recruitment import views

app_name = "recruitment"

urlpatterns = [
    path("jobs/", views.job_list_view, name="job_list"),
    path("jobs/new/", views.job_create_view, name="job_create"),
    path("jobs/<uuid:job_id>/", views.job_detail_view, name="job_detail"),
    path("jobs/<uuid:job_id>/edit/", views.job_edit_view, name="job_edit"),
    path("jobs/<uuid:job_id>/state/", views.job_state_view, name="job_state"),
    path("jobs/<uuid:job_id>/skills/", views.job_skill_view, name="job_skill"),
    path(
        "jobs/<uuid:job_id>/questions/",
        views.job_question_view,
        name="job_question",
    ),
    path("jobs/<uuid:job_id>/faqs/", views.job_faq_view, name="job_faq"),
]
