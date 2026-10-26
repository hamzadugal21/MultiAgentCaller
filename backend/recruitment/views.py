from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import role_required
from recruitment.forms import (
    InterviewQuestionForm,
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
from recruitment.models import JobPosting
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
