import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger('gpms.auth')

def _ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '?')

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    logger.info('LOGIN user=%s role=%s ip=%s', user.username, user.role, _ip(request))

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user:
        logger.info('LOGOUT user=%s ip=%s', user.username, _ip(request))

@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    logger.warning('LOGIN_FAILED username=%s ip=%s', credentials.get('username', '?'), _ip(request))
