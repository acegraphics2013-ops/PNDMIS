from datetime import timedelta
import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .access import profile, permitted_staff, can_review
from .models import Deliverable, Training, Task, ShiftCount, AuditEvent, StaffRecord, Unit, Profile
from .forms import SubmissionForm, ReviewForm, TrainingForm, TaskForm, ShiftForm


def audit(user, event, obj, detail=None):
    AuditEvent.objects.create(actor=user, event=event, object_type=type(obj).__name__, object_id=obj.pk, detail=detail or {})


def permitted_tasks(user):
    p = profile(user)
    if p.role == 'supervisor':
        return Task.objects.all()
    if p.role == 'manager':
        return Task.objects.filter(Q(assignee=user) | Q(unit=p.unit))
    return Task.objects.filter(assignee=user)


def task_to_dict(t):
    return {
        'id': t.pk,
        'name': t.title,
        'description': t.description or '',
        'category': t.unit.name if t.unit_id else '—',
        'category_id': t.unit_id,
        'status': t.status,
        'status_display': t.get_status_display(),
        'priority': t.priority,
        'due_date': t.due_date.isoformat() if t.due_date else None,
        'created': t.created_at.isoformat() if getattr(t, 'created_at', None) else None,
        'assignee': t.assignee.username if t.assignee_id else '—',
    }


# ---------- Pages ----------
@login_required
def dashboard(request):
    p = profile(request.user)
    staff = permitted_staff(request.user)
    today = timezone.localdate()
    soon = today + timedelta(days=7)
    qs = Deliverable.objects.filter(staff__in=staff)
    open_qs = qs.exclude(status__in=['verified', 'approved'])
    tasks = permitted_tasks(request.user)
    staff_per_unit = staff.filter(active=True).values('unit__name').annotate(count=Count('id')).order_by('unit__name')
    if p.role == 'supervisor':
        shift_today = ShiftCount.objects.filter(date=today).select_related('unit')
    elif p.role == 'manager':
        shift_today = ShiftCount.objects.filter(date=today, unit=p.unit).select_related('unit')
    else:
        shift_today = ShiftCount.objects.none()
    on_duty_total = shift_today.aggregate(total=Sum('on_duty'))['total'] or 0
    # SaaS stat cards mapped to real data
    total_records = tasks.count() + qs.count()
    active_records = staff.filter(active=True).count()
    pending_records = open_qs.count() + tasks.exclude(status__in=['completed', 'archived']).count()
    archived_records = tasks.filter(status='archived').count() + qs.filter(status='approved').count()
    recent_qs = AuditEvent.objects.select_related('actor').order_by('-occurred_at')
    if p.role == 'staff':
        recent_qs = recent_qs.filter(actor=request.user)
    recent = recent_qs[:10]
    return render(request, 'core/dashboard.html', {
        'role': p.get_role_display(), 'user_role': p.role,
        'ph_now': timezone.localtime(timezone.now()), 'today': today,
        'staff_count': staff.filter(active=True).count(), 'staff_per_unit': staff_per_unit,
        'shift_today': shift_today, 'on_duty_total': on_duty_total,
        'pending': open_qs.count(), 'overdue': open_qs.filter(due_date__lt=today).count(),
        'approaching': open_qs.filter(due_date__gte=today, due_date__lte=soon).order_by('due_date')[:15],
        'overdue_list': open_qs.filter(due_date__lt=today).order_by('due_date')[:15],
        'deliverables': qs.select_related('staff__user', 'staff__unit').order_by('due_date')[:30],
        'tasks': tasks.order_by('due_date')[:15],
        'tasks_overdue': tasks.filter(due_date__lt=today).exclude(status__in=['completed', 'archived']).count(),
        'tasks_due_soon': tasks.filter(due_date__gte=today, due_date__lte=soon).exclude(status__in=['completed', 'archived']).count(),
        'total_records': total_records, 'active_records': active_records,
        'pending_records': pending_records, 'archived_records': archived_records,
        'recent_activity': recent,
        'page_title': 'Dashboard', 'breadcrumb': 'Home / Dashboard',
    })


