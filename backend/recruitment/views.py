import uuid

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import role_required
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    revoke_application_ai_interview_consent,
)
from auditlog.models import AuditEvent
from candidates.models import CandidateProfile
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
        jobs = JobPosting.objects.filter(
            status=JobPosting.Status.OPEN,
            company__is_active=True,
        ).filter(Q(application_deadline__isnull=True) | Q(application_deadline__gt=timezone.now()))
    else:
        try:
            jobs = recruiter_jobs(request.user)
        except JobServiceError as error:
            raise PermissionDenied from error
    return render(request, "recruitment/job_list.html", {"jobs": jobs})


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
            ),
            pk=job_id,
        )
    else:
        job = _recruiter_job_or_404(request, job_id)
    return render(request, "recruitment/job_detail.html", {"job": job})


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
    job = get_object_or_404(JobPosting, pk=job_id)
    form = JobApplicationForm(request.POST or None, candidate=candidate)
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
    return render(request, "recruitment/application_form.html", {"form": form, "job": job})


@role_required(User.Role.CANDIDATE, User.Role.RECRUITER)
def application_list_view(request):
    if request.user.role == User.Role.CANDIDATE:
        applications = JobApplication.objects.filter(candidate__user=request.user).select_related("job")
    else:
        try:
            applications = recruiter_applications(request.user)
        except ApplicationServiceError as error:
            raise PermissionDenied from error
    return render(request, "recruitment/application_list.html", {"applications": applications})


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
    history = AuditEvent.objects.filter(
        resource_type="recruitment.JobApplication",
        resource_id=str(application.pk),
        event_type__in=(
            "application.created",
            "application.status_changed",
            "application.withdrawn",
        ),
    ).order_by("event_timestamp", "id")
    return render(
        request,
        "recruitment/application_detail.html",
        {"application": application, "history": history},
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
