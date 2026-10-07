from django.contrib.auth.views import LoginView

REMEMBER_SECONDS = 60 * 60 * 24 * 30


class ERPLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        # 0 = expire when the browser closes; otherwise keep for 30 days
        self.request.session.set_expiry(REMEMBER_SECONDS if self.request.POST.get("remember") else 0)
        return response