@login_required
def records_page(request):
    p = profile(request.user)
    units = Unit.objects.all().order_by('name') if p.role == 'supervisor' else Unit.objects.filter(pk=p.unit_id) if p.unit_id else Unit.objects.none()
    return render(request, 'core/records.html', {
        'page_title': 'Records Management', 'breadcrumb': 'Home / Records',
        'units': units, 'can_write': p.role in ['supervisor', 'manager'], 'user_role': p.role,
    })


@login_required
def categories_page(request):
    p = profile(request.user)
    units = Unit.objects.annotate(
        staff_count=Count('staffrecord', distinct=True),
        task_count=Count('task', distinct=True),
    ).order_by('name')
    type_counts = list(Deliverable.objects.filter(staff__in=permitted_staff(request.user)).values('type').annotate(count=Count('id')).order_by('type'))
    return render(request, 'core/categories.html', {
        'page_title': 'Categories', 'breadcrumb': 'Home / Categories',
        'units': units, 'type_counts': type_counts, 'user_role': p.role,
        'can_write': p.role == 'supervisor',
    })


@login_required
def reports_page(request):
    return render(request, 'core/reports.html', {'page_title': 'Reports & Analytics', 'breadcrumb': 'Home / Reports'})


@login_required
def users_page(request):
    p = profile(request.user)
    if p.role != 'supervisor':
        raise PermissionDenied('Supervisor only')
    users = Profile.objects.select_related('user', 'unit').order_by('role', 'user__username')
    return render(request, 'core/users.html', {'page_title': 'User Management', 'breadcrumb': 'Home / Users', 'profiles': users})


@login_required
def settings_page(request):
    p = profile(request.user)
    return render(request, 'core/settings.html', {'page_title': 'Settings', 'breadcrumb': 'Home / Settings', 'my_profile': p})


# ---------- REST API (JSON, CSRF-protected, RBAC) ----------
def _api_login_required(view):
    def w(request, *a, **kw):
        if not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'Authentication required'}, status=401)
        try:
            profile(request.user)
        except PermissionDenied as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=403)
        return view(request, *a, **kw)
    return w


@_api_login_required
def api_stats(request):
    staff = permitted_staff(request.user)
    today = timezone.localdate()
    qs = Deliverable.objects.filter(staff__in=staff)
    tasks = permitted_tasks(request.user)
    data = {
        'ok': True,
        'total_records': tasks.count() + qs.count(),
        'active_records': staff.filter(active=True).count(),
        'pending_records': qs.exclude(status__in=['verified', 'approved']).count() + tasks.exclude(status__in=['completed', 'archived']).count(),
        'archived_records': tasks.filter(status='archived').count() + qs.filter(status='approved').count(),
        'overdue': qs.filter(due_date__lt=today).exclude(status__in=['verified', 'approved']).count(),
    }
    return JsonResponse(data)


@_api_login_required
def api_analytics(request):
    staff = permitted_staff(request.user)
    by_status = list(Deliverable.objects.filter(staff__in=staff).values('status').annotate(count=Count('id')).order_by('status'))
    by_unit = list(staff.filter(active=True).values('unit__name').annotate(count=Count('id')).order_by('unit__name'))
    by_priority = list(permitted_tasks(request.user).values('priority').annotate(count=Count('id')).order_by('priority'))
    return JsonResponse({'ok': True, 'by_status': by_status, 'by_unit': by_unit, 'by_priority': by_priority})


