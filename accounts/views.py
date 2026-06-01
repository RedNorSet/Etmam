import re

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import User


def _password_error(password):
    if len(password) < 8:
        return 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Za-z]', password):
        return 'Password must contain at least one letter.'
    if not re.search(r'\d', password):
        return 'Password must contain at least one number.'
    if not re.search(r'[^A-Za-z0-9]', password):
        return 'Password must contain at least one special character.'
    return None


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
        action = request.POST.get('action', 'profile')

        if action == 'password':
            current_pw = request.POST.get('current_password', '')
            new_pw     = request.POST.get('new_password', '')
            confirm_pw = request.POST.get('confirm_password', '')
            if not user.check_password(current_pw):
                messages.error(request, 'Current password is incorrect.')
            else:
                pw_err = _password_error(new_pw)
                if pw_err:
                    messages.error(request, pw_err)
                elif new_pw != confirm_pw:
                    messages.error(request, 'New passwords do not match.')
                else:
                    user.set_password(new_pw)
                    user.save()
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, user)
                    messages.success(request, 'Password changed successfully.')
        else:
            user.bio           = request.POST.get('bio', '').strip()
            user.expertise     = request.POST.get('expertise', '').strip()
            user.office_hours  = request.POST.get('office_hours', '').strip()
            user.past_projects = request.POST.get('past_projects', '').strip()
            user.save(update_fields=['bio', 'expertise', 'office_hours', 'past_projects'])
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

        pw_err = _password_error(password)
        if pw_err:
            messages.error(request, pw_err)
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
            username      = username,
            full_name     = full_name,
            email         = email,
            role          = role,
            gender        = gender,
            department    = department,
            student_id    = student_id or None,
            expertise     = request.POST.get('expertise', '').strip(),
            bio           = request.POST.get('bio', '').strip(),
            office_hours  = request.POST.get('office_hours', '').strip(),
            past_projects = request.POST.get('past_projects', '').strip(),
            can_review    = 'can_review' in request.POST,
            available     = 'available' in request.POST,
            is_active     = True,
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
        full_name  = request.POST.get('full_name', '').strip()
        username   = request.POST.get('username', '').strip()
        email      = request.POST.get('email', '').strip()
        department = request.POST.get('department', '').strip()

        if not full_name:
            messages.error(request, 'Full name is required.')
            return render(request, 'accounts/edit_user.html', {'target': target})
        if not username:
            messages.error(request, 'Username is required.')
            return render(request, 'accounts/edit_user.html', {'target': target})
        if not email:
            messages.error(request, 'Email is required.')
            return render(request, 'accounts/edit_user.html', {'target': target})
        if not department:
            messages.error(request, 'Department is required.')
            return render(request, 'accounts/edit_user.html', {'target': target})

        if User.objects.filter(username=username).exclude(pk=user_id).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return render(request, 'accounts/edit_user.html', {'target': target})

        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            pw_err = _password_error(new_password)
            if pw_err:
                messages.error(request, pw_err)
                return render(request, 'accounts/edit_user.html', {'target': target})
            target.set_password(new_password)

        target.full_name     = full_name
        target.username      = username
        target.email         = email
        target.role          = request.POST.get('role', target.role)
        target.department    = department
        target.student_id    = request.POST.get('student_id', '').strip() or None
        target.expertise     = request.POST.get('expertise', '').strip()
        target.bio           = request.POST.get('bio', '').strip()
        target.office_hours  = request.POST.get('office_hours', '').strip()
        target.past_projects = request.POST.get('past_projects', '').strip()
        target.can_review    = 'can_review' in request.POST
        target.available     = 'available' in request.POST
        # Gender is editable only for inactive (archive placeholder) users
        if not target.is_active:
            gender = request.POST.get('gender', '').strip()
            if gender in ('male', 'female', ''):
                target.gender = gender
        target.is_active   = 'is_active' in request.POST

        max_teams_supervise = request.POST.get('max_teams_supervise', '').strip()
        if max_teams_supervise.isdigit():
            target.max_teams_supervise = int(max_teams_supervise)
        max_teams_review = request.POST.get('max_teams_review', '').strip()
        if max_teams_review.isdigit():
            target.max_teams_review = int(max_teams_review)

        target.save()
        messages.success(request, f'{target.username} updated successfully.')
        return redirect('accounts:edit_user', user_id=user_id)

    return render(request, 'accounts/edit_user.html', {'target': target})


@login_required
@require_POST
def delete_user(request, user_id):
    if not request.user.is_administrator():
        return redirect('dashboard:index')

    target = get_object_or_404(User, pk=user_id)

    if target.pk == request.user.pk:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('dashboard:admin')

    username = target.username
    target.delete()
    messages.success(request, f'User "{username}" has been deleted.')
    return redirect('dashboard:admin')
