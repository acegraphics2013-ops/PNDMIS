import calendar
import re
from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .access import (
    MANAGER,
    STAFF,
    SUPERVISOR,
    permitted_staff,
    permitted_units,
    profile,
    task_assignable_users,
)
from .models import (
    Category,
    Deliverable,
    Profile,
    ShiftCount,
    StaffRecord,
    Task,
    Training,
    Unit,
)

OPAQUE_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{1,249}$')


def validate_opaque_reference(value, label='document reference'):
    value = (value or '').strip()
    if not value:
        raise ValidationError(f'Enter an opaque secure {label}.')
    if '/' in value or '\\' in value or ':' in value or '..' in value:
        raise ValidationError('Use an opaque secure document ID, not a URL or file path.')
    if not OPAQUE_REF.match(value):
        raise ValidationError('Use only letters, numbers, dots, hyphens and underscores.')
    return value


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'description', 'active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if len(name) < 2:
            raise ValidationError('Unit name must be at least 2 characters.')
        qs = Unit.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('A unit with this name already exists.')
        return name


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'kind', 'description', 'active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if len(name) < 2:
            raise ValidationError('Classification name must be at least 2 characters.')
        kind = self.cleaned_data.get('kind')
        qs = Category.objects.filter(name__iexact=name, kind=kind)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('A classification with this name and type already exists.')
        return name


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'unit', 'category', 'assignee', 'due_date', 'priority', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        p = profile(actor)
        self.fields['unit'].queryset = permitted_units(actor).filter(active=True)
        self.fields['category'].queryset = Category.objects.filter(kind='record', active=True)
        self.fields['category'].required = False
        self.fields['assignee'].required = False
        self.fields['assignee'].queryset = task_assignable_users(actor)
        if p.role == MANAGER:
            self.fields['unit'].queryset = Unit.objects.filter(pk=p.unit_id, active=True)
            self.fields['unit'].initial = p.unit_id
            self.fields['unit'].required = True
            self.fields['assignee'].queryset = task_assignable_users(actor, p.unit_id)
        if self.instance.pk:
            self.fields['assignee'].queryset = self.fields['assignee'].queryset | User.objects.filter(pk=self.instance.assignee_id)

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if len(title) < 3:
            raise ValidationError('Record name must be at least 3 characters.')
        return title

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get('unit')
        assignee = cleaned.get('assignee')
        actor_profile = profile(self.actor)
        if actor_profile.role == MANAGER:
            if not unit or unit.pk != actor_profile.unit_id:
                raise ValidationError({'unit': 'You may only file records under your assigned unit.'})
        if assignee:
            try:
                assignee_profile = assignee.nursing_profile
            except Profile.DoesNotExist:
                raise ValidationError({'assignee': 'The selected user has no approved nursing role.'})
            if unit and assignee_profile.unit_id and assignee_profile.unit_id != unit.pk:
                raise ValidationError({'assignee': 'The assignee must belong to the selected unit.'})
            if actor_profile.role == MANAGER and assignee_profile.unit_id != actor_profile.unit_id:
                raise ValidationError({'assignee': 'You may only assign users in your own unit.'})
        category = cleaned.get('category')
        if category and category.kind != 'record':
            raise ValidationError({'category': 'Choose a record classification.'})
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.pk and not obj.created_by_id:
            obj.created_by = self.actor
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class TaskStatusForm(forms.Form):
    status = forms.ChoiceField(choices=[('pending', 'Pending'), ('progress', 'In progress'), ('completed', 'Completed')])

    def __init__(self, task, *args, **kwargs):
        self.task = task
        super().__init__(*args, **kwargs)
        self.fields['status'].initial = task.status


