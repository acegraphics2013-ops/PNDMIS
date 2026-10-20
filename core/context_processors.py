from .models import Notification, Profile


def navigation(request):
    if not request.user.is_authenticated:
        return {'nav_profile': None, 'unread_notifications': 0, 'user_role': ''}
    try:
        p = request.user.nursing_profile
    except Profile.DoesNotExist:
        return {'nav_profile': None, 'unread_notifications': 0, 'user_role': ''}
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return {
        'nav_profile': p,
        'user_role': p.role,
        'unread_notifications': unread,
        'can_manage_users': p.role == 'supervisor',
        'can_manage_config': p.role == 'supervisor',
        'can_view_audit': p.role == 'supervisor',
        'can_manage_shifts': p.role in ('supervisor', 'manager'),
    }
