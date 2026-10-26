import uuid

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import role_required
from interviews.models import InterviewRescheduleRequest, InterviewSchedule
from interviews.scheduling_services import (
    SchedulingServiceError,
    cancel_interview,
    confirm_interview_invitation,
    create_interview_invitation,
    deliver_interview_invitation,
    expire_interview_invitation,
    reissue_interview_invitation,
    request_interview_reschedule,
    review_reschedule_request,
)
from recruitment.application_services import (
    ApplicationServiceError,
    recruiter_applications,
)
from recruitment.forms import InterviewInvitationForm, InterviewRescheduleForm


def _confirmation_url(request, token):
    return request.build_absolute_uri(
        reverse("interviews:invitation_confirm", args=(token,))
    )


def _recruiter_application(request, application_id):
    try:
        return get_object_or_404(
            recruiter_applications(request.user), pk=application_id
        )
    except ApplicationServiceError as error:
        raise PermissionDenied from error


@role_required(User.Role.RECRUITER)
def invitation_create_view(request, application_id):
    application = _recruiter_application(request, application_id)
    form = InterviewInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            issued = create_interview_invitation(
                application=application,
                actor=request.user,
                scheduled_start=form.cleaned_data["scheduled_start"],
                scheduled_end=form.cleaned_data["scheduled_end"],
                timezone_name=form.cleaned_data["timezone"],
                policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
                idempotency_key=uuid.uuid4(),
            )
            delivered = deliver_interview_invitation(
                issued=issued,
                confirmation_url=_confirmation_url(request, issued.token),
            )
        except SchedulingServiceError as error:
            form.add_error(None, str(error))
        else:
            messages.info(
                request,
                "The invitation was sent."
                if delivered
                else "The schedule was created, but delivery failed safely.",
            )
            return redirect(
                "recruitment:application_detail", application_id=application.pk
            )
    return render(
        request,
        "interviews/invitation_form.html",
        {"form": form, "application": application},
    )


@role_required(User.Role.CANDIDATE)
def invitation_confirm_view(request, token):
    if request.method == "POST":
        try:
            schedule = confirm_interview_invitation(
                token=token,
                actor=request.user,
                policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
                consent_idempotency_key=uuid.uuid4(),
            )
        except SchedulingServiceError:
            return render(
                request,
                "interviews/invitation_result.html",
                {"confirmed": False},
                status=400,
            )
        messages.success(request, "Your interview time is confirmed.")
        return redirect(
            "recruitment:application_detail",
            application_id=schedule.application_id,
        )
    return render(request, "interviews/invitation_confirm.html")


@require_POST
@role_required(User.Role.RECRUITER)
def invitation_resend_view(request, schedule_id):
    schedule = get_object_or_404(InterviewSchedule, pk=schedule_id)
    try:
        issued = reissue_interview_invitation(schedule=schedule, actor=request.user)
        delivered = deliver_interview_invitation(
            issued=issued,
            confirmation_url=_confirmation_url(request, issued.token),
        )
    except SchedulingServiceError:
        delivered = False
    messages.info(
        request,
        "The invitation is available."
        if delivered
        else "The invitation could not be delivered.",
    )
    return redirect(
        "recruitment:application_detail", application_id=schedule.application_id
    )


@role_required(User.Role.CANDIDATE)
def reschedule_request_view(request, schedule_id):
    schedule = get_object_or_404(
        InterviewSchedule.objects.select_related("application__candidate"),
        pk=schedule_id,
        application__candidate__user=request.user,
        is_current=True,
    )
    form = InterviewRescheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            request_interview_reschedule(
                schedule=schedule,
                actor=request.user,
                proposed_start=form.cleaned_data["scheduled_start"],
                proposed_end=form.cleaned_data["scheduled_end"],
                timezone_name=form.cleaned_data["timezone"],
                reason=form.cleaned_data["reason"],
            )
        except SchedulingServiceError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Your reschedule request was submitted.")
            return redirect(
                "recruitment:application_detail",
                application_id=schedule.application_id,
            )
    return render(
        request,
        "interviews/reschedule_form.html",
        {"form": form, "schedule": schedule},
    )


@require_POST
@role_required(User.Role.RECRUITER)
def reschedule_review_view(request, request_id):
    reschedule = get_object_or_404(InterviewRescheduleRequest, pk=request_id)
    application_id = reschedule.schedule.application_id
    approve = request.POST.get("decision") == "approve"
    try:
        reviewed, issued = review_reschedule_request(
            reschedule_request=reschedule,
            actor=request.user,
            approve=approve,
            invitation_idempotency_key=uuid.uuid4() if approve else None,
        )
        if issued is not None:
            deliver_interview_invitation(
                issued=issued,
                confirmation_url=_confirmation_url(request, issued.token),
            )
    except SchedulingServiceError:
        messages.error(request, "The reschedule request could not be reviewed.")
    else:
        messages.success(request, "The reschedule request was reviewed.")
    return redirect(
        "recruitment:application_detail",
        application_id=application_id,
    )


@require_POST
@role_required(User.Role.RECRUITER)
def schedule_cancel_view(request, schedule_id):
    schedule = get_object_or_404(InterviewSchedule, pk=schedule_id)
    try:
        cancel_interview(
            schedule=schedule,
            actor=request.user,
            reason_code=request.POST.get("reason_code", "recruiter_cancelled"),
        )
    except SchedulingServiceError:
        messages.error(request, "The interview could not be cancelled.")
    return redirect(
        "recruitment:application_detail", application_id=schedule.application_id
    )


@require_POST
@role_required(User.Role.RECRUITER)
def schedule_expire_view(request, schedule_id):
    schedule = get_object_or_404(InterviewSchedule, pk=schedule_id)
    try:
        expire_interview_invitation(schedule=schedule, actor=request.user)
    except SchedulingServiceError:
        messages.error(request, "The invitation is not yet eligible for expiration.")
    return redirect(
        "recruitment:application_detail", application_id=schedule.application_id
    )