@_api_login_required
@require_http_methods(['GET', 'POST'])
def api_records(request):
    if request.method == 'GET':
        qs = permitted_tasks(request.user).select_related('unit', 'assignee')
        q = (request.GET.get('search') or '').strip()
        cat = request.GET.get('category') or ''
        status = request.GET.get('status') or ''
        sort = request.GET.get('sort') or '-created_at'
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if cat.isdigit():
            qs = qs.filter(unit_id=int(cat))
        if status in ['pending', 'progress', 'completed', 'archived']:
            qs = qs.filter(status=status)
        allowed_sorts = {'name': 'title', '-name': '-title', 'date': 'due_date', '-date': '-due_date', 'created_at': 'created_at', '-created_at': '-created_at', 'status': 'status', '-status': '-status'}
        qs = qs.order_by(allowed_sorts.get(sort, '-created_at'))
        try:
            page = max(1, int(request.GET.get('page', '1')))
        except ValueError:
            page = 1
        pag = Paginator(qs, 10)
        pg = pag.get_page(page)
        return JsonResponse({'ok': True, 'results': [task_to_dict(t) for t in pg.object_list], 'page': pg.number, 'pages': pag.num_pages, 'total': pag.count})
    # POST create
    p = profile(request.user)
    if p.role not in ['supervisor', 'manager']:
        return JsonResponse({'ok': False, 'error': 'Only supervisor/manager can create'}, status=403)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    form = TaskForm(payload)
    if p.role == 'manager':
        form.fields['unit'].queryset = Unit.objects.filter(pk=p.unit_id)
        # force unit scope
        if str(payload.get('unit') or '') and int(payload.get('unit')) != p.unit_id:
            return JsonResponse({'ok': False, 'error': 'Managers can only file under their own unit', 'errors': {'unit': ['Out of scope']}}, status=403)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Validation failed', 'errors': form.errors}, status=400)
    with transaction.atomic():
        obj = form.save()
        audit(request.user, 'task_created', obj)
    return JsonResponse({'ok': True, 'record': task_to_dict(obj)}, status=201)


@_api_login_required
@require_http_methods(['GET', 'PUT', 'DELETE'])
def api_record_detail(request, pk):
    obj = get_object_or_404(Task.objects.select_related('unit', 'assignee'), pk=pk)
    p = profile(request.user)
    in_scope = permitted_tasks(request.user).filter(pk=obj.pk).exists()
    if not in_scope:
        return JsonResponse({'ok': False, 'error': 'Not found or no access'}, status=404)
    if request.method == 'GET':
        return JsonResponse({'ok': True, 'record': task_to_dict(obj)})
    can_write = p.role == 'supervisor' or (p.role == 'manager' and p.unit_id and obj.unit_id == p.unit_id) or obj.assignee_id == request.user.id
    if not can_write:
        return JsonResponse({'ok': False, 'error': 'Forbidden'}, status=403)
    if request.method == 'DELETE':
        if p.role not in ['supervisor', 'manager']:
            return JsonResponse({'ok': False, 'error': 'Only supervisor/manager can delete'}, status=403)
        oid = obj.pk
        with transaction.atomic():
            obj.delete()
            # audit needs an object; log with stub
            AuditEvent.objects.create(actor=request.user, event='task_deleted', object_type='Task', object_id=oid, detail={})
        return JsonResponse({'ok': True, 'deleted': oid})
    # PUT update
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    # staff assignee may only change status; enforce
    if p.role == 'staff':
        allowed = {'status': payload.get('status')}
        payload = {'title': obj.title, 'description': obj.description, 'unit': obj.unit_id, 'assignee': obj.assignee_id, 'due_date': obj.due_date.isoformat(), 'priority': obj.priority, 'status': allowed['status']}
    form = TaskForm(payload, instance=obj)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Validation failed', 'errors': form.errors}, status=400)
    with transaction.atomic():
        obj = form.save()
        audit(request.user, 'task_updated', obj)
    return JsonResponse({'ok': True, 'record': task_to_dict(obj)})


