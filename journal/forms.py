from django import forms
from django.utils import timezone
from .models import Entry, Membership, JournalAccessSettings


class TimelineDateForm(forms.Form):
    date = forms.DateField(required=False, label='Find a date', input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))


class JournalAccessForm(forms.ModelForm):
    class Meta:
        model = JournalAccessSettings
        fields = ['access_until', 'access_days', 'expire_authors']
        labels = {'access_days': 'Days of access after submission',
                  'access_until': 'Fixed access deadline (optional)',
                  'expire_authors': 'Also expire access to their own submitted entries'}
        widgets = {'access_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}
        help_texts = {'access_until': 'Pick an Asia/Manila date and time to close access to all submitted entries. Leave blank to use the number of days below. Individual entry deadlines take precedence.',
                     'access_days': 'Used when the fixed deadline is blank. Applies to existing and new submitted entries; the owner retains access.'}

    def clean_access_until(self):
        value = self.cleaned_data.get('access_until')
        original = self.instance.access_until
        if value and original and value == timezone.localtime(original).replace(second=0, microsecond=0):
            return original
        return value


class EntryAccessForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ['professional_access_until']
        labels = {'professional_access_until': 'Allow professional access until'}
        widgets = {'professional_access_until': forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}
        help_texts = {'professional_access_until': 'Asia/Manila time. Leave blank to use the journal-wide access period. Audience and membership history restrictions still apply.'}

    def clean_professional_access_until(self):
        value = self.cleaned_data.get('professional_access_until')
        original = self.instance.professional_access_until
        if value and original and value == timezone.localtime(original).replace(second=0, microsecond=0):
            return original
        return value


class EntryForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].choices = [(Entry.Kind.SCHOOL, 'School'), (Entry.Kind.THERAPY, 'Therapy')]

    class Meta:
        model = Entry
        fields = ['event_date', 'kind', 'summary', 'observations', 'what_helped', 'follow_up', 'audience']
        widgets = {'event_date': forms.DateInput(attrs={'type': 'date'}),
                   **{field: forms.Textarea(attrs={'rows': 3}) for field in ['summary', 'observations', 'what_helped', 'follow_up']}}
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
