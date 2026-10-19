from django import forms
from .models import Deliverable,Training,Task,ShiftCount
class SubmissionForm(forms.ModelForm):
 class Meta: model=Deliverable;fields=['document_reference']
 def clean_document_reference(self):
  ref=self.cleaned_data['document_reference'].strip()
  if not ref or '/' in ref or ':' in ref:raise forms.ValidationError('Use an opaque secure document ID, not a URL or file path')
  return ref
class ReviewForm(forms.Form):
 decision=forms.ChoiceField(choices=[('verified','Verify'),('returned','Return for correction'),('approved','Approve')])
 remarks=forms.CharField(widget=forms.Textarea,required=False)
class TrainingForm(forms.ModelForm):
 class Meta:model=Training;fields=['title','date','hours','provider','status','certificate_reference'];widgets={'date':forms.DateInput(attrs={'type':'date'})}
class TaskForm(forms.ModelForm):
  class Meta:model=Task;fields=['title','description','unit','assignee','due_date','priority','status'];widgets={'due_date':forms.DateInput(attrs={'type':'date'}),'description':forms.Textarea(attrs={'rows':3})}
  def clean_title(self):
    t=(self.cleaned_data.get('title') or '').strip()
    if len(t)<3:raise forms.ValidationError('Record name must be at least 3 characters')
    return t
class ShiftForm(forms.ModelForm):
 class Meta:model=ShiftCount;fields=['unit','date','shift','on_duty'];widgets={'date':forms.DateInput(attrs={'type':'date'})}
