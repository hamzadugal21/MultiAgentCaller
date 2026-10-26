from django import forms

from candidates.models import Resume
from recruitment.models import InterviewQuestion, JobFAQ, JobPosting


class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = (
            "title",
            "reference_code",
            "description",
            "responsibilities",
            "minimum_qualifications",
            "preferred_qualifications",
            "location",
            "employment_type",
            "workplace_type",
            "minimum_experience_years",
            "maximum_experience_years",
            "salary_minimum",
            "salary_maximum",
            "salary_currency",
            "application_deadline",
        )
        widgets = {"application_deadline": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class JobSkillRequirementForm(forms.Form):
    skill_name = forms.CharField(max_length=100)
    minimum_proficiency = forms.IntegerField(min_value=1, max_value=5)
    minimum_years = forms.DecimalField(min_value=0, max_digits=4, decimal_places=1)
    weight = forms.DecimalField(min_value=0, max_value=1, max_digits=4, decimal_places=3)
    is_mandatory = forms.BooleanField(required=False)


class InterviewQuestionForm(forms.ModelForm):
    class Meta:
        model = InterviewQuestion
        fields = (
            "question_text",
            "question_type",
            "order",
            "maximum_response_seconds",
            "scoring_guidance",
            "is_required",
            "is_active",
        )


class JobFAQForm(forms.ModelForm):
    class Meta:
        model = JobFAQ
        fields = ("question", "answer", "is_active")


class JobApplicationForm(forms.Form):
    resume = forms.ModelChoiceField(queryset=Resume.objects.none())
    cover_note = forms.CharField(required=False, widget=forms.Textarea)
    consent_to_ai_interview = forms.BooleanField(required=False)

    def __init__(self, *args, candidate, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resume"].queryset = Resume.objects.filter(
            candidate=candidate,
            is_active=True,
            processing_status=Resume.ProcessingStatus.COMPLETED,
        )


class InterviewInvitationForm(forms.Form):
    scheduled_start = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    scheduled_end = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    timezone = forms.CharField(max_length=64, initial="Asia/Karachi")


class InterviewRescheduleForm(InterviewInvitationForm):
    reason = forms.CharField(required=False, max_length=1000, widget=forms.Textarea)
