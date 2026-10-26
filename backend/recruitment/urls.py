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
    path("jobs/<uuid:job_id>/apply/", views.application_create_view, name="application_create"),
    path("applications/", views.application_list_view, name="application_list"),
    path("applications/<uuid:application_id>/", views.application_detail_view, name="application_detail"),
    path("applications/<uuid:application_id>/consent/", views.application_consent_view, name="application_consent"),
    path("applications/<uuid:application_id>/withdraw/", views.application_withdraw_view, name="application_withdraw"),
]
