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
    has_effective_general_ai_processing_consent,
    revoke_general_ai_processing_consent,
)
from auditlog.models import AuditEvent, ConsentRecord
from auditlog.services import AuditCommand, record_domain_event
from candidates.forms import CandidateProfileForm, ResumeUploadForm
from candidates.models import CandidateProfile, Resume
from candidates.resume_services import (
    create_pending_resume,
    process_and_activate_resume,
)


def _profile_page_context(*, request, profile, form):
    skills = profile.candidate_skills.select_related("skill")
    active_resume_exists = profile.resumes.filter(is_active=True).exists()
    skill_count = skills.count()
    latest_consent = (
        ConsentRecord.objects.filter(
            candidate=profile,
            consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
            application__isnull=True,
        )
        .order_by("-recorded_at", "-id")
        .first()
    )
    consent_active = has_effective_general_ai_processing_consent(
        candidate=profile,
        policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
    )
    completion_checks = (
        bool(request.user.first_name and request.user.last_name),
        bool(profile.phone_number and profile.city),
        bool(profile.professional_summary),
        skill_count >= 2,
        active_resume_exists,
        consent_active,
    )
    completion_actions = []
    if not completion_checks[0]:
        completion_actions.append("Add your full name")
    if not completion_checks[1]:
        completion_actions.append("Add contact and location details")
    if not completion_checks[2]:
        completion_actions.append("Add a professional summary")
    if not completion_checks[3]:
        completion_actions.append("Add at least two skills")
    if not completion_checks[4]:
        completion_actions.append("Upload your current résumé")
    if not completion_checks[5]:
        completion_actions.append("Review AI processing consent")

    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()

    return {
        "completion_actions": completion_actions[:2],
        "consent_active": consent_active,
        "consent_recorded_at": (
            latest_consent.recorded_at if latest_consent is not None else None
        ),
        "display_name": display_name,
        "form": form,
        "initials": initials,
        "profile": profile,
        "profile_completion": round(
            100 * sum(completion_checks) / len(completion_checks)
        ),
        "skills": skills,
    }


def _resume_page_context(*, request, upload_form):
    profile = get_object_or_404(CandidateProfile, user=request.user)
    resumes = profile.resumes.all()
    active_resume = resumes.filter(is_active=True).first()
    previous_resumes = (
        resumes.exclude(pk=active_resume.pk) if active_resume is not None else resumes
    )
    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()

    return {
        "active_resume": active_resume,
        "active_resume_file_type": (
            "PDF"
            if active_resume is not None
            and active_resume.original_filename.lower().endswith(".pdf")
            else "DOCX"
        ),
        "display_name": display_name,
        "initials": initials,
        "previous_resumes": previous_resumes,
        "upload_form": upload_form,
    }


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
    return render(
        request,
        "candidates/profile_form.html",
        _profile_page_context(
            request=request,
            profile=profile,
            form=form,
        ),
    )


@require_POST
@role_required(User.Role.CANDIDATE)
def general_consent_view(request):
    profile = get_object_or_404(CandidateProfile, user=request.user)
    redirect_route = (
        "candidates:profile_edit"
        if request.POST.get("return_to") == "profile"
        else "accounts:candidate_dashboard"
    )
    action = request.POST.get("action")
    operation = {
        "grant": grant_general_ai_processing_consent,
        "revoke": revoke_general_ai_processing_consent,
    }.get(action)
    if operation is None:
        messages.error(request, "The consent action is not valid.")
        return redirect(redirect_route)
    operation(
        candidate=profile,
        actor=request.user,
        policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    messages.success(request, "Your consent preference was recorded.")
    return redirect(redirect_route)


@role_required(User.Role.CANDIDATE)
def resume_list_view(request):
    return render(
        request,
        "candidates/resume_list.html",
        _resume_page_context(
            request=request,
            upload_form=ResumeUploadForm(),
        ),
    )


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
    return render(
        request,
        "candidates/resume_list.html",
        _resume_page_context(
            request=request,
            upload_form=form,
        ),
    )


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
