from django.contrib import admin
from django.core.exceptions import PermissionDenied
from .models import Unit,Profile,StaffRecord,Deliverable,Training,Task,ShiftCount,AuditEvent
# Admin is restricted to trusted technical administrators (is_staff + permissions).
# Staff 201 sensitive fields are intentionally NOT exposed in this starter admin.
admin.site.register(Unit)
admin.site.register(Profile)
admin.site.register(Deliverable)
admin.site.register(Training)
admin.site.register(Task)
admin.site.register(ShiftCount)
# StaffRecord and AuditEvent intentionally not registered pending reviewed admin policy.
