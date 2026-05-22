from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import User


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next') or 'dashboard:index')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')


@require_POST
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def edit_user(request, user_id):
    if not request.user.is_administrator():
        return redirect('dashboard:index')

    target = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        target.full_name   = request.POST.get('full_name', '').strip()
        target.username    = request.POST.get('username', '').strip()
        target.email       = request.POST.get('email', '').strip()
        target.role        = request.POST.get('role', target.role)
        target.department  = request.POST.get('department', '').strip()
        target.student_id  = request.POST.get('student_id', '').strip() or None
        target.expertise   = request.POST.get('expertise', '').strip()
        target.can_review  = 'can_review' in request.POST
        target.available   = 'available' in request.POST
        target.is_active   = 'is_active' in request.POST

        max_teams = request.POST.get('max_teams', '').strip()
        if max_teams.isdigit():
            target.max_teams = int(max_teams)

        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            target.set_password(new_password)

        target.save()
        messages.success(request, f'{target.username} updated successfully.')
        return redirect('accounts:edit_user', user_id=user_id)

    return render(request, 'accounts/edit_user.html', {'target': target})
