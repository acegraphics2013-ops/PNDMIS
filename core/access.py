from django.core.exceptions import PermissionDenied
from .models import Profile

def profile(user):
 try:return user.nursing_profile
 except Profile.DoesNotExist:raise PermissionDenied('Account has no approved nursing role')

def permitted_staff(user):
 from .models import StaffRecord
 p=profile(user)
 if p.role=='supervisor':return StaffRecord.objects.all()
 if p.role=='manager' and p.unit_id:return StaffRecord.objects.filter(unit_id=p.unit_id)
 return StaffRecord.objects.filter(user=user)

def can_review(user,staff):
 p=profile(user)
 return p.role=='supervisor' or (p.role=='manager' and p.unit_id==staff.unit_id)