# ---------- Existing module views (kept) ----------
@login_required
def submit(request, pk):
    d = get_object_or_404(Deliverable.objects.select_related('staff'), pk=pk)
    if d.staff.user_id != request.user.id:
        raise PermissionDenied
    if d.status not in ['pending', 'returned']:
        raise PermissionDenied('Not open for submission')
    form = SubmissionForm(request.POST or None, instance=d)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            d = form.save(commit=False); d.status = 'submitted'; d.submitted_at = timezone.now(); d.save()
            audit(request.user, 'deliverable_submitted', d)
        return redirect('deliverables')
    return render(request, 'core/form.html', {'form': form, 'heading': 'Submit ' + d.type, 'page_title': 'Submit', 'breadcrumb': 'Home / Deliverables / Submit'})


@login_required
def review(request, pk):
    d = get_object_or_404(Deliverable.objects.select_related('staff'), pk=pk)
    if not can_review(request.user, d.staff):
        raise PermissionDenied
    if d.status not in ['submitted', 'review', 'verified']:
        raise PermissionDenied('Not ready for review')
    form = ReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        decision = form.cleaned_data['decision']
        if decision == 'approved' and profile(request.user).role != 'supervisor':
            raise PermissionDenied('Supervisor approval required')
        with transaction.atomic():
            d.status = decision; d.remarks = form.cleaned_data['remarks']; d.reviewer = request.user; d.reviewed_at = timezone.now(); d.save()
            audit(request.user, 'deliverable_' + decision, d)
        return redirect('deliverables')
    return render(request, 'core/form.html', {'form': form, 'heading': 'Review ' + d.type, 'page_title': 'Review', 'breadcrumb': 'Home / Deliverables / Review'})


@login_required
def deliverables(request):
    p = profile(request.user)
    staff = permitted_staff(request.user)
    qs = Deliverable.objects.filter(staff__in=staff).select_related('staff__user', 'staff__unit')
    f_type = request.GET.get('type', ''); f_status = request.GET.get('status', ''); f_overdue = request.GET.get('overdue', '')
    today = timezone.localdate()
    if f_type in ['DTR', 'DAR', 'IPCR', 'OTHER']:
        qs = qs.filter(type=f_type)
    if f_status in ['pending', 'submitted', 'review', 'returned', 'verified', 'approved']:
        qs = qs.filter(status=f_status)
    if f_overdue == '1':
        qs = qs.filter(due_date__lt=today).exclude(status__in=['verified', 'approved'])
    qs = qs.order_by('due_date')
    rows = [(d, d.due_date < today and d.status not in ['verified', 'approved']) for d in qs[:200]]
    return render(request, 'core/deliverables.html', {'rows': rows, 'f_type': f_type, 'f_status': f_status, 'f_overdue': f_overdue, 'user_role': p.role, 'today': today, 'page_title': 'Deliverables', 'breadcrumb': 'Home / Deliverables'})


@login_required
def staff_directory(request):
    p = profile(request.user)
    staff = permitted_staff(request.user).select_related('user', 'unit')
    return render(request, 'core/staff.html', {'staff': staff, 'user_role': p.role, 'page_title': '201 Files', 'breadcrumb': 'Home / 201 Files'})


@login_required
def staff_detail(request, pk):
    p = profile(request.user)
    obj = get_object_or_404(StaffRecord.objects.select_related('user', 'unit'), pk=pk)
    if not permitted_staff(request.user).filter(pk=obj.pk).exists():
        raise PermissionDenied
    show_sensitive = (p.role == 'supervisor') or (obj.user_id == request.user.id)
    return render(request, 'core/staff_detail.html', {
        's': obj, 'user_role': p.role, 'show_sensitive': show_sensitive,
        'trainings': obj.training.order_by('-date')[:20], 'deliverables': obj.deliverables.order_by('due_date')[:30],
        'page_title': '201 File Detail', 'breadcrumb': 'Home / 201 Files / Detail'})


@login_required
def training(request):
    staff = permitted_staff(request.user)
    qs = Training.objects.filter(staff__in=staff).select_related('staff__user', 'staff__unit').order_by('-date')
    return render(request, 'core/training.html', {'training': qs[:200], 'total_hours': qs.aggregate(total=Sum('hours'))['total'] or 0, 'page_title': 'LDNI / Training', 'breadcrumb': 'Home / Training'})


