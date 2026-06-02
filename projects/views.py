from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse

from accounts.models import User
from teams.models import TeamMember
from notifications.models import Notification
from .models import Project, SupervisionRequest, ProjectEditRequest

@login_required
def request_supervision(request, supervisor_id):
    if not request.user.is_student():
        return redirect('dashboard:index')

    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership:
        messages.error(request, 'You must be in a team before requesting a supervisor.')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')
    if membership.role != 'leader':
        messages.error(request, 'Only the team leader can request a supervisor.')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    team = membership.team
    supervisor = get_object_or_404(User, pk=supervisor_id, role='supervisor')

    if request.user.department and supervisor.department and request.user.department != supervisor.department:
        messages.error(request, f'This supervisor is in "{supervisor.department}" department; your department is "{request.user.department}".')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    if not supervisor.available:
        messages.error(request, f'{supervisor.full_name or supervisor.username} is not accepting new students.')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    if supervisor.is_at_capacity():
        messages.error(request, f'{supervisor.full_name or supervisor.username} has reached their team limit.')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    if SupervisionRequest.objects.filter(team=team, supervisor=supervisor, status__in=['pending', 'accepted']).exists():
        messages.error(request, 'You have already sent a request to this supervisor.')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    if hasattr(team, 'project') and team.project.supervisor:
        messages.error(request, 'Your team already has a supervisor.')
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        pitch = request.POST.get('pitch', '').strip()
        if not title or not pitch:
            messages.error(request, 'Please fill in all fields.')
            return redirect(reverse('dashboard:student') + '#sec-supervisors')

        declined = SupervisionRequest.objects.filter(team=team, supervisor=supervisor, status='declined').first()
        if declined:
            declined.title = title
            declined.pitch = pitch
            declined.status = 'pending'
            declined.save()
        else:
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
        return redirect(reverse('dashboard:student') + '#sec-supervisors')

    return redirect('dashboard:student')

@login_required
@require_POST
def accept_supervision(request, req_id):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')

    sup_req = get_object_or_404(SupervisionRequest, pk=req_id, supervisor=request.user, status='pending')
    team = sup_req.team

    if request.user.is_at_capacity():
        messages.error(request, f'You have reached your supervision limit ({request.user.max_teams_supervise} teams). Update your limit in your profile if needed.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

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

    SupervisionRequest.objects.filter(team=team, status='pending').exclude(pk=req_id).update(status='declined')

    for member in team.memberships.filter(status='active'):
        Notification.objects.create(
            recipient=member.user,
            type='approval',
            title='Supervision Request Accepted',
            message=f'{request.user.full_name or request.user.username} has accepted your supervision request for "{sup_req.title}".',
        )

    messages.success(request, f'You are now supervising team "{team.name}".')
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')

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
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')

@login_required
@require_POST
def admin_remove_supervisor(request, project_id):
    if not request.user.is_administrator():
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id)
    project.supervisor = None
    project.save()
    messages.success(request, f'Supervisor removed from "{project.title}".')
    team_id = project.team.pk
    return redirect(reverse('dashboard:admin') + f'?panel=teams_projects&open={team_id}')

@login_required
@require_POST
def admin_remove_reviewer(request, project_id):
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

@login_required
@require_POST
def student_propose_project_edit(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    membership = TeamMember.objects.filter(user=request.user, team=project.team, status='active').first()
    if not membership or membership.role != 'leader':
        messages.error(request, 'Only the team leader can propose project edits.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    new_title = request.POST.get('new_title', '').strip()
    new_description = request.POST.get('new_description', '').strip()

    if not new_title:
        messages.error(request, 'Project title cannot be empty.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    if new_title == project.title and new_description == project.description:
        messages.info(request, 'No changes detected.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    ProjectEditRequest.objects.update_or_create(
        project=project,
        defaults={
            'new_title':       new_title,
            'new_description': new_description,
            'submitted_by':    request.user,
        },
    )

    if project.supervisor:
        Notification.objects.create(
            recipient=project.supervisor,
            type='general',
            title=f'Project Edit Request — {project.team.name}',
            message=f'{request.user.full_name or request.user.username} has proposed changes to "{project.title}".',
        )

    messages.success(request, 'Edit request submitted — waiting for your supervisor to approve.')
    return redirect(reverse('dashboard:student') + '#sec-milestones')

@login_required
@require_POST
def supervisor_approve_edit(request, project_id):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id, supervisor=request.user)
    try:
        pending = project.pending_edit
    except ProjectEditRequest.DoesNotExist:
        messages.error(request, 'No pending edit found.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    old_title = project.title
    project.title       = pending.new_title
    project.description = pending.new_description
    project.save(update_fields=['title', 'description'])

    Notification.objects.create(
        recipient=pending.submitted_by,
        type='approval',
        title='Project Edit Approved',
        message=f'Your changes to "{old_title}" have been approved.',
    )
    pending.delete()
    messages.success(request, f'Changes to "{project.title}" approved.')
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')

@login_required
@require_POST
def supervisor_reject_edit(request, project_id):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id, supervisor=request.user)
    try:
        pending = project.pending_edit
    except ProjectEditRequest.DoesNotExist:
        messages.error(request, 'No pending edit found.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    Notification.objects.create(
        recipient=pending.submitted_by,
        type='general',
        title='Project Edit Rejected',
        message=f'Your proposed changes to "{project.title}" were rejected. Original values will be kept.',
    )
    pending.delete()
    messages.success(request, 'Edit request rejected. Original project details retained.')
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')
