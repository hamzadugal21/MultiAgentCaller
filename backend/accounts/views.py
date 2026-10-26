from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_POST

from .email_verification_services import (
    EmailVerificationError,
    create_email_verification_challenge,
    resend_email_verification_challenge,
    verify_email_verification_token,
)
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


def _deliver_verification(request, issued):
    confirm_url = request.build_absolute_uri(
        reverse("accounts:email_verification_confirm", args=(issued.token,))
    )
    send_mail(
        "Verify your email address",
        f"Verify your email address using this link: {confirm_url}",
        getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
        [issued.challenge.user.email],
        fail_silently=False,
    )


@require_POST
@role_required(User.Role.CANDIDATE)
def email_verification_request_view(request):
    try:
        issued = create_email_verification_challenge(user=request.user)
        _deliver_verification(request, issued)
    except (EmailVerificationError, OSError):
        pass
    messages.info(
        request,
        "If verification is available, a new verification message has been sent.",
    )
    return redirect("accounts:candidate_dashboard")


@require_POST
@role_required(User.Role.CANDIDATE)
def email_verification_resend_view(request):
    try:
        issued = resend_email_verification_challenge(user=request.user)
        _deliver_verification(request, issued)
    except (EmailVerificationError, OSError):
        pass
    messages.info(
        request,
        "If verification is available, a new verification message has been sent.",
    )
    return redirect("accounts:candidate_dashboard")


def _verification_attempt_key(request):
    if request.session.session_key is None:
        request.session.create()
    return salted_hmac(
        "accounts.email-verification.browser-attempt.v1",
        request.session.session_key,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def email_verification_confirm_view(request, token):
    if request.method == "POST":
        try:
            user = verify_email_verification_token(
                token=token,
                attempt_key=_verification_attempt_key(request),
            )
        except EmailVerificationError:
            return render(
                request,
                "accounts/email_verification_result.html",
                {"verified": False},
                status=400,
            )
        if request.user.is_authenticated and request.user.pk == user.pk:
            messages.success(request, "Your email address is verified.")
            return redirect("accounts:candidate_dashboard")
        return render(
            request,
            "accounts/email_verification_result.html",
            {"verified": True},
        )
    return render(
        request,
        "accounts/email_verification_confirm.html",
        {"token": token},
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
