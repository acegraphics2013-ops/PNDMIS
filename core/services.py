"""Business logic shared by HTML views, JSON endpoints and management commands."""
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .access import (
    MANAGER,
    STAFF,
    SUPERVISOR,
    can_manage_deliverable,
    can_review_deliverable,
    can_submit_deliverable,
    can_validate_training,
    profile,
)
from .models import AuditEvent, Deliverable, Notification, Profile, StaffRecord, Task, Training


def client_ip(request):
    if not request:
        return None
    value = request.META.get('REMOTE_ADDR')
    if not value:
        return None
    return value[:45]


def log_audit(actor, event, obj=None, *, object_type=None, object_id=None, target_label='',
              detail=None, previous=None, changes=None, request=None):
    """Persist an audit event. Never pass passwords, tokens or document contents."""
    if obj is not None:
        object_type = object_type or type(obj).__name__
        object_id = object_id or obj.pk
        target_label = target_label or str(obj)[:250]
    return AuditEvent.objects.create(
        actor=actor,
        event=event,
        object_type=object_type or 'Unknown',
        object_id=object_id or 0,
        target_label=target_label[:250],
        ip_address=client_ip(request),
        detail=detail or {},
        previous=previous or {},
        changes=changes or {},
    )


def notify(user, title, message='', category='system', url='', dedupe_key=None):
    if not user or not user.is_active:
        return None
    if dedupe_key:
        existing = Notification.objects.filter(dedupe_key=dedupe_key).first()
        if existing:
            return existing
    try:
        return Notification.objects.create(
            user=user,
            title=title[:200],
            message=message,
            category=category,
            url=url[:300],
            dedupe_key=dedupe_key,
        )
    except Exception:
        # A concurrent scheduler run may have inserted the same dedupe key.
        return Notification.objects.filter(dedupe_key=dedupe_key).first()


def notify_roles(roles, title, message='', category='system', url='', unit=None, dedupe_suffix=None):
    profiles = Profile.objects.filter(role__in=roles, user__is_active=True).select_related('user')
    if unit is not None:
        profiles = profiles.filter(unit=unit)
    created = 0
    for p in profiles:
        key = f'{dedupe_suffix}-{p.user_id}' if dedupe_suffix else None
        if notify(p.user, title, message, category, url, dedupe_key=key):
            created += 1
    return created


def _diff(previous, new):
    return {k: {'from': previous.get(k), 'to': new.get(k)} for k in new if previous.get(k) != new.get(k)}


DELIVERABLE_ACTIONS = {'start_review', 'verified', 'returned', 'approved'}


