import re
import uuid

from ai_system.agents.gateway import AgentRequest, DetachedAgentGateway
from ai_system.agents.profile_extraction import ProfileExtractionError, extract_profile
from ai_system.framework.agents import AgentName, BoundedAgentRunner
from ai_system.rag.service import (
    LocalMiniLMEmbedder,
    RagDocument,
    RetrievalPrincipal,
    SharedRagService,
)
from ai_system.runtime.gemini import GeminiRuntime
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
from candidates.models import CandidateProfile, CandidateSkill, Resume, Skill
from candidates.resume_services import (
    create_pending_resume,
    process_and_activate_resume,
)


def _profile_page_context(*, request, profile, form):
    skills = profile.candidate_skills.select_related("skill")
    raw_skill_names = form["skills"].value() or ""
    skill_names = [name.strip() for name in raw_skill_names.replace("\n", ",").split(",") if name.strip()]
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
        completion_actions.append("Upload your current resume")
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
        "skill_names": list(dict.fromkeys(skill_names)),
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
                submitted_names = {name.casefold(): name for name in form.cleaned_data["skills"]}
                existing_links = list(CandidateSkill.objects.filter(candidate=updated).select_related("skill"))
                for link in existing_links:
                    if link.skill.name.casefold() not in submitted_names:
                        link.delete()
                for name in submitted_names.values():
                    skill = Skill.objects.filter(name__iexact=name).first()
                    if skill is None:
                        skill = Skill.objects.create(name=name)
                    CandidateSkill.objects.get_or_create(
                        candidate=updated,
                        skill=skill,
                        defaults={"source": CandidateSkill.Source.SELF_REPORTED},
                    )
                # Retain the legacy column but never accept a user-selected timezone.
                updated.timezone = settings.TIME_ZONE
                updated.save(update_fields=("timezone", "updated_at"))
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
            request.session.pop("profile_extraction_preview", None)
            return redirect("candidates:profile_edit")
    else:
        form = CandidateProfileForm(instance=profile)
        form.initial["skills"] = ", ".join(
            profile.candidate_skills.select_related("skill").values_list(
                "skill__name", flat=True
            )
        )
        extraction = request.session.get("profile_extraction_preview", {}).get("data", {})
        for field in ("phone_number", "city", "professional_summary", "years_of_experience"):
            extracted = extraction.get(field)
            existing = getattr(profile, field)
            if extracted and not existing:
                form.initial[field] = extracted
        if extraction.get("skills") and not profile.candidate_skills.exists():
            form.initial["skills"] = ", ".join(extraction["skills"])
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
    legacy_action = request.POST.get("consent_action")
    if action and legacy_action and action != legacy_action:
        action = "__conflicting_actions__"
    else:
        action = action or legacy_action
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


@require_POST
@role_required(User.Role.CANDIDATE)
def resume_analyze_view(request):
    profile = get_object_or_404(CandidateProfile, user=request.user)
    if not has_effective_general_ai_processing_consent(candidate=profile, policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION):
        messages.error(request, "Grant AI processing consent before using profile extraction.")
        return redirect("candidates:resume_list")
    resume = get_object_or_404(Resume, pk=request.POST.get("resume_id"), candidate=profile, is_active=True, processing_status=Resume.ProcessingStatus.COMPLETED)
    runtime = GeminiRuntime()
    try:
        preview = extract_profile(runtime=runtime, resume_text=resume.extracted_text).as_dict()
        request.session["profile_extraction_preview"] = {"resume_id": str(resume.pk), "data": preview}
        messages.success(request, "AI extraction completed. Review the preview before applying it.")
    except ProfileExtractionError as error:
        messages.error(request, f"AI profile extraction was not completed ({error}). Please try again with a text-based PDF or DOCX resume.")
    finally:
        runtime.stop()
    return redirect("candidates:profile_edit")


@require_POST
@role_required(User.Role.CANDIDATE)
def resume_apply_profile_view(request):
    preview = request.session.get("profile_extraction_preview")
    profile = get_object_or_404(CandidateProfile, user=request.user)
    if not preview or request.POST.get("confirm") != "yes":
        messages.error(request, "Confirm the reviewed extraction before applying it.")
        return redirect("candidates:profile_edit")
    data = preview.get("data", {})
    get_object_or_404(Resume, pk=preview.get("resume_id"), candidate=profile, is_active=True, processing_status=Resume.ProcessingStatus.COMPLETED)
    if not has_effective_general_ai_processing_consent(candidate=profile, policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION):
        messages.error(request, "Current AI processing consent is required.")
        return redirect("candidates:profile_edit")
    with transaction.atomic():
        user = request.user
        if not user.first_name and data.get("full_name"):
            parts = data["full_name"].split()
            user.first_name, user.last_name = parts[0], " ".join(parts[1:])
            user.save(update_fields=("first_name", "last_name", "updated_at"))
        for field in ("phone_number", "city", "professional_summary", "years_of_experience"):
            if not getattr(profile, field) and data.get(field):
                setattr(profile, field, data[field])
        profile.save()
        for name in data.get("skills", []):
            skill, _ = Skill.objects.get_or_create(name=name[:100])
            CandidateSkill.objects.get_or_create(candidate=profile, skill=skill, defaults={"source": CandidateSkill.Source.AGENT, "confidence_score": 0.8})
        record_domain_event(AuditCommand(category=AuditEvent.Category.DATA_CHANGE, event_type="profile.updated", outcome=AuditEvent.Outcome.SUCCESS, severity=AuditEvent.Severity.INFO, resource_type="candidates.CandidateProfile", resource_id=profile.pk, actor=request.user, metadata={"changed_fields": ["ai_resume_preview_applied"]}))
    request.session.pop("profile_extraction_preview", None)
    messages.success(request, "Reviewed resume details were applied to your profile.")
    return redirect("candidates:profile_edit")


