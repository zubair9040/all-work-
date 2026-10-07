from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.urls import path

from core.auth import ERPLoginView
from core.views import dashboard

admin.site.site_header = "ERP Administration"
admin.site.site_title = "ERP"

# Send the admin's own login page to the branded one
admin.site.login = lambda request, extra_context=None: redirect(f"/login/?next={request.GET.get('next', '/admin/')}")

urlpatterns = [
    path("login/", ERPLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
]
