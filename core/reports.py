from datetime import timedelta

from django.utils import timezone

from .access import (
    can_view_sensitive_staff,
    permitted_deliverables,
    permitted_shifts,
    permitted_staff,
    permitted_tasks,
    permitted_training,
    profile,
)
from .forms import ReportFilterForm
from .models import Deliverable, StaffRecord, Task, Training


def filter_form(actor, data=None):
    form = ReportFilterForm(actor, data=data or None)
    form.is_valid()
    return form


def _base_filters(cleaned):
    return {
        'start': cleaned.get('start'),
        'end': cleaned.get('end'),
        'unit': cleaned.get('unit'),
        'staff': cleaned.get('staff'),
        'status': cleaned.get('status') or '',
        'type': cleaned.get('type') or '',
        'q': (cleaned.get('q') or '').strip(),
        'horizon': cleaned.get('horizon') or 90,
    }


def build_report(actor, cleaned):
    f = _base_filters(cleaned)
    kind = cleaned.get('kind') or 'compliance'
    if kind == 'training':
        return _training(actor, f)
    if kind == 'licenses':
        return _licenses(actor, f)
    if kind == 'shifts':
        return _shifts(actor, f)
    if kind == 'tasks':
        return _tasks(actor, f)
    return _compliance(actor, f)


def _compliance(actor, f):
    qs = permitted_deliverables(actor).select_related('staff__user', 'staff__unit')
    if f['start']:
        qs = qs.filter(due_date__gte=f['start'])
    if f['end']:
        qs = qs.filter(due_date__lte=f['end'])
    if f['unit']:
        qs = qs.filter(staff__unit=f['unit'])
    if f['staff']:
        qs = qs.filter(staff=f['staff'])
    if f['status']:
        qs = qs.filter(status=f['status'])
    if f['type']:
        qs = qs.filter(type=f['type'])
    if f['q']:
        from django.db.models import Q
        qs = qs.filter(
            Q(staff__user__username__icontains=f['q'])
            | Q(staff__user__first_name__icontains=f['q'])
            | Q(staff__user__last_name__icontains=f['q'])
            | Q(period__icontains=f['q'])
        )
    qs = qs.order_by('due_date', 'staff__user__username')[:5000]
    today = timezone.localdate()
    rows = []
    counts = {key: 0 for key, _ in Deliverable.STATUSES}
    on_time = 0
    for d in qs:
        counts[d.status] = counts.get(d.status, 0) + 1
        if d.submitted_at and d.submitted_at.date() <= d.due_date:
            on_time += 1
        rows.append([
            str(d.staff), d.staff.unit.name, d.type, d.period, d.due_date,
            d.get_status_display(),
            d.submitted_at.date() if d.submitted_at else '',
            'Yes' if (d.due_date < today and d.status not in ('verified', 'approved')) else 'No',
        ])
    total = len(rows)
    closed = counts.get('verified', 0) + counts.get('approved', 0)
    summary = [
        ('Requirements', total),
        ('Approved', counts.get('approved', 0)),
        ('Verified', counts.get('verified', 0)),
        ('Open', total - closed),
        ('Overdue', sum(1 for r in rows if r[-1] == 'Yes')),
        ('On-time submissions', on_time),
        ('Completion rate', f'{(closed / total * 100):.1f}%' if total else '—'),
    ]
    return {
        'kind': 'compliance', 'title': 'Deliverable compliance',
        'columns': ['Staff', 'Unit', 'Type', 'Period', 'Due date', 'Status', 'Submitted', 'Overdue'],
        'rows': rows, 'summary': summary,
        'empty': 'No deliverables match the selected filters.',
    }


def _training(actor, f):
    qs = permitted_training(actor).select_related('staff__user', 'staff__unit')
    if f['start']:
        qs = qs.filter(date__gte=f['start'])
    if f['end']:
        qs = qs.filter(date__lte=f['end'])
    if f['unit']:
        qs = qs.filter(staff__unit=f['unit'])
    if f['staff']:
        qs = qs.filter(staff=f['staff'])
    if f['q']:
        from django.db.models import Q
        qs = qs.filter(
            Q(title__icontains=f['q']) | Q(provider__icontains=f['q'])
            | Q(staff__user__username__icontains=f['q'])
        )
    qs = qs.order_by('-date')[:5000]
    rows = []
    total_hours = 0
    validated = pending = returned = 0
    for t in qs:
        total_hours += float(t.hours or 0)
        if t.validation_status == 'validated':
            validated += 1
        elif t.validation_status == 'pending':
            pending += 1
        else:
            returned += 1
        rows.append([
            str(t.staff), t.staff.unit.name, t.title, t.date, t.hours,
            t.get_status_display(), t.get_validation_status_display(), t.provider,
        ])
    summary = [
        ('Training records', len(rows)),
        ('Total hours', f'{total_hours:.1f}'),
        ('Validated', validated),
        ('Pending validation', pending),
        ('Returned', returned),
    ]
    return {
        'kind': 'training', 'title': 'Training completion',
        'columns': ['Staff', 'Unit', 'Title', 'Date', 'Hours', 'Attendance', 'Validation', 'Provider'],
        'rows': rows, 'summary': summary,
        'empty': 'No training records match the selected filters.',
    }