@role_required(User.Role.CANDIDATE)
def faq_view(request):
    if request.GET.get("new"):
        request.session.pop("faq_history", None)
        request.session.pop("faq_topic_query", None)
    if request.session.get("faq_history_version") != 2:
        request.session.pop("faq_history", None)
        request.session.pop("faq_topic_query", None)
        request.session["faq_history_version"] = 2
    question = request.POST.get("question", "").strip() if request.method == "POST" else ""
    result = None
    history = request.session.get("faq_history", [])
    if request.method == "POST":
        profile = get_object_or_404(CandidateProfile, user=request.user)
        if not question:
            result = {"status": "error", "message": "Enter a recruitment-process question."}
        elif len(question) > 1200:
            result = {"status": "error", "message": "That question is too long for the local model. Please keep it under 1,200 characters."}
        elif not has_effective_general_ai_processing_consent(candidate=profile, policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION):
            result = {"status": "error", "message": "Grant AI processing consent in My Profile first."}
        else:
            rag = SharedRagService(LocalMiniLMEmbedder())
            rag.reindex([
                RagDocument("public-login", "public_policy", "3", "Candidates log in from the HireFlow AI Login page by entering their registered email address and password, then submitting the login form. A registered candidate who knows their credentials does not need password recovery."),
                RagDocument("public-password-recovery", "public_policy", "5", "A candidate who forgot a password should use the password recovery link on the HireFlow AI Login page. This is public navigation guidance; never ask for an email, password, or identifier. Recovery is not required for normal login."),
                RagDocument("public-profile-resume", "public_policy", "3", "Candidates manage their profile from Candidate Portal > My Profile and upload PDF or DOCX resumes from My Resume. Auto-Fill Profile with AI requires active AI-processing consent and fills resume-supported editable fields for review before Save Changes."),
                RagDocument("public-jobs-applications", "public_policy", "3", "Browse Jobs lists currently eligible published jobs; open a job and use Apply when available. Submitted application status is visible in Candidate Portal > My Applications."),
                RagDocument("public-interviews", "public_policy", "4", "Recruiters schedule interviews after candidate AI consent. Scheduled interviews appear in the Candidate Portal without an email or separate confirmation step. The fixed date and time use Asia/Karachi and cannot be changed. HireFlow interviews use approved questions and authorized human review."),
            ])
            runtime = GeminiRuntime()
            try:
                compact_history = [
                    {"role": item.get("role"), "content": item.get("content", "")[:600]}
                    for item in history[-6:]
                    if isinstance(item, dict)
                    and item.get("role") in {"user", "assistant"}
                    and isinstance(item.get("content"), str)
                    and not (item.get("role") == "assistant" and item.get("action") == "clarify")
                ]
                retrieval_query = question
                principal = RetrievalPrincipal(user_id=str(request.user.pk), role="candidate", candidate_id=str(profile.pk), ai_processing_consented=True)
                conversation_signal = "dissatisfaction" if re.search(r"(?i)\b(understand me|repeating|didn.t answer|not answering|what are you saying)\b", question) else "ordinary"
                contextual_followup = conversation_signal == "dissatisfaction" or bool(
                    re.search(r"(?i)\b(that|it|there|this option|that option|again)\b", question)
                )
                current_sources = rag.retrieve(query=question, principal=principal, limit=1)
                if contextual_followup or (current_sources and current_sources[0].score < 0.24):
                    retrieval_query = request.session.get("faq_topic_query") or question
                gateway = DetachedAgentGateway(runner=BoundedAgentRunner(runtime, timeout_seconds=25), rag=rag)
                context = {"question": question, "authenticated_role": request.user.role, "conversation_history": compact_history, "conversation_signal": conversation_signal}
                decision = gateway.propose(AgentRequest(agent_name=AgentName.FAQ, principal=principal, context=context, retrieval_query=retrieval_query, retrieval_limit=1))
                if decision.proposal.action == "clarify" and decision.source_ids:
                    context["answer_required"] = True
                    decision = gateway.propose(AgentRequest(agent_name=AgentName.FAQ, principal=principal, context=context, retrieval_query=retrieval_query, allowed_actions=frozenset({"answer_from_sources", "recommend_human_review"}), retrieval_limit=1))
                elif conversation_signal == "dissatisfaction" and decision.source_ids and not re.search(r"(?i)\b(sorry|apolog|understand|clearer|clarify)\b", decision.proposal.message):
                    context["answer_required"] = True
                    context["acknowledgement_required"] = True
                    decision = gateway.propose(AgentRequest(agent_name=AgentName.FAQ, principal=principal, context=context, retrieval_query=retrieval_query, allowed_actions=frozenset({"answer_from_sources"}), retrieval_limit=1))
                result = {"status": "completed" if decision.proposal.fallback_code is None else "fallback", "message": decision.proposal.message, "action": decision.proposal.action, "sources": decision.source_ids, "llm": decision.proposal.fallback_code is None}
                if decision.proposal.fallback_code is None:
                    history = (history + [{"role": "user", "content": question}, {"role": "assistant", "content": decision.proposal.message, "action": decision.proposal.action}])[-8:]
                    request.session["faq_history"] = history
                    if decision.source_ids and current_sources and current_sources[0].score >= 0.24 and not contextual_followup:
                        request.session["faq_topic_query"] = question[:600]
            except Exception:
                result = {"status": "unavailable", "message": "The AI service is unavailable. Please try again shortly."}
            finally:
                runtime.stop()
    return render(request, "candidates/faq.html", {"question": question, "result": result})


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
