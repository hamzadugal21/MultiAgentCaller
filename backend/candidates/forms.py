from django import forms

from candidates.models import CandidateProfile, Resume


class CandidateProfileForm(forms.ModelForm):
    skills = forms.CharField(
        required=False,
        help_text="Add skills separated by commas.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    class Meta:
        model = CandidateProfile
        fields = (
            "phone_number",
            "city",
            "country_code",
            "professional_summary",
            "years_of_experience",
            "availability",
            "skills",
        )

    def clean_skills(self):
        raw = self.cleaned_data.get("skills", "")
        names = [name.strip() for name in raw.replace("\n", ",").split(",")]
        names = [name for name in names if name]
        normalized = {name.casefold() for name in names}
        if len(names) != len(normalized):
            raise forms.ValidationError("Each skill may be listed only once.")
        if any(len(name) > 100 for name in names):
            raise forms.ValidationError("Each skill must be 100 characters or fewer.")
        if len(names) > 30:
            raise forms.ValidationError("You may add up to 30 skills at a time.")
        return names


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ("file",)