def transition_deliverable(deliverable, actor, action, remarks='', request=None):
    if action not in DELIVERABLE_ACTIONS:
        raise ValidationError('Unknown workflow action.')
    with transaction.atomic():
        d = (
            Deliverable.objects.select_for_update()
            .select_related('staff__user', 'staff__unit')
            .get(pk=deliverable.pk)
        )
        p = profile(actor)
        old_status = d.status
        if action == 'approved':
            if p.role != SUPERVISOR:
                raise PermissionDenied('Supervisor final approval is required.')
            if not can_manage_deliverable(actor, d):
                raise PermissionDenied('Not in your scope.')
            if d.status != 'verified':
                raise ValidationError('Only a verified deliverable can be approved.')
            d.status = 'approved'
            d.approved_by = actor
            d.approved_at = timezone.now()
            event = 'deliverable_approved'
            notification_title = 'Deliverable approved'
            notification_message = f'{d.type} {d.period} was approved.'
            notification_roles = [STAFF]
        else:
            if not can_review_deliverable(actor, d):
                raise PermissionDenied('You cannot review this deliverable.')
            if action == 'start_review':
                if d.status != 'submitted':
                    raise ValidationError('Only a submitted deliverable can enter review.')
                d.status = 'review'
                event = 'deliverable_review_started'
                notification_title = 'Deliverable under review'
                notification_message = f'{d.type} {d.period} is now under review.'
                notification_roles = [STAFF]
            elif action == 'verified':
                if d.status not in ('submitted', 'review'):
                    raise ValidationError('Only a submitted or under-review deliverable can be verified.')
                d.status = 'verified'
                d.verified_by = actor
                d.verified_at = timezone.now()
                event = 'deliverable_verified'
                notification_title = 'Deliverable verified'
                notification_message = f'{d.type} {d.period} was verified and awaits final approval.'
                notification_roles = [SUPERVISOR]
            else:
                if d.status not in ('submitted', 'review', 'verified'):
                    raise ValidationError('This deliverable cannot be returned in its current state.')
                remarks = (remarks or '').strip()
                if not remarks:
                    raise ValidationError('Remarks are required when returning a deliverable.')
                d.status = 'returned'
                d.returned_at = timezone.now()
                event = 'deliverable_returned'
                notification_title = 'Deliverable returned for correction'
                notification_message = remarks[:300]
                notification_roles = [STAFF]

        d.reviewer = actor
        d.reviewed_at = timezone.now()
        if remarks:
            d.remarks = remarks
        d.save()
        log_audit(
            actor, event, d,
            detail={'remarks': remarks[:500], 'status': d.status},
            previous={'status': old_status},
            changes={'status': {'from': old_status, 'to': d.status}},
            request=request,
        )
        if notification_roles == [STAFF]:
            notify(
                d.staff.user, notification_title,
                f'{d.type} · {d.period} · {notification_message}',
                'approval', f'/deliverables/{d.pk}/',
                dedupe_key=f'deliv-{d.pk}-{event}-{d.submission_count}',
            )
        elif notification_roles == [SUPERVISOR]:
            notify_roles(
                [SUPERVISOR], notification_title,
                f'{d.staff} · {d.type} · {d.period}',
                'approval', f'/deliverables/{d.pk}/',
                dedupe_suffix=f'deliv-{d.pk}-{event}',
            )
        return d


def submit_deliverable(deliverable, actor, document_reference, request=None):
    with transaction.atomic():
        d = (
            Deliverable.objects.select_for_update()
            .select_related('staff__user', 'staff__unit')
            .get(pk=deliverable.pk)
        )
        if not can_submit_deliverable(actor, d):
            raise PermissionDenied('You may only submit your own open requirements.')
        old_status = d.status
        d.document_reference = document_reference
        d.status = 'submitted'
        d.submitted_at = timezone.now()
        d.submission_count += 1
        d.save()
        log_audit(
            actor, 'deliverable_submitted', d,
            detail={'document_reference': d.document_reference, 'submission_count': d.submission_count},
            previous={'status': old_status},
            changes={'status': {'from': old_status, 'to': 'submitted'}},
            request=request,
        )
        notify_roles(
            [MANAGER], 'Deliverable submitted for verification',
            f'{d.staff} submitted {d.type} for {d.period}.',
            'approval', f'/deliverables/{d.pk}/', unit=d.staff.unit_id,
            dedupe_suffix=f'deliv-{d.pk}-submitted-{d.submission_count}',
        )
        return d


def validate_training(training, actor, decision, remarks='', request=None):
    if decision not in ('validated', 'returned'):
        raise ValidationError('Invalid training decision.')
    remarks = (remarks or '').strip()
    if decision == 'returned' and not remarks:
        raise ValidationError('Remarks are required when returning a training record.')
    with transaction.atomic():
        t = Training.objects.select_for_update().select_related('staff__user', 'staff__unit').get(pk=training.pk)
        if not can_validate_training(actor, t):
            raise PermissionDenied('You cannot validate this training record.')
        old = t.validation_status
        t.validation_status = decision
        t.validation_remarks = remarks
        t.validated_by = actor
        t.validated_at = timezone.now()
        t.save()
        log_audit(
            actor, f'training_{decision}', t,
            detail={'remarks': remarks[:500]},
            previous={'validation_status': old},
            changes={'validation_status': {'from': old, 'to': decision}},
            request=request,
        )
        notify(
            t.staff.user,
            'Training validated' if decision == 'validated' else 'Training returned for correction',
            f'{t.title}' + (f' · {remarks[:250]}' if remarks else ''),
            'training', '/training/',
            dedupe_key=f'training-{t.pk}-{decision}-{old}',
        )
        return t


