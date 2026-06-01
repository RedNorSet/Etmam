from django.conf import settings
from django.shortcuts import redirect

# URLs that unauthenticated users are allowed to visit
_PUBLIC_PREFIXES = (
    settings.LOGIN_URL,
    '/accounts/login/',
    '/accounts/logout/',
    '/static/',
    '/media/',
    '/admin/',          # Django built-in admin has its own auth
)


class LoginRequiredMiddleware:
    """
    Redirect any unauthenticated request that isn't headed for a public URL
    to the login page. Acts as a safety net on top of @login_required decorators.
    """

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
    """
    Force-logout sessions belonging to deactivated accounts.
    Runs after AuthenticationMiddleware so request.user is already resolved.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            from django.contrib.auth import logout
            logout(request)
            return redirect(settings.LOGIN_URL)
        return self.get_response(request)
