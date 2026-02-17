from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import render, redirect
from .forms import RegisterForm

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Usuario creado correctamente.")
            # opcional: login directo
            login(request, user)
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.urls import reverse
from datahub.models import UserProfile

GENERIC_PASSWORD = "123456789"  # la que definiste

class CustomLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        # usuario autenticado
        response = super().form_valid(form)

        raw_password = form.cleaned_data.get("password")
        user = self.request.user

        # Solo fuerza cambio si:
        # - password ingresada es la genérica
        # - y el perfil está marcado
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if raw_password == GENERIC_PASSWORD and profile.must_change_password:
            return redirect("password_change")

        return response

from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from datahub.models import UserProfile

class CustomPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        resp = super().form_valid(form)
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])
        return resp