def _licenses(actor, f):
    horizon = f['horizon'] or 90
    today = timezone.localdate()
    qs = permitted_staff(actor).filter(active=True, prc_expiry__isnull=False).select_related('user', 'unit')
    qs = qs.filter(prc_expiry__lte=today + timedelta(days=horizon))
    if f['start']:
        qs = qs.filter(prc_expiry__gte=f['start'])
    if f['end']:
        qs = qs.filter(prc_expiry__lte=f['end'])
    if f['unit']:
        qs = qs.filter(unit=f['unit'])
    if f['staff']:
        qs = qs.filter(pk=f['staff'].pk)
    if f['q']:
        from django.db.models import Q
        qs = qs.filter(
            Q(user__username__icontains=f['q']) | Q(user__first_name__icontains=f['q'])
            | Q(user__last_name__icontains=f['q']) | Q(prc_number__icontains=f['q'])
        )
    qs = qs.order_by('prc_expiry')
    rows = []
    expired = soon = 0
    for s in qs:
        days = (s.prc_expiry - today).days
        if days < 0:
            expired += 1
        elif days <= 30:
            soon += 1
        contact = s.contact_number if can_view_sensitive_staff(actor, s) else 'Restricted'
        rows.append([
            str(s), s.unit.name, s.employee_number or '', s.prc_number,
            s.prc_expiry, days, contact,
        ])
    summary = [
        ('Licenses in horizon', len(rows)),
        ('Expired', expired),
        ('Expiring within 30 days', soon),
        ('Horizon (days)', horizon),
    ]
    return {
        'kind': 'licenses', 'title': 'Expiring PRC licenses',
        'columns': ['Staff', 'Unit', 'Employee no.', 'PRC no.', 'Expiry', 'Days remaining', 'Contact'],
        'rows': rows, 'summary': summary,
        'empty': 'No PRC licenses expire within this horizon.',
    }


def _shifts(actor, f):
    qs = permitted_shifts(actor).select_related('unit', 'entered_by')
    if f['start']:
        qs = qs.filter(date__gte=f['start'])
    if f['end']:
        qs = qs.filter(date__lte=f['end'])
    if f['unit']:
        qs = qs.filter(unit=f['unit'])
    if f['q']:
        qs = qs.filter(unit__name__icontains=f['q'])
    qs = qs.order_by('-date', 'unit__name', 'shift')[:5000]
    rows = []
    day_total = night_total = 0
    for s in qs:
        if s.shift == 'day':
            day_total += s.on_duty
        else:
            night_total += s.on_duty
        rows.append([s.unit.name, s.date, s.get_shift_display(), s.on_duty, s.entered_by.username])
    summary = [
        ('Shift entries', len(rows)),
        ('Day on-duty total', day_total),
        ('Night on-duty total', night_total),
        ('Combined on-duty', day_total + night_total),
    ]
    return {
        'kind': 'shifts', 'title': 'Shift counts',
        'columns': ['Unit', 'Date', 'Shift', 'On duty', 'Entered by'],
        'rows': rows, 'summary': summary,
        'empty': 'No shift counts match the selected filters.',
    }


def _tasks(actor, f):
    qs = permitted_tasks(actor).select_related('unit', 'assignee')
    if f['start']:
        qs = qs.filter(due_date__gte=f['start'])
    if f['end']:
        qs = qs.filter(due_date__lte=f['end'])
    if f['unit']:
        qs = qs.filter(unit=f['unit'])
    if f['status']:
        qs = qs.filter(status=f['status'])
    if f['q']:
        from django.db.models import Q
        qs = qs.filter(Q(title__icontains=f['q']) | Q(description__icontains=f['q']))
    qs = qs.order_by('due_date')[:5000]
    today = timezone.localdate()
    rows = []
    overdue = 0
    for t in qs:
        is_overdue = t.due_date < today and t.status not in ('completed', 'archived')
        if is_overdue:
            overdue += 1
        rows.append([
            t.title, t.unit.name if t.unit else '', t.assignee.username if t.assignee else '',
            t.due_date, t.get_priority_display(), t.get_status_display(),
            'Yes' if is_overdue else 'No',
        ])
    summary = [
        ('Tasks', len(rows)),
        ('Overdue', overdue),
        ('Open', sum(1 for t in qs if t.status not in ('completed', 'archived'))),
        ('Completed', sum(1 for t in qs if t.status == 'completed')),
    ]
    return {
        'kind': 'tasks', 'title': 'Tasks and overdue items',
        'columns': ['Task', 'Unit', 'Assignee', 'Due date', 'Priority', 'Status', 'Overdue'],
        'rows': rows, 'summary': summary,
        'empty': 'No tasks match the selected filters.',
    }


def report_filename(kind, extension):
    return f'pndmis-{kind}-{timezone.localdate().isoformat()}.{extension}'
