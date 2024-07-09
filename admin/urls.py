from django.urls import path, include
from django.contrib import admin
from console.admin import console_admin_site

urlpatterns = [    
    path('admin/', console_admin_site.urls),
]