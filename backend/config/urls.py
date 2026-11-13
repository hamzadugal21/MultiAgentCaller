from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("candidate/", include("candidates.urls")),
    path("recruitment/", include("recruitment.urls")),
    path("interviews/", include("interviews.urls")),
    path("calling/", include("calling.urls")),
    path("", include("accounts.urls")),
]

if getattr(settings, "ADMIN_INTERFACE_ENABLED", True):
    urlpatterns.insert(1, path("admin/", admin.site.urls))
