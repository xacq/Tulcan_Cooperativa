from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView, PasswordChangeDoneView
from .views import register_view, CustomLoginView, CustomPasswordChangeView

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", register_view, name="register"),

    path("password-change/", CustomPasswordChangeView.as_view(), name="password_change"),
    path("password-change/done/", PasswordChangeDoneView.as_view(
        template_name="accounts/password_change_done.html"
    ), name="password_change_done"),

    # ---- PASSWORD RESET (Django built-in) ----
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html"
    ), name="password_reset"),

    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"
    ), name="password_reset_done"),

    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html"
    ), name="password_reset_confirm"),

    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"
    ), name="password_reset_complete"),
]
