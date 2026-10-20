"""Central server-side authorization helpers.

Every view, JSON endpoint and data mutation must use these helpers instead of
trusting hidden buttons or client-side state.
"""
from functools import wraps

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from .models import Category, Deliverable, Profile, ShiftCount, StaffRecord, Task, Training, Unit

SUPERVISOR = 'supervisor'
MANAGER = 'manager'
STAFF = 'staff'
ROLES = (SUPERVISOR, MANAGER, STAFF)


def profile(user):
    try:
        return user.nursing_profile
    except Profile.DoesNotExist:
        raise PermissionDenied('Account has no approved nursing role')


def role(user):
    return profile(user).role


def user_unit_id(user):
    p = profile(user)
    return p.unit_id


def is_supervisor(user):
    return role(user) == SUPERVISOR


def is_manager(user):
    return role(user) == MANAGER


def is_staff(user):
    return role(user) == STAFF


def role_required(*roles):
    """Decorator for HTML views. Compose with @login_required."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied('Authentication required')
            if role(request.user) not in roles:
                raise PermissionDenied('You do not have permission to perform this action')
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


# ---------- Units and configuration ----------
def permitted_units(user):
    p = profile(user)
    if p.role == SUPERVISOR:
        return Unit.objects.all()
    if p.unit_id:
        return Unit.objects.filter(pk=p.unit_id)
    return Unit.objects.none()


def unit_in_scope(user, unit_id):
    if not unit_id:
        return False
    return permitted_units(user).filter(pk=unit_id).exists()


def can_manage_config(user):
    return role(user) == SUPERVISOR


def can_manage_users(user):
    return role(user) == SUPERVISOR


def can_view_audit(user):
    return role(user) == SUPERVISOR


def permitted_categories(user):
    if role(user) == SUPERVISOR:
        return Category.objects.all()
    return Category.objects.filter(active=True)


# ---------- Staff 201 ----------
def permitted_staff(user):
    p = profile(user)
    if p.role == SUPERVISOR:
        return StaffRecord.objects.all()
    if p.role == MANAGER and p.unit_id:
        return StaffRecord.objects.filter(unit_id=p.unit_id)
    return StaffRecord.objects.filter(user=user)


def can_view_staff(user, staff):
    return permitted_staff(user).filter(pk=staff.pk).exists()


def can_view_sensitive_staff(user, staff):
    p = profile(user)
    return p.role == SUPERVISOR or staff.user_id == user.id


def can_edit_staff(user, staff):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    if staff.user_id == user.id:
        return True
    return p.role == MANAGER and p.unit_id and staff.unit_id == p.unit_id


def can_create_staff(user):
    return role(user) == SUPERVISOR


def can_toggle_staff(user, staff):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    return p.role == MANAGER and p.unit_id and staff.unit_id == p.unit_id


# ---------- Tasks / records ----------
def permitted_tasks(user):
    p = profile(user)
    if p.role == SUPERVISOR:
        return Task.objects.all()
    if p.role == MANAGER and p.unit_id:
        return Task.objects.filter(unit_id=p.unit_id)
    return Task.objects.filter(assignee=user)


def can_edit_task(user, task):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    if p.role == MANAGER and p.unit_id and task.unit_id == p.unit_id:
        return True
    return p.role == STAFF and task.assignee_id == user.id


def can_delete_task(user, task):
    return role(user) == SUPERVISOR


def can_archive_task(user, task):
    p = profile(user)
    return p.role == SUPERVISOR or (
        p.role == MANAGER and p.unit_id and task.unit_id == p.unit_id
    )


def can_change_task_status(user, task):
    if not can_edit_task(user, task):
        return False
    p = profile(user)
    if p.role == STAFF:
        return task.assignee_id == user.id and task.status != 'archived'
    return True


def task_assignable_users(user, unit=None):
    p = profile(user)
    if p.role == SUPERVISOR:
        qs = User.objects.filter(nursing_profile__isnull=False, is_active=True)
        if unit:
            qs = qs.filter(nursing_profile__unit_id=unit)
        return qs.order_by('first_name', 'last_name', 'username')
    if p.role == MANAGER and p.unit_id:
        qs_unit = unit if unit else p.unit_id
        if str(qs_unit) != str(p.unit_id):
            return User.objects.none()
        return User.objects.filter(nursing_profile__unit_id=p.unit_id, is_active=True).order_by('first_name', 'last_name', 'username')
    return User.objects.none()


# ---------- Deliverables ----------
def permitted_deliverables(user):
    p = profile(user)
    if p.role == SUPERVISOR:
        return Deliverable.objects.all()
    if p.role == MANAGER and p.unit_id:
        return Deliverable.objects.filter(staff__unit_id=p.unit_id)
    return Deliverable.objects.filter(staff__user=user)


def can_manage_deliverable(user, deliverable):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    return p.role == MANAGER and p.unit_id and deliverable.staff.unit_id == p.unit_id


def can_review_deliverable(user, deliverable):
    return can_manage_deliverable(user, deliverable)


def can_approve_deliverable(user, deliverable):
    return role(user) == SUPERVISOR


def can_submit_deliverable(user, deliverable):
    return deliverable.staff.user_id == user.id and deliverable.status in ('pending', 'returned')


# ---------- Training ----------
def permitted_training(user):
    p = profile(user)
    if p.role == SUPERVISOR:
        return Training.objects.all()
    if p.role == MANAGER and p.unit_id:
        return Training.objects.filter(staff__unit_id=p.unit_id)
    return Training.objects.filter(staff__user=user)


def can_validate_training(user, training):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    return p.role == MANAGER and p.unit_id and training.staff.unit_id == p.unit_id


def can_edit_training(user, training):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    if p.role == MANAGER and p.unit_id and training.staff.unit_id == p.unit_id:
        return True
    return training.staff.user_id == user.id and training.validation_status in ('pending', 'returned')


def can_archive_training(user, training):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    return p.role == MANAGER and p.unit_id and training.staff.unit_id == p.unit_id


def can_delete_training(user, training):
    return role(user) == SUPERVISOR


# ---------- Shifts ----------
def permitted_shifts(user):
    p = profile(user)
    if p.role == SUPERVISOR:
        return ShiftCount.objects.all()
    if p.role == MANAGER and p.unit_id:
        return ShiftCount.objects.filter(unit_id=p.unit_id)
    return ShiftCount.objects.none()


def can_manage_shift(user, shift=None):
    p = profile(user)
    if p.role == SUPERVISOR:
        return True
    if p.role == MANAGER and p.unit_id:
        return shift is None or shift.unit_id == p.unit_id
    return False
