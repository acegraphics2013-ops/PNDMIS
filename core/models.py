from django.conf import settings
from django.db import models
from django.utils import timezone


class Unit(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['active', 'name'], name='unit_active_name_idx')]

    def __str__(self):
        return self.name


class Category(models.Model):
    KINDS = [
        ('record', 'Record classification'),
        ('deliverable', 'Deliverable type'),
        ('training', 'Training category'),
    ]
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KINDS, default='record')
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['kind', 'name']
        constraints = [models.UniqueConstraint(fields=['name', 'kind'], name='unique_category_name_kind')]

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'


class Profile(models.Model):
    ROLES = [('supervisor', 'Department Supervisor'), ('manager', 'Unit Manager'), ('staff', 'Nursing Staff')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='nursing_profile')
    role = models.CharField(max_length=12, choices=ROLES, default='staff')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        return self.user.get_username()


class StaffRecord(models.Model):
    EMPLOYMENT = [
        ('permanent', 'Permanent'),
        ('temporary', 'Temporary'),
        ('contractual', 'Contractual'),
        ('part_time', 'Part-time'),
        ('resigned', 'Resigned'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='staff_record')
    employee_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    position = models.CharField(max_length=100, blank=True)
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT, default='permanent')
    birthday = models.DateField(null=True, blank=True)
    contact_number = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    prc_number = models.CharField(max_length=80, blank=True)
    prc_expiry = models.DateField(null=True, blank=True)
    pna_membership = models.CharField(max_length=100, blank=True)
    ansap_membership = models.CharField(max_length=100, blank=True)
    document_reference = models.CharField(
        max_length=250, blank=True,
        help_text='Opaque ID in the approved private document store; never a public URL.',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['user__last_name', 'user__first_name', 'user__username']
        indexes = [
            models.Index(fields=['unit', 'active'], name='staff_unit_active_idx'),
            models.Index(fields=['prc_expiry'], name='staff_prc_expiry_idx'),
        ]

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class Deliverable(models.Model):
    TYPES = [('DTR', 'DTR'), ('DAR', 'DAR'), ('IPCR', 'IPCR'), ('OTHER', 'Other')]
    STATUSES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('review', 'Under review'),
        ('returned', 'Returned for correction'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
    ]
    staff = models.ForeignKey(StaffRecord, on_delete=models.PROTECT, related_name='deliverables')
    type = models.CharField(max_length=8, choices=TYPES)
    period = models.CharField(max_length=60)
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUSES, default='pending')
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='reviewed_deliverables',
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='verified_deliverables',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='approved_deliverables',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='created_deliverables',
    )
    remarks = models.TextField(blank=True)
    document_reference = models.CharField(
        max_length=250, blank=True,
        help_text='Opaque ID in approved private document store; never a public URL',
    )
    submission_count = models.PositiveSmallIntegerField(default=0)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['due_date', 'type']
        constraints = [models.UniqueConstraint(fields=['staff', 'type', 'period'], name='unique_staff_requirement_period')]
        indexes = [
            models.Index(fields=['status', 'due_date'], name='deliv_status_due_idx'),
            models.Index(fields=['staff', 'status'], name='deliv_staff_status_idx'),
            models.Index(fields=['archived', 'due_date'], name='deliv_archived_due_idx'),
        ]

    def __str__(self):
        return f'{self.type} · {self.staff} · {self.period}'

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return self.due_date < timezone.localdate() and self.status not in ('verified', 'approved')


class Training(models.Model):
    STATUSES = [('planned', 'Planned'), ('attended', 'Attended'), ('completed', 'Completed')]
    VALIDATION = [('pending', 'Pending validation'), ('validated', 'Validated'), ('returned', 'Returned')]
    staff = models.ForeignKey(StaffRecord, on_delete=models.PROTECT, related_name='training')
    title = models.CharField(max_length=250)
    date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    provider = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default='planned')
    validation_status = models.CharField(max_length=20, choices=VALIDATION, default='validated')
    validation_remarks = models.TextField(blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='validated_training',
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    certificate_reference = models.CharField(max_length=250, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True, blank=True, related_name='training')
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-date', 'title']
        indexes = [
            models.Index(fields=['staff', 'date'], name='training_staff_date_idx'),
            models.Index(fields=['validation_status'], name='training_validation_idx'),
        ]

    def __str__(self):
        return f'{self.title} · {self.staff}'

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class Task(models.Model):
    STATUSES = [
        ('pending', 'Pending'),
        ('progress', 'In progress'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True, blank=True, related_name='tasks')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    due_date = models.DateField()
    priority = models.CharField(max_length=10, choices=[('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')], default='normal')
    status = models.CharField(max_length=15, choices=STATUSES, default='pending')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='created_tasks',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-priority']
        indexes = [
            models.Index(fields=['status', 'due_date'], name='task_status_due_idx'),
            models.Index(fields=['unit', 'status'], name='task_unit_status_idx'),
            models.Index(fields=['assignee', 'status'], name='task_assignee_status_idx'),
        ]

    def __str__(self):
        return self.title


class ShiftCount(models.Model):
    SHIFTS = [('day', 'Day'), ('night', 'Night')]
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    date = models.DateField()
    shift = models.CharField(max_length=10, choices=SHIFTS)
    on_duty = models.PositiveSmallIntegerField()
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-date', 'unit__name', 'shift']
        constraints = [models.UniqueConstraint(fields=['unit', 'date', 'shift'], name='unique_unit_date_shift')]
        indexes = [
            models.Index(fields=['unit', 'date'], name='shift_unit_date_idx'),
            models.Index(fields=['date'], name='shift_date_idx'),
        ]

    def __str__(self):
        return f'{self.unit} · {self.date} · {self.get_shift_display()}'

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class Notification(models.Model):
    CATEGORIES = [
        ('deadline', 'Deadline'),
        ('approval', 'Approval'),
        ('task', 'Task'),
        ('license', 'License'),
        ('training', 'Training'),
        ('system', 'System'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='system')
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=200, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read', 'created_at'], name='notif_user_read_idx')]

    def __str__(self):
        return self.title


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    event = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.PositiveBigIntegerField()
    target_label = models.CharField(max_length=250, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    detail = models.JSONField(default=dict, blank=True)
    previous = models.JSONField(default=dict, blank=True)
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['occurred_at'], name='audit_occurred_idx'),
            models.Index(fields=['object_type', 'object_id'], name='audit_object_idx'),
            models.Index(fields=['event'], name='audit_event_idx'),
        ]

    def __str__(self):
        return f'{self.event} · {self.object_type} #{self.object_id}'
