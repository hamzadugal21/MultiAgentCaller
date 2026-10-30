from django.urls import path

from .views import (
    EmailLoginView,
    SecureLogoutView,
    admin_dashboard_view,
    candidate_dashboard_view,
    dashboard_view,
    email_verification_confirm_view,
    email_verification_request_view,
    email_verification_resend_view,
    home_view,
    how_it_works_view,
    recruiter_dashboard_view,
    signup_view,
)

app_name = "accounts"


urlpatterns = [
    path("", home_view, name="home"),
    path("how-it-works/", how_it_works_view, name="how_it_works"),
    path("signup/", signup_view, name="signup"),
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", SecureLogoutView.as_view(), name="logout"),
    path(
        "email/verify/request/",
        email_verification_request_view,
        name="email_verification_request",
    ),
    path(
        "email/verify/resend/",
        email_verification_resend_view,
        name="email_verification_resend",
    ),
    path(
        "email/verify/<str:token>/",
        email_verification_confirm_view,
        name="email_verification_confirm",
    ),
    path("dashboard/", dashboard_view, name="dashboard"),
    path(
        "dashboard/candidate/",
        candidate_dashboard_view,
        name="candidate_dashboard",
    ),
    path(
        "dashboard/recruiter/",
        recruiter_dashboard_view,
        name="recruiter_dashboard",
    ),
    path(
        "dashboard/administrator/",
        admin_dashboard_view,
        name="admin_dashboard",
    ),
]
