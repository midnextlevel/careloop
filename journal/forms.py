from django import forms
from django.utils import timezone
from .models import Entry, Membership


class EntryForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput)
    class Meta:
        model = Entry
        fields = ['event_date', 'kind', 'summary', 'observations', 'what_helped', 'follow_up', 'audience']
        widgets = {'event_date': forms.DateInput(attrs={'type': 'date'}),
                   **{field: forms.Textarea(attrs={'rows': 4}) for field in ['summary', 'observations', 'what_helped', 'follow_up']}}
        labels = {'kind': 'Entry type', 'summary': 'Daily summary', 'what_helped': 'What helped', 'follow_up': 'Follow-up (optional)'}


class MemberForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['history_start'].required = False
            self.initial['history_start'] = None
            self.fields['history_start'].help_text = 'Leave blank to start at the exact approval time. Enter an Asia/Manila time only to deliberately grant another history start.'

    class Meta:
        model = Membership
        fields = ['email', 'role', 'active', 'history_start']
        widgets = {'history_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}
        help_texts = {'history_start': 'Asia/Manila time. Earlier times explicitly grant access to older care-team entries.'}

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if self.instance.pk and email != self.instance.email:
            raise forms.ValidationError('Email identities cannot be renamed. Revoke and approve a new membership.')
        return email

    def clean_history_start(self):
        value = self.cleaned_data.get('history_start')
        if self.instance.pk and value is not None:
            original = self.instance.history_start
            # Browsers post the displayed minute, not the stored seconds/microseconds.
            # Keeping that displayed value means no deliberate history adjustment.
            displayed = timezone.localtime(original).replace(second=0, microsecond=0)
            if value == displayed:
                return original
        return value
