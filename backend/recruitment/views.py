import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import role_required
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    has_effective_application_ai_interview_consent,
    has_effective_general_ai_processing_consent,
    revoke_application_ai_interview_consent,
)
from auditlog.models import AuditEvent
from candidates.models import CandidateProfile, Resume
from interviews.models import InterviewSchedule
from recruitment.application_services import (
    ApplicationServiceError,
    change_application_interview_consent,
    create_application,
    recruiter_applications,
    withdraw_application,
)
from recruitment.forms import (
    InterviewQuestionForm,
    JobApplicationForm,
    JobFAQForm,
    JobPostingForm,
    JobSkillRequirementForm,
)
from recruitment.job_services import (
    JobServiceError,
    add_interview_question,
    add_job_faq,
    add_job_skill,
    create_job,
    recruiter_jobs,
    update_job,
)
from recruitment.models import JobApplication, JobPosting
from recruitment.transition_services import WorkflowTransitionError, transition_job


@role_required(User.Role.RECRUITER, User.Role.CANDIDATE)
def job_list_view(request):
    if request.user.role == User.Role.CANDIDATE:
        jobs = (
            JobPosting.objects.filter(
                status=JobPosting.Status.OPEN,
                company__is_active=True,
            )
            .filter(
                Q(application_deadline__isnull=True)
                | Q(application_deadline__gt=timezone.now())
            )
            .select_related("company")
            .prefetch_related("skill_requirements__skill")
        )
        display_name = request.user.get_full_name().strip() or request.user.email
        initials = "".join(
            part[0].upper()
            for part in (request.user.first_name, request.user.last_name)
            if part
        )[:2] or request.user.email[0].upper()
        context = {
            "display_name": display_name,
            "initials": initials,
            "jobs": jobs,
        }
        template_name = "recruitment/job_list.html"
    else:
        try:
            jobs = recruiter_jobs(request.user).annotate(
                applicant_count=Count("applications")
            )
        except JobServiceError as error:
            raise PermissionDenied from error
        recruiter = request.user.recruiter_profile
        display_name = request.user.get_full_name().strip() or request.user.email
        initials = "".join(
            part[0].upper()
            for part in (request.user.first_name, request.user.last_name)
            if part
        )[:2] or request.user.email[0].upper()
        context = {
            "closed_job_count": jobs.filter(
                status=JobPosting.Status.CLOSED
            ).count(),
            "display_name": display_name,
            "draft_job_count": jobs.filter(
                status=JobPosting.Status.DRAFT
            ).count(),
            "initials": initials,
            "jobs": jobs,
            "published_job_count": jobs.filter(
                status=JobPosting.Status.OPEN
            ).count(),
            "recruiter": recruiter,
        }
        template_name = "recruitment/recruiter_job_list.html"
    return render(request, template_name, context)


@role_required(User.Role.RECRUITER)
def job_create_view(request):
    if request.method == "POST":
        form = JobPostingForm(request.POST)
        if form.is_valid():
            try:
                job = create_job(actor=request.user, values=form.cleaned_data)
            except JobServiceError as error:
                raise PermissionDenied from error
            messages.success(request, "The draft job was created.")
            return redirect("recruitment:job_edit", job_id=job.pk)
    else:
        form = JobPostingForm()
    return render(request, "recruitment/job_form.html", {"form": form})


def _recruiter_job_or_404(request, job_id):
    try:
        return get_object_or_404(recruiter_jobs(request.user), pk=job_id)
    except JobServiceError as error:
        raise PermissionDenied from error


@role_required(User.Role.RECRUITER)
def job_edit_view(request, job_id):
    job = _recruiter_job_or_404(request, job_id)
    if request.method == "POST":
        form = JobPostingForm(request.POST, instance=job)
        if form.is_valid():
            values = {field: form.cleaned_data[field] for field in form.fields}
            try:
                job = update_job(
                    actor=request.user,
                    job=job,
                    values=values,
                    changed_fields=form.changed_data,
                )
            except JobServiceError as error:
                raise PermissionDenied from error
            messages.success(request, "The job was updated.")
            return redirect("recruitment:job_edit", job_id=job.pk)
    else:
        form = JobPostingForm(instance=job)
    return render(
        request,
        "recruitment/job_form.html",
        {"form": form, "job": job},
    )


