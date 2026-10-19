from django.urls import path
from . import views
urlpatterns=[
 path('',views.dashboard,name='dashboard'),
 path('records/',views.records_page,name='records'),
 path('categories/',views.categories_page,name='categories'),
 path('reports/',views.reports_page,name='reports'),
 path('users/',views.users_page,name='users'),
 path('settings/',views.settings_page,name='settings'),
 path('staff/',views.staff_directory,name='staff'),
 path('staff/<int:pk>/',views.staff_detail,name='staff_detail'),
 path('deliverables/',views.deliverables,name='deliverables'),
 path('training/',views.training,name='training'),
 path('training/add/',views.add_training,name='add_training'),
 path('tasks/',views.tasks_view,name='tasks'),
 path('tasks/add/',views.add_task,name='add_task'),
 path('tasks/<int:pk>/status/',views.task_status,name='task_status'),
 path('shifts/',views.shifts,name='shifts'),
 path('shifts/add/',views.add_shift,name='add_shift'),
 path('deliverables/<int:pk>/submit/',views.submit,name='submit'),
 path('deliverables/<int:pk>/review/',views.review,name='review'),
 # JSON REST API (CSRF + session auth + RBAC)
 path('api/stats/',views.api_stats,name='api_stats'),
 path('api/analytics/',views.api_analytics,name='api_analytics'),
 path('api/records/',views.api_records,name='api_records'),
 path('api/records/<int:pk>/',views.api_record_detail,name='api_record_detail'),
]
