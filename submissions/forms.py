from django import forms


class SubmissionUploadForm(forms.Form):
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-input'}),
    )
    files = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': 'form-input'}),
    )

    def __init__(self, *args, files=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.uploaded_files = files.getlist('files') if files else []

    def clean(self):
        cleaned = super().clean()
        if not self.uploaded_files:
            raise forms.ValidationError('Please upload at least one file.')

        max_size = 25 * 1024 * 1024
        for uploaded_file in self.uploaded_files:
            if uploaded_file.size > max_size:
                raise forms.ValidationError(f'{uploaded_file.name} is larger than 25 MB.')
        return cleaned


class SubmissionReviewForm(forms.Form):
    score = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=100,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0', 'max': '100'}),
    )
    status = forms.ChoiceField(
        choices=[
            ('reviewed', 'Reviewed'),
            ('approved', 'Approved'),
            ('revision', 'Revision Needed'),
        ],
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    feedback = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-input'}),
    )

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        score = cleaned.get('score')
        feedback = (cleaned.get('feedback') or '').strip()

        if status in {'reviewed', 'approved'} and score is None:
            raise forms.ValidationError('A score is required when reviewing or approving a submission.')
        if status == 'revision' and not feedback:
            raise forms.ValidationError('Feedback is required when requesting a revision.')
        return cleaned
