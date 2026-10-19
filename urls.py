from django.contrib import admin
from django.urls import path,include
urlpatterns=[path('admin/',admin.site.urls),path('accounts/',include('django.contrib.auth.urls')),path('',include('core.urls'))]
admin.site.site_header='PNDMIS administration'
admin.site.site_title='PNDMIS'
admin.site.index_title='PNDMIS admin'
