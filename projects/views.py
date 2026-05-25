from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse

from accounts.models import User
from teams.models import TeamMember
from notifications.models import Notification
from .models import Project, SupervisionRequest


@login_required
def request_supervision(request, supervisor_id):
    if not request.user.is_student():
        return redirect('dashboard:index')

    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership:
        messages.error(request, 'You must be in a team before requesting a supervisor.')
        return redirect('accounts:supervisor_list')

    team = membership.team
    supervisor = get_object_or_404(User, pk=supervisor_id, role='supervisor')

    if not supervisor.available:
        messages.error(request, f'{supervisor.full_name or supervisor.username} is not accepting new students.')
        return redirect('accounts:supervisor_detail', user_id=supervisor_id)

    if supervisor.is_at_capacity():
        messages.error(request, f'{supervisor.full_name or supervisor.username} has reached their team limit.')
        return redirect('accounts:supervisor_detail', user_id=supervisor_id)

    if SupervisionRequest.objects.filter(team=team, supervisor=supervisor).exists():
        messages.error(request, 'You have already sent a request to this supervisor.')
        return redirect('accounts:supervisor_detail', user_id=supervisor_id)

    if hasattr(team, 'project') and team.project.supervisor:
        messages.error(request, 'Your team already has a supervisor.')
        return redirect('dashboard:student')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        pitch = request.POST.get('pitch', '').strip()
        if not title or not pitch:
            messages.error(request, 'Please fill in all fields.')
            return redirect('accounts:supervisor_detail', user_id=supervisor_id)

        SupervisionRequest.objects.create(
            team=team,
            supervisor=supervisor,
            title=title,
            pitch=pitch,
        )

        Notification.objects.create(
            recipient=supervisor,
            type='general',
            title=f'Supervision Request from {team.name}',
            message=f'Team "{team.name}" has requested your supervision for project: "{title}".',
        )

        messages.success(request, f'Request sent to {supervisor.full_name or supervisor.username}.')
        return redirect('accounts:supervisor_detail', user_id=supervisor_id)

    return redirect('accounts:supervisor_detail', user_id=supervisor_id)


@login_required
@require_POST
def accept_supervision(request, req_id):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')

    sup_req = get_object_or_404(SupervisionRequest, pk=req_id, supervisor=request.user, status='pending')
    team = sup_req.team

    # Create or update project
    project, created = Project.objects.get_or_create(
        team=team,
        defaults={
            'title': sup_req.title,
            'description': sup_req.pitch,
            'supervisor': request.user,
            'status': 'active',
        }
    )
    if not created:
        project.supervisor = request.user
        project.status = 'active'
        project.save()

    sup_req.status = 'accepted'
    sup_req.save()

    # Decline all other pending requests from this team
    SupervisionRequest.objects.filter(team=team, status='pending').exclude(pk=req_id).update(status='declined')

    # Notify team members
    for member in team.memberships.filter(status='active'):
        Notification.objects.create(
            recipient=member.user,
            type='approval',
            title='Supervision Request Accepted',
            message=f'{request.user.full_name or request.user.username} has accepted your supervision request for "{sup_req.title}".',
        )

    messages.success(request, f'You are now supervising team "{team.name}".')
    return redirect('dashboard:supervisor')


@login_required
@require_POST
def decline_supervision(request, req_id):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')

    sup_req = get_object_or_404(SupervisionRequest, pk=req_id, supervisor=request.user, status='pending')
    sup_req.status = 'declined'
    sup_req.save()

    for member in sup_req.team.memberships.filter(status='active'):
        Notification.objects.create(
            recipient=member.user,
            type='general',
            title='Supervision Request Declined',
            message=f'{request.user.full_name or request.user.username} has declined your supervision request.',
        )

    messages.success(request, f'Request from "{sup_req.team.name}" declined.')
    return redirect('dashboard:supervisor')


@login_required
@require_POST
def admin_remove_supervisor(request, project_id):
    if not request.user.is_administrator():
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id)
    project.supervisor = None
    project.status = 'draft'
    project.save()
    messages.success(request, f'Supervisor removed from "{project.title}".')
    team_id = project.team.pk
    return redirect(reverse('dashboard:admin') + f'?panel=teams_projects&open={team_id}')


@login_required
@require_POST
def admin_remove_reviewer(request, project_id):
    """Legacy endpoint kept for backward compat; new UI uses dashboard:admin_remove_reviewer."""
    if not request.user.is_administrator():
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id)
    reviewer_id = request.POST.get('reviewer_id')
    if reviewer_id:
        try:
            project.reviewers.remove(int(reviewer_id))
        except (ValueError, TypeError):
            pass
    else:
        project.reviewers.clear()
    messages.success(request, f'Reviewer removed from "{project.title}".')
    team_id = project.team.pk
    return redirect(reverse('dashboard:admin') + f'?panel=teams_projects&open={team_id}')
