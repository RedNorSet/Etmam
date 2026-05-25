from django import forms

from .models import Milestone, MilestoneTemplate


class MilestoneTemplateForm(forms.ModelForm):
    class Meta:
        model = MilestoneTemplate
        fields = ['title', 'description', 'type', 'default_due_offset_days', 'default_weight', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Template title'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Standard instructions'}),
            'type': forms.Select(attrs={'class': 'form-input'}),
            'default_due_offset_days': forms.NumberInput(attrs={'class': 'form-input', 'min': '0'}),
            'default_weight': forms.NumberInput(attrs={'class': 'form-input', 'min': '0', 'max': '100'}),
            'is_active': forms.CheckboxInput(attrs={'style': 'accent-color:#2563eb;'}),
        }

    def clean_default_weight(self):
        weight = self.cleaned_data['default_weight']
        if weight > 100:
            raise forms.ValidationError('Weight cannot be greater than 100.')
        return weight


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ['title', 'description', 'type', 'due_date', 'weight']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Milestone title'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Instructions or deliverables'}),
            'type': forms.Select(attrs={'class': 'form-input'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'weight': forms.NumberInput(attrs={'class': 'form-input', 'min': '0', 'max': '100'}),
        }

    def clean_weight(self):
        weight = self.cleaned_data['weight']
        if weight > 100:
            raise forms.ValidationError('Weight cannot be greater than 100.')
        return weight
