from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("candidate/", include("candidates.urls")),
    path("recruitment/", include("recruitment.urls")),
    path("", include("accounts.urls")),
]
