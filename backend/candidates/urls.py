from django.urls import path

from candidates import views

app_name = "candidates"

urlpatterns = [
    path("profile/", views.profile_edit_view, name="profile_edit"),
    path("consent/", views.general_consent_view, name="general_consent"),
    path("resumes/", views.resume_list_view, name="resume_list"),
    path("resumes/upload/", views.resume_upload_view, name="resume_upload"),
    path(
        "resumes/<uuid:resume_id>/download/",
        views.resume_download_view,
        name="resume_download",
    ),
]
