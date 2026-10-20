from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
class Unit(models.Model):
 name=models.CharField(max_length=80,unique=True)
 def __str__(self):return self.name
class Profile(models.Model):
 ROLES=[('supervisor','Department Supervisor'),('manager','Unit Manager'),('staff','Nursing Staff')]
 user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='nursing_profile')
 role=models.CharField(max_length=12,choices=ROLES,default='staff')
 unit=models.ForeignKey(Unit,on_delete=models.PROTECT,null=True,blank=True)
 def __str__(self):return self.user.get_username()
class StaffRecord(models.Model):
 user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='staff_record')
 unit=models.ForeignKey(Unit,on_delete=models.PROTECT)
 position=models.CharField(max_length=100,blank=True)
 birthday=models.DateField(null=True,blank=True)
 contact_number=models.CharField(max_length=40,blank=True)
 address=models.TextField(blank=True)
 prc_number=models.CharField(max_length=80,blank=True)
 prc_expiry=models.DateField(null=True,blank=True)
 pna_membership=models.CharField(max_length=100,blank=True)
 ansap_membership=models.CharField(max_length=100,blank=True)
 active=models.BooleanField(default=True)
class Deliverable(models.Model):
 TYPES=[('DTR','DTR'),('DAR','DAR'),('IPCR','IPCR'),('OTHER','Other')]
 STATUSES=[('pending','Pending'),('submitted','Submitted'),('review','Under review'),('returned','Returned for correction'),('verified','Verified'),('approved','Approved')]
 staff=models.ForeignKey(StaffRecord,on_delete=models.PROTECT,related_name='deliverables')
 type=models.CharField(max_length=8,choices=TYPES)
 period=models.CharField(max_length=60)
 due_date=models.DateField()
 status=models.CharField(max_length=12,choices=STATUSES,default='pending')
 submitted_at=models.DateTimeField(null=True,blank=True)
 reviewed_at=models.DateTimeField(null=True,blank=True)
 reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='reviewed_deliverables')
 remarks=models.TextField(blank=True)
 document_reference=models.CharField(max_length=250,blank=True,help_text='Opaque ID in approved private document store; never a public URL')
 class Meta: constraints=[models.UniqueConstraint(fields=['staff','type','period'],name='unique_staff_requirement_period')]
class Training(models.Model):
 staff=models.ForeignKey(StaffRecord,on_delete=models.PROTECT,related_name='training')
 title=models.CharField(max_length=250)
 date=models.DateField()
 hours=models.DecimalField(max_digits=6,decimal_places=1,default=0)
 provider=models.CharField(max_length=150,blank=True)
 status=models.CharField(max_length=20,choices=[('planned','Planned'),('attended','Attended'),('completed','Completed')],default='planned')
 certificate_reference=models.CharField(max_length=250,blank=True)
class Task(models.Model):
  title=models.CharField(max_length=250)
  description=models.TextField(blank=True)
  unit=models.ForeignKey(Unit,on_delete=models.PROTECT,null=True,blank=True)
  assignee=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
  due_date=models.DateField()
  priority=models.CharField(max_length=10,choices=[('normal','Normal'),('high','High'),('critical','Critical')],default='normal')
  status=models.CharField(max_length=15,choices=[('pending','Pending'),('progress','In progress'),('completed','Completed'),('archived','Archived')],default='pending')
  created_at=models.DateTimeField(default=timezone.now)
  updated_at=models.DateTimeField(auto_now=True)
class ShiftCount(models.Model):
 unit=models.ForeignKey(Unit,on_delete=models.PROTECT)
 date=models.DateField()
 shift=models.CharField(max_length=10,choices=[('day','Day'),('night','Night')])
 on_duty=models.PositiveSmallIntegerField()
 entered_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 class Meta:constraints=[models.UniqueConstraint(fields=['unit','date','shift'],name='unique_unit_date_shift')]
class AuditEvent(models.Model):
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 event=models.CharField(max_length=80)
 object_type=models.CharField(max_length=80)
 object_id=models.PositiveBigIntegerField()
 occurred_at=models.DateTimeField(auto_now_add=True)
 detail=models.JSONField(default=dict,blank=True)
