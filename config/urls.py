from django.contrib import admin
from django.urls import path

from core.views import dashboard

admin.site.site_header = "ERP Administration"
admin.site.site_title = "ERP"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
]