def _create_reminder(user, title, message, category, url, key, dry_run, stats):
    if dry_run:
        if not Notification.objects.filter(dedupe_key=key).exists():
            stats['planned'] += 1
        return
    if Notification.objects.filter(dedupe_key=key).exists():
        stats['skipped'] += 1
        return
    Notification.objects.create(
        user=user, title=title[:200], message=message, category=category,
        url=url[:300], dedupe_key=key,
    )
    stats['created'] += 1


def run_reminders(today=None, dry_run=False):
    """Create in-app reminder notifications. Intended for a scheduler:
    `python manage.py send_reminders` (see README). No background worker is assumed.
    """
    today = today or timezone.localdate()
    stats = {'created': 0, 'skipped': 0, 'planned': 0}
    open_deliverables = Deliverable.objects.filter(
        archived=False,
    ).exclude(status__in=['approved']).select_related('staff__user', 'staff__unit')

    for d in open_deliverables:
        days = (d.due_date - today).days
        stage = None
        if days in (7, 3, 1):
            stage = f'{days}d'
        elif days < 0:
            stage = 'overdue'
        if stage and d.status in ('pending', 'returned'):
            _create_reminder(
                d.staff.user,
                'Deliverable overdue' if stage == 'overdue' else 'Deliverable due soon',
                f'{d.type} for {d.period} is due {d.due_date}.',
                'deadline', f'/deliverables/{d.pk}/',
                f'deliv-{d.pk}-{stage}', dry_run, stats,
            )
        if d.status in ('submitted', 'review'):
            for p in Profile.objects.filter(role=MANAGER, unit=d.staff.unit_id, user__is_active=True).select_related('user'):
                _create_reminder(
                    p.user, 'Deliverable awaiting verification',
                    f'{d.staff} · {d.type} · {d.period}.',
                    'approval', f'/deliverables/{d.pk}/',
                    f'deliv-{d.pk}-verify-{d.submission_count}-{p.user_id}', dry_run, stats,
                )
        if d.status == 'verified':
            for p in Profile.objects.filter(role=SUPERVISOR, user__is_active=True).select_related('user'):
                _create_reminder(
                    p.user, 'Deliverable awaiting final approval',
                    f'{d.staff} · {d.type} · {d.period}.',
                    'approval', f'/deliverables/{d.pk}/',
                    f'deliv-{d.pk}-approve-{p.user_id}', dry_run, stats,
                )

    horizon = today + timedelta(days=90)
    for staff in StaffRecord.objects.filter(active=True, prc_expiry__isnull=False, prc_expiry__lte=horizon).select_related('user', 'unit'):
        days = (staff.prc_expiry - today).days
        if days > 60:
            continue
        _create_reminder(
            staff.user, 'PRC license expiring'
            if days >= 0 else 'PRC license expired',
            f'PRC license expires on {staff.prc_expiry}.',
            'license', f'/staff/{staff.pk}/',
            f'prc-{staff.pk}-{staff.prc_expiry}-60', dry_run, stats,
        )
        for p in Profile.objects.filter(role=SUPERVISOR, user__is_active=True).select_related('user'):
            _create_reminder(
                p.user, 'Staff PRC license expiring',
                f'{staff} · PRC expires {staff.prc_expiry}.',
                'license', f'/staff/{staff.pk}/',
                f'prc-sup-{staff.pk}-{staff.prc_expiry}-{p.user_id}', dry_run, stats,
            )

    for task in Task.objects.filter(assignee__isnull=False).exclude(status__in=['completed', 'archived']).select_related('assignee'):
        days = (task.due_date - today).days
        stage = f'{days}d' if days in (7, 3, 1) else ('overdue' if days < 0 else None)
        if stage:
            _create_reminder(
                task.assignee, 'Task overdue' if stage == 'overdue' else 'Task due soon',
                f'{task.title} is due {task.due_date}.',
                'task', '/tasks/', f'task-{task.pk}-{stage}', dry_run, stats,
            )
    return stats
