from django.contrib import admin

from interviews.models import (
    CandidateEvaluation,
    CriterionScore,
    EvaluationCriterion,
    EvaluationRubric,
    InterviewRescheduleRequest,
    InterviewSchedule,
)


class EvaluationCriterionInline(admin.TabularInline):
    model = EvaluationCriterion
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.evaluations.exists():
            return (
                "name",
                "description",
                "order",
                "weight",
                "scoring_guidance",
                "is_required",
            )
        return ()

    def has_add_permission(self, request, obj=None):
        return not (obj and obj.evaluations.exists())

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.evaluations.exists())


@admin.register(EvaluationRubric)
class EvaluationRubricAdmin(admin.ModelAdmin):
    list_display = ("name", "job", "version", "passing_score", "is_active")
    list_filter = ("is_active", "job__company")
    search_fields = ("name", "job__title", "job__reference_code")
    inlines = (EvaluationCriterionInline,)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.evaluations.exists():
            return ("job", "name", "version", "description", "passing_score")
        return ()

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.evaluations.exists())


class CriterionScoreInline(admin.TabularInline):
    model = CriterionScore
    extra = 0
    can_delete = False
    readonly_fields = (
        "criterion",
        "score",
        "confidence",
        "evidence",
        "explanation",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CandidateEvaluation)
class CandidateEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "status",
        "overall_score",
        "recommendation",
        "review_outcome",
        "is_final",
    )
    list_filter = ("status", "review_outcome", "is_final")
    readonly_fields = tuple(
        field.name for field in CandidateEvaluation._meta.fields
    )
    inlines = (CriterionScoreInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(InterviewSchedule)
admin.site.register(InterviewRescheduleRequest)
