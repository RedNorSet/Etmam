from django.conf import settings
from django.shortcuts import redirect

_PUBLIC_PREFIXES = (
    settings.LOGIN_URL,
    '/accounts/login/',
    '/accounts/logout/',
    '/static/',
    '/media/',
    '/admin/',
)

class LoginRequiredMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            path = request.path_info
            if not any(path.startswith(p) for p in _PUBLIC_PREFIXES):
                login_url = settings.LOGIN_URL
                return redirect(f'{login_url}?next={path}')
        return self.get_response(request)

class ActiveUserMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            from django.contrib.auth import logout
            logout(request)
            return redirect(settings.LOGIN_URL)
        return self.get_response(request)