@login_required
def add_training(request):
    p = profile(request.user)
    if p.role != 'staff':
        raise PermissionDenied('Staff enter their own training')
    staff = get_object_or_404(permitted_staff(request.user), user=request.user)
    form = TrainingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False); obj.staff = staff; obj.save()
        audit(request.user, 'training_created', obj)
        return redirect('training')
    return render(request, 'core/form.html', {'form': form, 'heading': 'Record my training', 'page_title': 'Add Training', 'breadcrumb': 'Home / Training / Add'})


@login_required
def tasks_view(request):
    p = profile(request.user)
    qs = permitted_tasks(request.user).select_related('unit')
    f = request.GET.get('filter', 'all')
    today = timezone.localdate(); soon = today + timedelta(days=7)
    if f == 'overdue':
        qs = qs.filter(due_date__lt=today).exclude(status__in=['completed', 'archived'])
    elif f == 'soon':
        qs = qs.filter(due_date__gte=today, due_date__lte=soon).exclude(status__in=['completed', 'archived'])
    elif f == 'open':
        qs = qs.exclude(status__in=['completed', 'archived'])
    rows = []
    for t in qs.order_by('due_date')[:200]:
        flag = 'done' if t.status in ['completed', 'archived'] else 'overdue' if t.due_date < today else 'soon' if t.due_date <= soon else 'ok'
        rows.append((t, flag))
    return render(request, 'core/tasks.html', {'rows': rows, 'f': f, 'today': today, 'can_add': p.role in ['supervisor', 'manager'], 'user_role': p.role, 'page_title': 'Deadlines', 'breadcrumb': 'Home / Deadlines'})


@login_required
def add_task(request):
    p = profile(request.user)
    if p.role not in ['supervisor', 'manager']:
        raise PermissionDenied('Only supervisor/manager assign tasks')
    form = TaskForm(request.POST or None)
    if p.role == 'manager':
        form.fields['unit'].queryset = Unit.objects.filter(pk=p.unit_id)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(); audit(request.user, 'task_created', obj)
        return redirect('tasks')
    return render(request, 'core/form.html', {'form': form, 'heading': 'Assign task / deadline', 'page_title': 'Assign Task', 'breadcrumb': 'Home / Deadlines / Add'})


@login_required
def task_status(request, pk):
    p = profile(request.user)
    t = get_object_or_404(Task, pk=pk)
    allowed = p.role == 'supervisor' or (p.role == 'manager' and p.unit_id and t.unit_id == p.unit_id) or (t.assignee_id == request.user.id)
    if not allowed:
        raise PermissionDenied
    if request.method == 'POST':
        ns = request.POST.get('status', '')
        if ns in ['pending', 'progress', 'completed', 'archived']:
            t.status = ns; t.save(); audit(request.user, 'task_' + ns, t)
        return redirect('tasks')
    return redirect('tasks')


@login_required
def shifts(request):
    p = profile(request.user)
    if p.role == 'staff':
        raise PermissionDenied
    qs = ShiftCount.objects.all() if p.role == 'supervisor' else ShiftCount.objects.filter(unit=p.unit)
    return render(request, 'core/shifts.html', {'shifts': qs.select_related('unit').order_by('-date')[:100], 'page_title': 'Shifts', 'breadcrumb': 'Home / Shifts'})


@login_required
def add_shift(request):
    p = profile(request.user)
    if p.role == 'staff':
        raise PermissionDenied
    form = ShiftForm(request.POST or None)
    if p.role == 'manager':
        form.fields['unit'].queryset = form.fields['unit'].queryset.filter(pk=p.unit_id)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False); obj.entered_by = request.user; obj.save()
        audit(request.user, 'shift_created', obj)
        return redirect('shifts')
    return render(request, 'core/form.html', {'form': form, 'heading': 'Enter shift count', 'page_title': 'Add Shift', 'breadcrumb': 'Home / Shifts / Add'})
