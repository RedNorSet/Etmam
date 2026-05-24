from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from .models import Notification


@login_required
def open(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])
    return redirect(n.link or '/dashboard/')
