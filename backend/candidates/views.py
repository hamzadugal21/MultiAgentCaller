import uuid

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import role_required
from auditlog.consent_services import (
    grant_general_ai_processing_consent,
    revoke_general_ai_processing_consent,
)
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from candidates.forms import CandidateProfileForm, ResumeUploadForm
from candidates.models import CandidateProfile, Resume
from candidates.resume_services import (
    create_pending_resume,
    process_and_activate_resume,
)


@role_required(User.Role.CANDIDATE)
def profile_edit_view(request):
    profile = get_object_or_404(CandidateProfile, user=request.user)
    if request.method == "POST":
        form = CandidateProfileForm(request.POST, instance=profile)
        if form.is_valid():
            with transaction.atomic():
                updated = form.save()
                record_domain_event(
                    AuditCommand(
                        category=AuditEvent.Category.DATA_CHANGE,
                        event_type="profile.updated",
                        outcome=AuditEvent.Outcome.SUCCESS,
                        severity=AuditEvent.Severity.INFO,
                        resource_type="candidates.CandidateProfile",
                        resource_id=updated.pk,
                        actor=request.user,
                        metadata={"changed_fields": sorted(form.changed_data)},
                    )
                )
            messages.success(request, "Your profile was updated.")
            return redirect("candidates:profile_edit")
    else:
        form = CandidateProfileForm(instance=profile)
    return render(request, "candidates/profile_form.html", {"form": form})


@require_POST
@role_required(User.Role.CANDIDATE)
def general_consent_view(request):
    profile = get_object_or_404(CandidateProfile, user=request.user)
    action = request.POST.get("action")
    operation = {
        "grant": grant_general_ai_processing_consent,
        "revoke": revoke_general_ai_processing_consent,
    }.get(action)
    if operation is None:
        messages.error(request, "The consent action is not valid.")
        return redirect("accounts:candidate_dashboard")
    operation(
        candidate=profile,
        actor=request.user,
        policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    messages.success(request, "Your consent preference was recorded.")
    return redirect("accounts:candidate_dashboard")


@role_required(User.Role.CANDIDATE)
def resume_list_view(request):
    resumes = Resume.objects.filter(candidate__user=request.user)
    return render(request, "candidates/resume_list.html", {"resumes": resumes})


@role_required(User.Role.CANDIDATE)
def resume_upload_view(request):
    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            profile = get_object_or_404(CandidateProfile, user=request.user)
            resume = create_pending_resume(
                candidate=profile,
                actor=request.user,
                uploaded_file=form.cleaned_data["file"],
            )
            processed = process_and_activate_resume(resume=resume, actor=request.user)
            if processed.processing_status == Resume.ProcessingStatus.COMPLETED:
                messages.success(request, "Your resume was processed successfully.")
            else:
                messages.error(
                    request,
                    "The resume could not be processed; your previous resume is unchanged.",
                )
            return redirect("candidates:resume_list")
    else:
        form = ResumeUploadForm()
    return render(request, "candidates/resume_upload.html", {"form": form})


@role_required(User.Role.CANDIDATE)
def resume_download_view(request, resume_id):
    resume = get_object_or_404(
        Resume,
        pk=resume_id,
        candidate__user=request.user,
    )
    record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.DATA_ACCESS,
            event_type="resume.downloaded",
            outcome=AuditEvent.Outcome.SUCCESS,
            severity=AuditEvent.Severity.INFO,
            resource_type="candidates.Resume",
            resource_id=resume.pk,
            actor=request.user,
        )
    )
    return FileResponse(
        resume.file.open("rb"),
        as_attachment=True,
        filename=resume.original_filename,
    )
