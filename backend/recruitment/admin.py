from django import forms
from django.contrib import admin

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from recruitment.models import (
    Company,
    InterviewQuestion,
    JobFAQ,
    JobPosting,
    JobSkillRequirement,
    RecruiterProfile,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active", "industry")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.ADMINISTRATION,
                event_type="company.updated" if change else "company.created",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.Company",
                resource_id=obj.pk,
                actor=request.user,
                metadata={"changed_fields": sorted(form.changed_data)} if change else {},
            )
        )


class RecruiterProfileAdminForm(forms.ModelForm):
    class Meta:
        model = RecruiterProfile
        fields = "__all__"

    def clean_user(self):
        user = self.cleaned_data["user"]
        if user.role != User.Role.RECRUITER:
            raise forms.ValidationError("Select a user with the recruiter role.")
        return user


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    form = RecruiterProfileAdminForm
    list_display = (
        "user",
        "company",
        "is_verified",
        "can_manage_jobs",
        "can_review_candidates",
    )
    list_filter = ("company", "is_verified", "can_manage_jobs", "can_review_candidates")
    search_fields = ("user__email", "company__name")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        capabilities = []
        if obj.can_manage_jobs:
            capabilities.append("manage_jobs")
        if obj.can_review_candidates:
            capabilities.append("review_candidates")
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.ADMINISTRATION,
                event_type="recruiter.updated" if change else "recruiter.provisioned",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.RecruiterProfile",
                resource_id=obj.pk,
                actor=request.user,
                metadata=(
                    {"changed_fields": sorted(form.changed_data)}
                    if change
                    else {
                        "company_id": obj.company_id,
                        "capabilities": capabilities,
                        "is_verified": obj.is_verified,
                    }
                ),
            )
        )


admin.site.register(JobPosting)
admin.site.register(JobSkillRequirement)
admin.site.register(InterviewQuestion)
admin.site.register(JobFAQ)
