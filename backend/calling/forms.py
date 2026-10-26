import uuid

from django import forms

from calling.services import MAX_SIMULATED_ANSWER_CHARACTERS


class SessionPreparationForm(forms.Form):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("idempotency_key", uuid.uuid4())


class SimulatedAnswerForm(forms.Form):
    answer_text = forms.CharField(
        max_length=MAX_SIMULATED_ANSWER_CHARACTERS,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "autocomplete": "off",
            }
        ),
    )
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("idempotency_key", uuid.uuid4())