@role_required(User.Role.RECRUITER, User.Role.CANDIDATE)
def job_detail_view(request, job_id):
    if request.user.role == User.Role.CANDIDATE:
        job = get_object_or_404(
            JobPosting.objects.filter(
                Q(application_deadline__isnull=True)
                | Q(application_deadline__gt=timezone.now()),
                status=JobPosting.Status.OPEN,
                company__is_active=True,
            )
            .select_related("company")
            .prefetch_related("skill_requirements__skill"),
            pk=job_id,
        )
        display_name = request.user.get_full_name().strip() or request.user.email
        initials = "".join(
            part[0].upper()
            for part in (request.user.first_name, request.user.last_name)
            if part
        )[:2] or request.user.email[0].upper()
        context = {
            "display_name": display_name,
            "initials": initials,
            "job": job,
        }
        template_name = "recruitment/job_detail.html"
    else:
        job = _recruiter_job_or_404(request, job_id)
        context = {"job": job}
        template_name = "recruitment/recruiter_job_detail.html"
    return render(request, template_name, context)


@require_POST
@role_required(User.Role.RECRUITER)
def job_state_view(request, job_id):
    job = _recruiter_job_or_404(request, job_id)
    try:
        transition_job(
            job=job,
            target_status=request.POST.get("status"),
            actor=request.user,
        )
    except WorkflowTransitionError:
        messages.error(request, "The requested job state change is not allowed.")
    return redirect("recruitment:job_edit", job_id=job.pk)


@role_required(User.Role.RECRUITER)
def job_skill_view(request, job_id):
    job = _recruiter_job_or_404(request, job_id)
    form = JobSkillRequirementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        add_job_skill(actor=request.user, job=job, values=form.cleaned_data.copy())
        return redirect("recruitment:job_edit", job_id=job.pk)
    return render(request, "recruitment/job_child_form.html", {"form": form, "job": job, "kind": "skill"})


@role_required(User.Role.RECRUITER)
def job_question_view(request, job_id):
    job = _recruiter_job_or_404(request, job_id)
    form = InterviewQuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        add_interview_question(actor=request.user, job=job, values=form.cleaned_data)
        return redirect("recruitment:job_edit", job_id=job.pk)
    return render(request, "recruitment/job_child_form.html", {"form": form, "job": job, "kind": "question"})


@role_required(User.Role.RECRUITER)
def job_faq_view(request, job_id):
    job = _recruiter_job_or_404(request, job_id)
    form = JobFAQForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        add_job_faq(actor=request.user, job=job, values=form.cleaned_data)
        return redirect("recruitment:job_edit", job_id=job.pk)
    return render(request, "recruitment/job_child_form.html", {"form": form, "job": job, "kind": "FAQ"})


@role_required(User.Role.CANDIDATE)
def application_create_view(request, job_id):
    candidate = get_object_or_404(CandidateProfile, user=request.user)
    job = get_object_or_404(
        JobPosting.objects.filter(
            Q(application_deadline__isnull=True)
            | Q(application_deadline__gt=timezone.now()),
            status=JobPosting.Status.OPEN,
            company__is_active=True,
        ).select_related("company"),
        pk=job_id,
    )
    form = JobApplicationForm(request.POST or None, candidate=candidate)
    eligible_resume = form.fields["resume"].queryset.first()
    if request.method == "GET" and eligible_resume is not None:
        form.fields["resume"].initial = eligible_resume
    if request.method == "POST" and form.is_valid():
        try:
            application = create_application(
                actor=request.user,
                job=job,
                resume=form.cleaned_data["resume"],
                cover_note=form.cleaned_data["cover_note"],
                grant_interview_consent=form.cleaned_data["consent_to_ai_interview"],
                policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
                consent_idempotency_key=uuid.uuid4(),
            )
        except ApplicationServiceError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Your application was submitted.")
            return redirect("recruitment:application_detail", application_id=application.pk)
    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()
    return render(
        request,
        "recruitment/application_form.html",
        {
            "display_name": display_name,
            "eligible_resume": eligible_resume,
            "form": form,
            "initials": initials,
            "job": job,
        },
    )


