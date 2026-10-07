from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.contrib.auth.views import LoginView
from django.dispatch import receiver
from django.utils import timezone

from .models import LoginAttempt

REMEMBER_SECONDS = 60 * 60 * 24 * 30
MAX_USER_FAILURES = 5      # per username + IP
MAX_IP_FAILURES = 20       # per IP, any username
LOCKOUT = timedelta(minutes=15)


def client_ip(request):
    # REMOTE_ADDR only: X-Forwarded-For is client-controlled unless a trusted proxy sets it.
    return request.META.get("REMOTE_ADDR") or None


def lockout_remaining(username, ip):
    """Return the timedelta left on a lockout, or None if sign-in is allowed."""
    since = timezone.now() - LOCKOUT
    recent = LoginAttempt.objects.filter(created_at__gte=since)
    for qs, limit in (
        (recent.filter(username__iexact=username, ip=ip), MAX_USER_FAILURES),
        (recent.filter(ip=ip), MAX_IP_FAILURES),
    ):
        times = list(qs.order_by("-created_at").values_list("created_at", flat=True)[:limit])
        if len(times) >= limit:
            # Lock lifts when the oldest counted failure leaves the window
            return times[-1] + LOCKOUT - timezone.now()
    return None


@receiver(user_login_failed)
def record_failure(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    LoginAttempt.objects.create(username=(credentials.get("username") or "")[:150], ip=client_ip(request))


@receiver(user_logged_in)
def clear_failures(sender, request, user, **kwargs):
    LoginAttempt.objects.filter(username__iexact=user.get_username(), ip=client_ip(request)).delete()


class ERPLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        remaining = lockout_remaining(request.POST.get("username", ""), client_ip(request))
        if remaining is not None:
            minutes = max(1, int(remaining.total_seconds() // 60) + 1)
            self.locked_minutes = minutes
            # Don't even check the password while locked, so guessing gets no signal
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["locked_minutes"] = getattr(self, "locked_minutes", None)
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        # 0 = expire when the browser closes; otherwise keep for 30 days
        self.request.session.set_expiry(REMEMBER_SECONDS if self.request.POST.get("remember") else 0)
        return response
