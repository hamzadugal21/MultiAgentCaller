from django.urls import path

from .views import (
    EmailLoginView,
    SecureLogoutView,
    admin_dashboard_view,
    agent_demo_view,
    candidate_dashboard_view,
    dashboard_view,
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
    path("agents/demo/", agent_demo_view, name="agent_demo"),
]