def _recruiter_application_page_context(request, applications):
    recruiter = request.user.recruiter_profile
    application_entries = []
    for application in applications:
        candidate_user = application.candidate.user
        candidate_name = candidate_user.get_full_name().strip()
        candidate_initials = "".join(
            part[0].upper()
            for part in (candidate_user.first_name, candidate_user.last_name)
            if part
        )[:2] or "C"
        application_entries.append(
            {
                "application": application,
                "candidate_initials": candidate_initials,
                "candidate_name": candidate_name or "Candidate",
                "status_class": application.status,
            }
        )
    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()
    return {
        "application_entries": application_entries,
        "display_name": display_name,
        "initials": initials,
        "recruiter": recruiter,
    }


@role_required(User.Role.CANDIDATE, User.Role.RECRUITER)
def application_list_view(request):
    if request.user.role == User.Role.CANDIDATE:
        candidate = get_object_or_404(CandidateProfile, user=request.user)
        now = timezone.now()
        current_schedules = InterviewSchedule.objects.filter(
            is_current=True
        ).prefetch_related("call_sessions")
        applications = list(
            JobApplication.objects.filter(candidate=candidate)
            .select_related("job__company", "resume")
            .prefetch_related(
                Prefetch(
                    "interview_schedules",
                    queryset=current_schedules,
                    to_attr="current_schedules",
                )
            )
        )
        application_entries = []
        upcoming_schedules = []
        for application in applications:
            schedule = (
                application.current_schedules[0]
                if application.current_schedules
                else None
            )
            is_confirmed = (
                schedule is not None
                and schedule.status == InterviewSchedule.Status.CONFIRMED
            )
            application_entries.append(
                {
                    "application": application,
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
            if is_confirmed and schedule.scheduled_end > now:
                upcoming_schedules.append(schedule)

        upcoming_schedule = min(
            upcoming_schedules,
            key=lambda schedule: schedule.scheduled_start,
            default=None,
        )
        upcoming_session = None
        upcoming_local_start = None
        readiness_checks = ()
        if upcoming_schedule is not None:
            sessions = list(upcoming_schedule.call_sessions.all())
            upcoming_session = sessions[0] if sessions else None
            try:
                display_timezone = ZoneInfo(upcoming_schedule.timezone)
            except ZoneInfoNotFoundError:
                display_timezone = timezone.get_default_timezone()
            upcoming_local_start = timezone.localtime(
                upcoming_schedule.scheduled_start,
                display_timezone,
            )
            policy_version = settings.CURRENT_AI_CONSENT_POLICY_VERSION
            general_consent = has_effective_general_ai_processing_consent(
                candidate=candidate,
                policy_version=policy_version,
            )
            interview_consent = has_effective_application_ai_interview_consent(
                application=upcoming_schedule.application,
                policy_version=policy_version,
            )
            active_resume_ready = candidate.resumes.filter(
                is_active=True,
                processing_status=Resume.ProcessingStatus.COMPLETED,
            ).exists()
            readiness_checks = (
                ("Email verified", request.user.email_verified),
                ("Resume ready", active_resume_ready),
                (
                    "Interview consent active",
                    general_consent and interview_consent,
                ),
                ("Interview confirmed", True),
            )

        active_statuses = {
            JobApplication.Status.APPLIED,
            JobApplication.Status.SCREENING,
            JobApplication.Status.INVITED,
            JobApplication.Status.INTERVIEWED,
            JobApplication.Status.SHORTLISTED,
        }
        review_statuses = {
            JobApplication.Status.SCREENING,
            JobApplication.Status.INVITED,
            JobApplication.Status.INTERVIEWED,
            JobApplication.Status.SHORTLISTED,
        }
        display_name = request.user.get_full_name().strip() or request.user.email
        initials = "".join(
            part[0].upper()
            for part in (request.user.first_name, request.user.last_name)
            if part
        )[:2] or request.user.email[0].upper()
        context = {
            "active_application_count": sum(
                application.status in active_statuses for application in applications
            ),
            "application_entries": application_entries,
            "display_name": display_name,
            "initials": initials,
            "readiness_checks": readiness_checks,
            "under_review_count": sum(
                application.status in review_statuses for application in applications
            ),
            "upcoming_interview_count": len(upcoming_schedules),
            "upcoming_local_start": upcoming_local_start,
            "upcoming_schedule": upcoming_schedule,
            "upcoming_session": upcoming_session,
        }
        template_name = "recruitment/application_list.html"
    else:
        try:
            applications = list(recruiter_applications(request.user))
        except ApplicationServiceError as error:
            raise PermissionDenied from error
        context = _recruiter_application_page_context(request, applications)
        template_name = "recruitment/recruiter_application_list.html"
    return render(request, template_name, context)


def _accessible_application(request, application_id):
    if request.user.role == User.Role.CANDIDATE:
        return get_object_or_404(
            JobApplication.objects.select_related("job", "candidate__user", "resume"),
            pk=application_id,
            candidate__user=request.user,
        )
    try:
        return get_object_or_404(recruiter_applications(request.user), pk=application_id)
    except ApplicationServiceError as error:
        raise PermissionDenied from error


@role_required(User.Role.CANDIDATE, User.Role.RECRUITER)
def application_detail_view(request, application_id):
    application = _accessible_application(request, application_id)
    schedule = application.interview_schedules.filter(is_current=True).first()
    pending_reschedules = (
        schedule.reschedule_requests.filter(status="pending") if schedule else ()
    )
    history = AuditEvent.objects.filter(
        resource_type="recruitment.JobApplication",
        resource_id=str(application.pk),
        event_type__in=(
            "application.created",
            "application.status_changed",
            "application.withdrawn",
        ),
    ).order_by("event_timestamp", "id")
    if request.user.role == User.Role.RECRUITER:
        try:
            applications = list(recruiter_applications(request.user))
        except ApplicationServiceError as error:
            raise PermissionDenied from error
        candidate_user = application.candidate.user
        candidate_name = candidate_user.get_full_name().strip() or "Candidate"
        candidate_initials = "".join(
            part[0].upper()
            for part in (candidate_user.first_name, candidate_user.last_name)
            if part
        )[:2] or "C"
        general_consent_active = has_effective_general_ai_processing_consent(
            candidate=application.candidate,
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
        interview_consent_active = has_effective_application_ai_interview_consent(
            application=application,
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
        context = _recruiter_application_page_context(request, applications)
        context.update(
            {
                "application": application,
                "candidate_initials": candidate_initials,
                "candidate_name": candidate_name,
                "candidate_skills": application.candidate.candidate_skills.select_related(
                    "skill"
                ),
                "general_consent_active": general_consent_active,
                "history": history,
                "interview_consent_active": interview_consent_active,
                "pending_reschedules": pending_reschedules,
                "resume_ready": bool(
                    application.resume
                    and application.resume.processing_status
                    == Resume.ProcessingStatus.COMPLETED
                ),
                "schedule": schedule,
                "selected_application": application,
                "session": schedule.call_sessions.first() if schedule else None,
            }
        )
        return render(
            request,
            "recruitment/recruiter_application_list.html",
            context,
        )
    return render(
        request,
        "recruitment/application_detail.html",
        {
            "application": application,
            "history": history,
            "schedule": schedule,
            "pending_reschedules": pending_reschedules,
        },
    )


@require_POST
@role_required(User.Role.CANDIDATE)
def application_consent_view(request, application_id):
    application = _accessible_application(request, application_id)
    operation = {
        "grant": grant_application_ai_interview_consent,
        "revoke": revoke_application_ai_interview_consent,
    }.get(request.POST.get("action"))
    if operation is None:
        messages.error(request, "The consent action is not valid.")
    else:
        change_application_interview_consent(
            application=application,
            actor=request.user,
            operation=operation,
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
        messages.success(request, "Your interview consent preference was recorded.")
    return redirect("recruitment:application_detail", application_id=application.pk)


@require_POST
@role_required(User.Role.CANDIDATE)
def application_withdraw_view(request, application_id):
    application = _accessible_application(request, application_id)
    try:
        withdraw_application(application=application, actor=request.user)
    except ApplicationServiceError:
        messages.error(request, "The application cannot be withdrawn.")
    else:
        messages.success(request, "Your application was withdrawn.")
    return redirect("recruitment:application_detail", application_id=application.pk)
