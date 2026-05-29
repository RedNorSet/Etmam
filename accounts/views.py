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
def supervisor_profile(request):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')
    user = request.user
    if request.method == 'POST':
        user.bio          = request.POST.get('bio', '').strip()
        user.expertise    = request.POST.get('expertise', '').strip()
        user.office_hours = request.POST.get('office_hours', '').strip()
        user.past_projects = request.POST.get('past_projects', '').strip()
        user.available    = 'available' in request.POST
        user.max_teams_supervise = int(request.POST.get('max_teams_supervise', user.max_teams_supervise) or user.max_teams_supervise)
        user.max_teams_review    = int(request.POST.get('max_teams_review', user.max_teams_review) or user.max_teams_review)
        user.save()
        messages.success(request, 'Profile updated.')
        return redirect('accounts:supervisor_profile')
    return render(request, 'accounts/supervisor_profile.html', {'user': user})




@login_required
def add_user(request):
    if not request.user.is_administrator():
        return redirect('dashboard:index')

    if request.method == 'POST':
        username         = request.POST.get('username', '').strip()
        password         = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        full_name        = request.POST.get('full_name', '').strip()
        email            = request.POST.get('email', '').strip()
        department       = request.POST.get('department', '').strip()
        student_id       = request.POST.get('student_id', '').strip()
        role             = request.POST.get('role', 'student')
        gender           = request.POST.get('gender', '').strip()

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return render(request, 'accounts/add_user.html')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/add_user.html')

        if not full_name:
            messages.error(request, 'Full name is required.')
            return render(request, 'accounts/add_user.html')

        if not email:
            messages.error(request, 'Email is required.')
            return render(request, 'accounts/add_user.html')

        if not department:
            messages.error(request, 'Department is required.')
            return render(request, 'accounts/add_user.html')

        if not student_id:
            messages.error(request, 'ID is required.')
            return render(request, 'accounts/add_user.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return render(request, 'accounts/add_user.html')

        if role != 'administrator' and not gender:
            messages.error(request, 'Gender is required.')
            return render(request, 'accounts/add_user.html')

        if role in ('supervisor', 'reviewer') and not request.POST.get('expertise', '').strip():
            messages.error(request, 'Expertise is required for supervisors and reviewers.')
            return render(request, 'accounts/add_user.html')

        user = User(
            username   = username,
            full_name  = full_name,
            email      = email,
            role       = role,
            gender     = gender,
            department = department,
            student_id = student_id or None,
            expertise  = request.POST.get('expertise', '').strip(),
            can_review = 'can_review' in request.POST,
            available  = 'available' in request.POST,
            is_active  = True,
        )
        max_teams_supervise = request.POST.get('max_teams_supervise', '').strip()
        if max_teams_supervise.isdigit():
            user.max_teams_supervise = int(max_teams_supervise)
        max_teams_review = request.POST.get('max_teams_review', '').strip()
        if max_teams_review.isdigit():
            user.max_teams_review = int(max_teams_review)
        user.set_password(password)
        user.save()
        messages.success(request, f'User "{username}" created successfully.')
        return redirect('accounts:add_user')

    return render(request, 'accounts/add_user.html')


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
        target.gender      = request.POST.get('gender', '').strip()
        target.department  = request.POST.get('department', '').strip()
        target.student_id  = request.POST.get('student_id', '').strip() or None
        target.expertise   = request.POST.get('expertise', '').strip()
        target.can_review  = 'can_review' in request.POST
        target.available   = 'available' in request.POST
        target.is_active   = 'is_active' in request.POST

        max_teams_supervise = request.POST.get('max_teams_supervise', '').strip()
        if max_teams_supervise.isdigit():
            target.max_teams_supervise = int(max_teams_supervise)
        max_teams_review = request.POST.get('max_teams_review', '').strip()
        if max_teams_review.isdigit():
            target.max_teams_review = int(max_teams_review)

        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            target.set_password(new_password)

        target.save()
        messages.success(request, f'{target.username} updated successfully.')
        return redirect('accounts:edit_user', user_id=user_id)

    return render(request, 'accounts/edit_user.html', {'target': target})
