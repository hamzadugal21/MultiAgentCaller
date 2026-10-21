from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import CandidateSignupForm, EmailLoginForm
from .models import User


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = CandidateSignupForm(request.POST)

        if form.is_valid():
            user = form.save()

            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

            messages.success(
                request,
                "Your candidate account was created successfully.",
            )

            return redirect("accounts:candidate_dashboard")
    else:
        form = CandidateSignupForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form},
    )


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("accounts:dashboard")


class SecureLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


def role_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                raise PermissionDenied

            return view_function(request, *args, **kwargs)

        return wrapped_view

    return decorator


@login_required
def dashboard_view(request):
    dashboard_routes = {
        User.Role.CANDIDATE: "accounts:candidate_dashboard",
        User.Role.RECRUITER: "accounts:recruiter_dashboard",
        User.Role.ADMIN: "accounts:admin_dashboard",
    }

    route = dashboard_routes.get(request.user.role)

    if route is None:
        raise PermissionDenied

    return redirect(route)


@role_required(User.Role.CANDIDATE)
def candidate_dashboard_view(request):
    return render(
        request,
        "accounts/candidate_dashboard.html",
    )


@role_required(User.Role.RECRUITER)
def recruiter_dashboard_view(request):
    return render(
        request,
        "accounts/recruiter_dashboard.html",
    )


@role_required(User.Role.ADMIN)
def admin_dashboard_view(request):
    return render(
        request,
        "accounts/admin_dashboard.html",
    )
