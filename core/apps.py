from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    try:
        from .services import log_audit
        log_audit(user, 'login', object_type='User', object_id=user.pk,
                  target_label=user.get_username(), request=request)
    except Exception:
        # Never block authentication if audit storage is unavailable.
        pass


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    if not user:
        return
    try:
        from .services import log_audit
        log_audit(user, 'logout', object_type='User', object_id=user.pk,
                  target_label=user.get_username(), request=request)
    except Exception:
        pass


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