class StaffRecordForm(forms.ModelForm):
    class Meta:
        model = StaffRecord
        fields = [
            'user', 'employee_number', 'unit', 'position', 'employment_status', 'birthday',
            'contact_number', 'address', 'prc_number', 'prc_expiry', 'pna_membership',
            'ansap_membership', 'document_reference', 'active',
        ]
        widgets = {
            'birthday': forms.DateInput(attrs={'type': 'date'}),
            'prc_expiry': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    SENSITIVE_FIELDS = ['birthday', 'contact_number', 'address', 'prc_number', 'prc_expiry']
    MANAGER_FIELDS = ['position', 'employment_status', 'pna_membership', 'ansap_membership', 'active']
    OWNER_FIELDS = [
        'birthday', 'contact_number', 'address', 'prc_number', 'prc_expiry',
        'pna_membership', 'ansap_membership', 'document_reference',
    ]

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        p = profile(actor)
        self.fields['unit'].queryset = permitted_units(actor)
        self.fields['document_reference'].required = False
        if self.instance.pk:
            if p.role == SUPERVISOR:
                allowed = list(self.fields.keys())
            elif self.instance.user_id == actor.id:
                allowed = self.OWNER_FIELDS
            else:
                allowed = self.MANAGER_FIELDS
        else:
            allowed = list(self.fields.keys())
        for name in list(self.fields):
            if name not in allowed:
                del self.fields[name]
        if 'user' in self.fields:
            self.fields['user'].queryset = User.objects.filter(staff_record__isnull=True).order_by('username')
        if p.role != SUPERVISOR and 'unit' in self.fields:
            self.fields['unit'].queryset = permitted_units(actor)
        if 'active' in self.fields and p.role == SUPERVISOR:
            self.fields['active'].help_text = 'Deactivation keeps the 201 file and history for accountability.'
        self.fields['employee_number'].required = False

    def clean_employee_number(self):
        number = (self.cleaned_data.get('employee_number') or '').strip()
        if not number:
            return None
        qs = StaffRecord.objects.filter(employee_number__iexact=number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('This employee number is already assigned.')
        return number

    def clean_document_reference(self):
        value = (self.cleaned_data.get('document_reference') or '').strip()
        if not value:
            return ''
        return validate_opaque_reference(value)

    def clean_prc_expiry(self):
        value = self.cleaned_data.get('prc_expiry')
        if value and value.year < 1950:
            raise ValidationError('Enter a valid PRC expiration date.')
        return value

    def clean(self):
        cleaned = super().clean()
        p = profile(self.actor)
        if p.role == MANAGER and self.instance.pk:
            if self.instance.unit_id != p.unit_id:
                raise ValidationError('You may only edit staff in your assigned unit.')
        if 'unit' in cleaned and p.role == MANAGER and cleaned.get('unit') and cleaned['unit'].pk != p.unit_id:
            raise ValidationError({'unit': 'You may only assign staff to your own unit.'})
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.pk:
            if not obj.unit_id:
                obj.unit = profile(self.actor).unit
        if commit:
            obj.save()
            try:
                user_profile = obj.user.nursing_profile
            except Profile.DoesNotExist:
                user_profile = None
            if user_profile and obj.unit_id and user_profile.unit_id != obj.unit_id:
                user_profile.unit = obj.unit
                user_profile.save(update_fields=['unit'])
        return obj


class DeliverableForm(forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = ['staff', 'type', 'period', 'due_date']
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = permitted_staff(actor).filter(active=True)
        if self.instance.pk and self.instance.status not in ('pending', 'returned'):
            for name in ['staff', 'type', 'period']:
                self.fields.pop(name, None)

    def clean_period(self):
        period = (self.cleaned_data.get('period') or '').strip()
        if len(period) < 2:
            raise ValidationError('Enter a period identifier, for example 2026-10.')
        return period

    def clean(self):
        cleaned = super().clean()
        p = profile(self.actor)
        staff = cleaned.get('staff')
        if staff and p.role == MANAGER and staff.unit_id != p.unit_id:
            raise ValidationError({'staff': 'You may only create requirements for your own unit.'})
        if self.instance.pk and self.instance.status not in ('pending', 'returned'):
            staff = self.instance.staff
        if staff and cleaned.get('period') and cleaned.get('type'):
            qs = Deliverable.objects.filter(staff=staff, type=cleaned['type'], period=cleaned['period'])
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('A deliverable of this type already exists for that staff member and period.')
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.pk:
            obj.status = 'pending'
            obj.created_by = self.actor
        if commit:
            obj.save()
        return obj


class BulkDeliverableForm(forms.Form):
    staff = forms.ModelMultipleChoiceField(queryset=StaffRecord.objects.none())
    type = forms.ChoiceField(choices=Deliverable.TYPES)
    start_month = forms.RegexField(
        regex=r'^\d{4}-(0[1-9]|1[0-2])$',
        error_messages={'invalid': 'Use YYYY-MM, for example 2026-10.'},
        label='Start month (YYYY-MM)',
    )
    months = forms.IntegerField(min_value=1, max_value=12, initial=1)
    due_day = forms.IntegerField(min_value=1, max_value=28, initial=28, help_text='Due day of each month (1-28).')

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = permitted_staff(actor).filter(active=True)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_month')
        months = cleaned.get('months')
        day = cleaned.get('due_day')
        if start and months and day:
            year, month = [int(x) for x in start.split('-')]
            periods = []
            for offset in range(months):
                y = year + (month - 1 + offset) // 12
                m = (month - 1 + offset) % 12 + 1
                last_day = calendar.monthrange(y, m)[1]
                periods.append((f'{y:04d}-{m:02d}', date(y, m, min(day, last_day))))
            cleaned['periods'] = periods
        return cleaned


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = ['document_reference']
        widgets = {'document_reference': forms.TextInput(attrs={'placeholder': 'e.g. DOC-2026-000123'})}

    def clean_document_reference(self):
        return validate_opaque_reference(self.cleaned_data.get('document_reference'))


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[
        ('start_review', 'Start review'),
        ('verified', 'Verify'),
        ('returned', 'Return for correction'),
        ('approved', 'Approve'),
    ])
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)

    def __init__(self, deliverable, actor, *args, **kwargs):
        self.deliverable = deliverable
        self.actor = actor
        super().__init__(*args, **kwargs)
        p = profile(actor)
        if deliverable.status == 'submitted':
            allowed = ['start_review', 'verified', 'returned']
        elif deliverable.status == 'review':
            allowed = ['verified', 'returned']
        elif deliverable.status == 'verified':
            allowed = ['approved', 'returned'] if p.role == SUPERVISOR else ['returned']
        else:
            allowed = []
        self.fields['decision'].choices = [
            (k, v) for k, v in self.fields['decision'].choices if k in allowed
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'returned' and not (cleaned.get('remarks') or '').strip():
            raise ValidationError('Remarks are required when returning a deliverable for correction.')
        return cleaned


class TrainingForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['staff', 'title', 'date', 'hours', 'provider', 'status', 'category', 'certificate_reference']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        p = profile(actor)
        if p.role == STAFF:
            self.fields.pop('staff', None)
        else:
            self.fields['staff'].queryset = permitted_staff(actor).filter(active=True)
        self.fields['category'].queryset = Category.objects.filter(kind='training', active=True)
        self.fields['category'].required = False
        self.fields['certificate_reference'].required = False
        if 'staff' in self.fields and p.role == MANAGER:
            self.fields['staff'].queryset = permitted_staff(actor).filter(active=True, unit_id=p.unit_id)

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if len(title) < 3:
            raise ValidationError('Training title must be at least 3 characters.')
        return title

    def clean_hours(self):
        hours = self.cleaned_data.get('hours')
        if hours is None:
            return 0
        if hours < 0 or hours > 1000:
            raise ValidationError('Enter training hours between 0 and 1000.')
        return hours

    def clean_certificate_reference(self):
        value = (self.cleaned_data.get('certificate_reference') or '').strip()
        if not value:
            return ''
        return validate_opaque_reference(value, 'certificate reference')

    def clean(self):
        cleaned = super().clean()
        p = profile(self.actor)
        if p.role == STAFF:
            kind = cleaned.get('category')
            if kind and kind.kind != 'training':
                raise ValidationError({'category': 'Choose a training category.'})
        elif cleaned.get('staff'):
            staff = cleaned['staff']
            if p.role == MANAGER and staff.unit_id != p.unit_id:
                raise ValidationError({'staff': 'You may only record training for your own unit.'})
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        p = profile(self.actor)
        if p.role == STAFF:
            obj.staff = getattr(self.actor, 'staff_record', None)
            if obj.staff is None:
                raise ValidationError('Your account has no 201 file. Contact your supervisor.')
            if not obj.pk:
                obj.validation_status = 'pending'
            elif obj.validation_status == 'returned':
                obj.validation_status = 'pending'
                obj.validated_by = None
                obj.validated_at = None
        elif not obj.pk:
            obj.validation_status = 'validated'
            obj.validated_by = self.actor
            obj.validated_at = timezone.now()
        if commit:
            obj.save()
        return obj


class TrainingValidationForm(forms.Form):
    decision = forms.ChoiceField(choices=[('validated', 'Validate'), ('returned', 'Return for correction')])
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'returned' and not (cleaned.get('remarks') or '').strip():
            raise ValidationError('Remarks are required when returning a training record.')
        return cleaned


class ShiftForm(forms.ModelForm):
    class Meta:
        model = ShiftCount
        fields = ['unit', 'date', 'shift', 'on_duty']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        p = profile(actor)
        self.fields['unit'].queryset = permitted_units(actor).filter(active=True)
        if p.role == MANAGER:
            self.fields['unit'].queryset = Unit.objects.filter(pk=p.unit_id, active=True)
            self.fields['unit'].initial = p.unit_id
            self.fields['unit'].required = True

    def clean_on_duty(self):
        value = self.cleaned_data.get('on_duty')
        if value is None or value < 0:
            raise ValidationError('Enter a valid on-duty count.')
        if value > 500:
            raise ValidationError('On-duty count looks invalid (maximum 500).')
        return value

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get('unit')
        day = cleaned.get('date')
        shift = cleaned.get('shift')
        p = profile(self.actor)
        if p.role == MANAGER and unit and unit.pk != p.unit_id:
            raise ValidationError({'unit': 'You may only manage shift counts for your assigned unit.'})
        if unit and day and shift:
            qs = ShiftCount.objects.filter(unit=unit, date=day, shift=shift)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('A shift count already exists for this unit, date and shift. Edit the existing entry instead.')
        return cleaned


class UserCreateForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=Profile.ROLES)
    unit = forms.ModelChoiceField(queryset=Unit.objects.filter(active=True), required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    create_staff_record = forms.BooleanField(required=False, initial=True)
    employee_number = forms.CharField(max_length=40, required=False)
    position = forms.CharField(max_length=100, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        unit = cleaned.get('unit')
        if role in (MANAGER, STAFF) and not unit:
            raise ValidationError({'unit': 'A unit is required for managers and nursing staff.'})
        employee_number = (cleaned.get('employee_number') or '').strip()
        if employee_number and StaffRecord.objects.filter(employee_number__iexact=employee_number).exists():
            raise ValidationError({'employee_number': 'This employee number is already assigned.'})
        cleaned['employee_number'] = employee_number or None
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_active = self.cleaned_data.get('is_active', True)
        if commit:
            user.save()
            Profile.objects.create(user=user, role=self.cleaned_data['role'], unit=self.cleaned_data.get('unit'))
            if (
                self.cleaned_data.get('create_staff_record')
                and self.cleaned_data['role'] in (MANAGER, STAFF)
                and self.cleaned_data.get('unit')
            ):
                StaffRecord.objects.create(
                    user=user,
                    unit=self.cleaned_data['unit'],
                    employee_number=self.cleaned_data.get('employee_number'),
                    position=self.cleaned_data.get('position') or '',
                )
        return user


class UserUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Profile.ROLES)
    unit = forms.ModelChoiceField(queryset=Unit.objects.all(), required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, actor, target, *args, **kwargs):
        self.actor = actor
        self.target = target
        super().__init__(*args, **kwargs)
        try:
            current_profile = target.nursing_profile
            self.fields['role'].initial = current_profile.role
            self.fields['unit'].initial = current_profile.unit_id
        except Profile.DoesNotExist:
            pass

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        qs = User.objects.filter(username__iexact=username)
        if self.target.pk:
            qs = qs.exclude(pk=self.target.pk)
        if qs.exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        unit = cleaned.get('unit')
        is_active = cleaned.get('is_active')
        if role in (MANAGER, STAFF) and not unit:
            raise ValidationError({'unit': 'A unit is required for managers and nursing staff.'})
        if self.target.pk == self.actor.pk:
            if role != SUPERVISOR:
                raise ValidationError({'role': 'You cannot remove your own supervisor role.'})
            if not is_active:
                raise ValidationError({'is_active': 'You cannot deactivate your own account.'})
        was_supervisor = False
        try:
            was_supervisor = self.target.nursing_profile.role == SUPERVISOR
        except Profile.DoesNotExist:
            pass
        if was_supervisor and (role != SUPERVISOR or not is_active):
            other_supervisors = Profile.objects.filter(role=SUPERVISOR, user__is_active=True).exclude(user=self.target)
            if not other_supervisors.exists():
                raise ValidationError('At least one active supervisor account must remain.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            prof, _ = Profile.objects.get_or_create(user=user, defaults={'role': self.cleaned_data['role']})
            old_unit = prof.unit_id
            prof.role = self.cleaned_data['role']
            prof.unit = self.cleaned_data.get('unit')
            prof.save()
            staff = getattr(user, 'staff_record', None)
            if staff and prof.unit_id and staff.unit_id != prof.unit_id:
                staff.unit = prof.unit
                staff.save(update_fields=['unit', 'updated_at'])
        return user


class ProfileSelfForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class ReportFilterForm(forms.Form):
    KIND_CHOICES = [
        ('compliance', 'Deliverable compliance'),
        ('training', 'Training completion'),
        ('licenses', 'Expiring PRC licenses'),
        ('shifts', 'Shift counts'),
        ('tasks', 'Overdue tasks'),
    ]
    kind = forms.ChoiceField(choices=KIND_CHOICES, required=False, initial='compliance')
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    unit = forms.ModelChoiceField(queryset=Unit.objects.none(), required=False, empty_label='All units')
    staff = forms.ModelChoiceField(queryset=StaffRecord.objects.none(), required=False, empty_label='All staff')
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses')] + Deliverable.STATUSES)
    type = forms.ChoiceField(required=False, choices=[('', 'All types')] + Deliverable.TYPES)
    q = forms.CharField(required=False, max_length=100)
    horizon = forms.IntegerField(required=False, min_value=1, max_value=730, initial=90, label='License horizon (days)')

    def __init__(self, actor, *args, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        self.fields['unit'].queryset = permitted_units(actor)
        self.fields['staff'].queryset = permitted_staff(actor)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start')
        end = cleaned.get('end')
        if start and end and start > end:
            raise ValidationError('Start date must be on or before the end date.')
        unit = cleaned.get('unit')
        staff = cleaned.get('staff')
        if unit and staff and staff.unit_id != unit.pk:
            raise ValidationError({'staff': 'The selected staff member is not in the selected unit.'})
        return cleaned
