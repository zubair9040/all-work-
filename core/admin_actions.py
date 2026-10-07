from django.contrib import messages

from .models import ERPError


def run_action(modeladmin, request, queryset, method, label):
    ok = 0
    for obj in queryset:
        try:
            getattr(obj, method)()
            ok += 1
        except ERPError as e:
            modeladmin.message_user(request, f"{obj}: {e}", messages.ERROR)
    if ok:
        modeladmin.message_user(request, f"{label}: {ok} record(s)", messages.SUCCESS)
