from django import forms

from interviews.evaluation_services import CriterionReview
from interviews.models import CandidateEvaluation


class HumanEvaluationForm(forms.Form):
    summary = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Summarize job-related evidence only. Do not copy a full transcript.",
    )
    reviewer_notes = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Required to finalize. These notes remain restricted to authorized reviewers.",
    )
    review_outcome = forms.ChoiceField(
        required=False,
        choices=(("", "Select a human outcome"), *CandidateEvaluation.ReviewOutcome.choices),
        help_text="Only an authorized human can finalize this outcome.",
    )

    def __init__(self, *args, evaluation, **kwargs):
        super().__init__(*args, **kwargs)
        self.evaluation = evaluation
        score_by_criterion = {
            score.criterion_id: score
            for score in evaluation.criterion_scores.select_related("criterion")
        }
        for criterion in evaluation.rubric.criteria.all():
            score = score_by_criterion.get(criterion.pk)
            prefix = f"criterion_{criterion.pk}"
            self.fields[f"{prefix}_score"] = forms.DecimalField(
                label=f"{criterion.name} score",
                min_value=0,
                max_value=100,
                decimal_places=2,
                required=criterion.is_required,
                initial=score.score if score else None,
                help_text=criterion.scoring_guidance or criterion.description,
            )
            self.fields[f"{prefix}_confidence"] = forms.DecimalField(
                label=f"{criterion.name} confidence",
                min_value=0,
                max_value=1,
                decimal_places=3,
                required=criterion.is_required,
                initial=score.confidence if score else None,
                help_text="Use 0 for no confidence and 1 for complete confidence.",
            )
            self.fields[f"{prefix}_evidence"] = forms.CharField(
                label=f"{criterion.name} evidence",
                max_length=1200,
                required=criterion.is_required,
                initial=score.evidence if score else "",
                widget=forms.Textarea(attrs={"rows": 3}),
                help_text="Record concise, job-related evidence; do not paste a full answer or transcript.",
            )
            self.fields[f"{prefix}_explanation"] = forms.CharField(
                label=f"{criterion.name} explanation",
                max_length=1200,
                required=False,
                initial=score.explanation if score else "",
                widget=forms.Textarea(attrs={"rows": 2}),
            )
        if not self.is_bound:
            self.initial.update(
                {
                    "summary": evaluation.summary,
                    "reviewer_notes": evaluation.reviewer_notes,
                    "review_outcome": evaluation.review_outcome,
                }
            )

    def criterion_reviews(self):
        reviews = []
        for criterion in self.evaluation.rubric.criteria.all():
            prefix = f"criterion_{criterion.pk}"
            score = self.cleaned_data.get(f"{prefix}_score")
            confidence = self.cleaned_data.get(f"{prefix}_confidence")
            if score is None and confidence is None and not criterion.is_required:
                continue
            reviews.append(
                CriterionReview(
                    criterion_id=criterion.pk,
                    score=score,
                    confidence=confidence,
                    evidence=self.cleaned_data.get(f"{prefix}_evidence", ""),
                    explanation=self.cleaned_data.get(
                        f"{prefix}_explanation",
                        "",
                    ),
                )
            )
        return reviews
