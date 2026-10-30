from datetime import timedelta
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Count, Prefetch, Q
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_POST

from auditlog.models import AuditEvent
from interviews.models import InterviewSchedule
from recruitment.models import (
    Company,
    JobApplication,
    JobPosting,
    RecruiterProfile,
)

from .email_verification_services import (
    EmailVerificationError,
    create_email_verification_challenge,
    resend_email_verification_challenge,
    verify_email_verification_token,
)
from .forms import CandidateSignupForm, EmailLoginForm
from .models import User


def home_view(request):
    return render(request, "accounts/home.html")


def how_it_works_view(request):
    return render(request, "accounts/how_it_works.html")


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
    profile = request.user.candidate_profile
    applications = profile.applications.select_related(
        "job",
        "job__company",
    ).order_by("-applied_at")
    active_application_count = applications.exclude(
        status__in=(
            JobApplication.Status.REJECTED,
            JobApplication.Status.WITHDRAWN,
        )
    ).count()
    upcoming_interviews = InterviewSchedule.objects.filter(
        application__candidate=profile,
        is_current=True,
        status__in=(
            InterviewSchedule.Status.PENDING,
            InterviewSchedule.Status.CONFIRMED,
        ),
        scheduled_start__gte=timezone.now(),
    ).select_related(
        "application__job",
        "application__job__company",
    )
    active_resume = profile.resumes.filter(is_active=True).first()
    skill_count = profile.candidate_skills.count()

    completion_checks = (
        bool(request.user.first_name and request.user.last_name),
        bool(profile.phone_number and profile.city),
        bool(profile.professional_summary),
        skill_count >= 2,
        active_resume is not None,
        profile.ai_processing_consent,
    )
    profile_completion = round(
        100 * sum(completion_checks) / len(completion_checks)
    )
    remaining_profile_actions = []
    if not completion_checks[0]:
        remaining_profile_actions.append("Add your full name")
    if not completion_checks[1]:
        remaining_profile_actions.append("Add contact and location details")
    if not completion_checks[2]:
        remaining_profile_actions.append("Add a professional summary")
    if not completion_checks[3]:
        remaining_profile_actions.append("Add at least two skills")
    if not completion_checks[4]:
        remaining_profile_actions.append("Upload your current résumé")
    if not completion_checks[5]:
        remaining_profile_actions.append("Review AI processing consent")

    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()

    return render(
        request,
        "accounts/candidate_dashboard.html",
        {
            "active_application_count": active_application_count,
            "active_resume": active_resume,
            "display_name": display_name,
            "initials": initials,
            "profile": profile,
            "profile_completion": profile_completion,
            "recent_applications": applications[:3],
            "remaining_profile_actions": remaining_profile_actions[:2],
            "upcoming_interview": upcoming_interviews.first(),
            "upcoming_interview_count": upcoming_interviews.count(),
        },
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
    try:
        recruiter = RecruiterProfile.objects.select_related("company", "user").get(
            user=request.user,
            user__is_active=True,
            user__role=User.Role.RECRUITER,
            is_verified=True,
            company__is_active=True,
        )
    except RecruiterProfile.DoesNotExist as error:
        raise PermissionDenied from error
    if not (recruiter.can_manage_jobs or recruiter.can_review_candidates):
        raise PermissionDenied

    now = timezone.now()
    eligible_deadline = Q(application_deadline__isnull=True) | Q(
        application_deadline__gt=now
    )
    company_jobs = JobPosting.objects.filter(company=recruiter.company)
    active_jobs = company_jobs.filter(
        eligible_deadline,
        status=JobPosting.Status.OPEN,
    ).annotate(applicant_count=Count("applications"))
    company_applications = JobApplication.objects.filter(
        job__company=recruiter.company
    )
    current_schedules = InterviewSchedule.objects.filter(is_current=True)
    recent_applications = list(
        company_applications.select_related("candidate__user", "job")
        .prefetch_related(
            Prefetch(
                "interview_schedules",
                queryset=current_schedules,
                to_attr="current_schedules",
            )
        )
        .order_by("-applied_at")[:4]
    )
    recent_application_entries = []
    for application in recent_applications:
        schedule = (
            application.current_schedules[0]
            if application.current_schedules
            else None
        )
        is_confirmed = (
            schedule is not None
            and schedule.status == InterviewSchedule.Status.CONFIRMED
        )
        candidate_name = application.candidate.user.get_full_name().strip()
        recent_application_entries.append(
            {
                "application": application,
                "candidate_name": candidate_name or "Candidate",
                "display_status": (
                    "Interview confirmed"
                    if is_confirmed
                    else application.get_status_display()
                ),
                "status_class": (
                    "confirmed" if is_confirmed else application.status
                ),
            }
        )

    local_now = timezone.localtime(now)
    week_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start -= timedelta(days=week_start.weekday())
    week_end = week_start + timedelta(days=7)
    upcoming_interviews = list(
        InterviewSchedule.objects.filter(
            application__job__company=recruiter.company,
            is_current=True,
            status__in=(
                InterviewSchedule.Status.PENDING,
                InterviewSchedule.Status.CONFIRMED,
            ),
            scheduled_end__gt=now,
        )
        .select_related("application__candidate__user", "application__job")
        .order_by("scheduled_start")[:3]
    )
    upcoming_interview_entries = []
    for schedule in upcoming_interviews:
        try:
            display_timezone = ZoneInfo(schedule.timezone)
        except ZoneInfoNotFoundError:
            display_timezone = timezone.get_default_timezone()
        candidate_name = schedule.application.candidate.user.get_full_name().strip()
        upcoming_interview_entries.append(
            {
                "candidate_name": candidate_name or "Candidate",
                "local_start": timezone.localtime(
                    schedule.scheduled_start,
                    display_timezone,
                ),
                "schedule": schedule,
            }
        )

    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()
    return render(
        request,
        "accounts/recruiter_dashboard.html",
        {
            "active_job_count": active_jobs.count(),
            "active_jobs": active_jobs[:3],
            "awaiting_review_count": company_applications.filter(
                status__in=(
                    JobApplication.Status.APPLIED,
                    JobApplication.Status.SCREENING,
                )
            ).count(),
            "display_name": display_name,
            "initials": initials,
            "interviews_this_week_count": InterviewSchedule.objects.filter(
                application__job__company=recruiter.company,
                is_current=True,
                status__in=(
                    InterviewSchedule.Status.PENDING,
                    InterviewSchedule.Status.CONFIRMED,
                ),
                scheduled_start__gte=week_start,
                scheduled_start__lt=week_end,
            ).count(),
            "new_application_count": company_applications.filter(
                status=JobApplication.Status.APPLIED
            ).count(),
            "recent_application_entries": recent_application_entries,
            "recruiter": recruiter,
            "upcoming_interview_entries": upcoming_interview_entries,
        },
    )


@role_required(User.Role.ADMIN)
def admin_dashboard_view(request):
    if not request.user.is_active:
        raise PermissionDenied

    now = timezone.now()
    display_name = request.user.get_full_name().strip() or "Administrator"
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or "SA"
    shared_context = {
        "display_name": display_name,
        "initials": initials,
    }

    open_job_filter = Q(is_active=True) & Q(jobs__status=JobPosting.Status.OPEN) & (
        Q(jobs__application_deadline__isnull=True)
        | Q(jobs__application_deadline__gte=now)
    )
    if request.GET.get("section") == "management":
        companies = Company.objects.annotate(
            active_job_count=Count(
                "jobs",
                filter=open_job_filter,
                distinct=True,
            ),
            recruiter_count=Count("recruiters", distinct=True),
        ).order_by("name")
        recruiter_entries = []
        recruiter_profiles = RecruiterProfile.objects.select_related(
            "user",
            "company",
        ).order_by("is_verified", "company__name", "user__first_name")
        for recruiter in recruiter_profiles:
            recruiter_name = recruiter.user.get_full_name().strip()
            recruiter_initials = "".join(
                part[0].upper()
                for part in (
                    recruiter.user.first_name,
                    recruiter.user.last_name,
                )
                if part
            )[:2] or "R"
            if not recruiter.user.is_active:
                status_label = "Access disabled"
                status_class = "is-disabled"
            elif recruiter.is_verified:
                status_label = "Verified"
                status_class = "is-verified"
            else:
                status_label = "Pending verification"
                status_class = "is-pending"
            recruiter_entries.append(
                {
                    "display_name": recruiter_name or "Recruiter",
                    "initials": recruiter_initials,
                    "profile": recruiter,
                    "status_class": status_class,
                    "status_label": status_label,
                }
            )

        return render(
            request,
            "accounts/admin_management.html",
            {
                **shared_context,
                "companies": companies,
                "recruiter_entries": recruiter_entries,
            },
        )

    local_now = timezone.localtime(now)
    week_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start -= timedelta(days=week_start.weekday())
    week_end = week_start + timedelta(days=7)

    recent_companies = Company.objects.annotate(
        active_job_count=Count(
            "jobs",
            filter=open_job_filter,
            distinct=True,
        )
    ).order_by("-updated_at", "name")[:4]

    recruiter_access_entries = []
    recruiter_profiles = (
        RecruiterProfile.objects.select_related("user", "company")
        .filter(user__is_active=True)
        .order_by("is_verified", "-updated_at")[:3]
    )
    for recruiter in recruiter_profiles:
        recruiter_name = recruiter.user.get_full_name().strip()
        recruiter_access_entries.append(
            {
                "display_name": recruiter_name or "Recruiter",
                "profile": recruiter,
            }
        )

    safe_activity_labels = {
        "company.created": "Company created",
        "company.updated": "Company updated",
        "recruiter.provisioned": "Recruiter provisioned",
        "recruiter.updated": "Recruiter access updated",
        "job.published": "Job published",
        "interview.confirmed": "Interview confirmed",
    }
    safe_events = AuditEvent.objects.filter(
        event_type__in=safe_activity_labels,
    ).order_by("-event_timestamp")[:4]
    platform_activity_entries = [
        {
            "event": event,
            "label": safe_activity_labels[event.event_type],
        }
        for event in safe_events
    ]

    return render(
        request,
        "accounts/admin_dashboard.html",
        {
            "active_company_count": Company.objects.filter(
                is_active=True
            ).count(),
            **shared_context,
            "interviews_this_week_count": InterviewSchedule.objects.filter(
                is_current=True,
                status__in=(
                    InterviewSchedule.Status.PENDING,
                    InterviewSchedule.Status.CONFIRMED,
                ),
                scheduled_start__gte=week_start,
                scheduled_start__lt=week_end,
            ).count(),
            "platform_activity_entries": platform_activity_entries,
            "published_job_count": JobPosting.objects.filter(
                company__is_active=True,
                status=JobPosting.Status.OPEN,
            )
            .filter(
                Q(application_deadline__isnull=True)
                | Q(application_deadline__gte=now)
            )
            .count(),
            "recent_companies": recent_companies,
            "recruiter_access_entries": recruiter_access_entries,
            "verified_recruiter_count": RecruiterProfile.objects.filter(
                company__is_active=True,
                is_verified=True,
                user__is_active=True,
            ).count(),
        },
    )
