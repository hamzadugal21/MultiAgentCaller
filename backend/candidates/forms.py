from django import forms

from candidates.models import CandidateProfile, Resume


class CandidateProfileForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = (
            "phone_number",
            "city",
            "country_code",
            "timezone",
            "professional_summary",
            "years_of_experience",
            "availability",
        )


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ("file",)
