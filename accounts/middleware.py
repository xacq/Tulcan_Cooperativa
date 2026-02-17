from django.shortcuts import redirect
from django.urls import resolve

SAFE_URL_NAMES = {
    "password_change",
    "password_change_done",
    "logout",
    "login",
}

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, "userprofile", None)
            if profile and profile.must_change_password:
                current = resolve(request.path_info).url_name
                if current not in SAFE_URL_NAMES and not request.path_info.startswith("/admin/"):
                    return redirect("password_change")

        return self.get_response(request)
