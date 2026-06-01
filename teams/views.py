from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from .models import Team, TeamMember


@login_required
def search_students(request):
    q = request.GET.get('q', '').strip()
    results = []
    if q:
        already_in_team = TeamMember.objects.values_list('user_id', flat=True)
        qs = (
            User.objects
            .filter(role='student')
            .filter(Q(full_name__icontains=q) | Q(student_id__icontains=q))
            .exclude(pk__in=already_in_team)
            .exclude(pk=request.user.pk)
        )
        if request.user.gender:
            qs = qs.filter(gender=request.user.gender)
        if request.user.department:
            qs = qs.filter(department=request.user.department)
        results = qs.order_by('full_name', 'username')[:8]
    return render(request, 'teams/partials/student_search_results.html', {
        'results': results,
        'q': q,
    })


@login_required
@require_POST
def create_team(request):
    if not request.user.is_student():
        messages.error(request, 'Only students can create teams.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    if TeamMember.objects.filter(user=request.user).exists():
        messages.error(request, 'You are already in a team.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Team name cannot be empty.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    if Team.objects.filter(name=name, is_active=True).exists():
        messages.error(request, 'An active team with that name already exists.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    team = Team.objects.create(name=name, created_by=request.user)
    TeamMember.objects.create(team=team, user=request.user, role='leader', status='active')
    messages.success(request, f'Team "{name}" created successfully.')
    return redirect(reverse('dashboard:student') + '#sec-team')


@login_required
@require_POST
def invite_member(request):
    if not request.user.is_student():
        messages.error(request, 'Only students can invite members.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    membership = TeamMember.objects.filter(user=request.user, status='active').first()
    if not membership:
        messages.error(request, 'You must be in a team to invite members.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    username = request.POST.get('username', '').strip()
    if not username:
        messages.error(request, 'Please select a student.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    try:
        invitee = User.objects.get(username=username, role='student')
    except User.DoesNotExist:
        messages.error(request, f'No student found with username "{username}".')
        return redirect(reverse('dashboard:student') + '#sec-team')

    if TeamMember.objects.filter(user=invitee).exists():
        messages.error(request, f'{invitee.full_name or username} is already in a team or has a pending invite.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    if not request.user.gender:
        messages.error(request, 'Please set your gender before inviting members.')
        return redirect(reverse('dashboard:student') + '#sec-team')
    if not invitee.gender:
        messages.error(request, f'{invitee.full_name or username} has not set their gender yet.')
        return redirect(reverse('dashboard:student') + '#sec-team')
    if request.user.gender != invitee.gender:
        messages.error(request, 'You can only invite students of the same gender.')
        return redirect(reverse('dashboard:student') + '#sec-team')
    if request.user.department != invitee.department:
        messages.error(request, 'You can only invite students from the same department.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    active_count = TeamMember.objects.filter(team=membership.team, status='active').count()
    if active_count >= 5:
        messages.error(request, 'Your team already has 5 members. You cannot invite more.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    pending = TeamMember.objects.create(
        team=membership.team,
        user=invitee,
        role='member',
        status='pending',
    )

    Notification.objects.create(
        recipient=invitee,
        type='invite',
        title=f'Team Invitation — {membership.team.name}',
        message=f'{request.user.full_name or request.user.username} has invited you to join team "{membership.team.name}".',
        link=str(pending.pk),
    )

    messages.success(request, f'Invite sent to {invitee.full_name or username}.')
    return redirect(reverse('dashboard:student') + '#sec-team')


@login_required
@require_POST
def accept_invite(request, member_id):
    pending = get_object_or_404(TeamMember, pk=member_id, user=request.user, status='pending')
    pending.status = 'active'
    pending.save()
    Notification.objects.filter(recipient=request.user, type='invite', link=str(member_id)).update(is_read=True)
    messages.success(request, f'You have joined team "{pending.team.name}"!')
    return redirect(reverse('dashboard:student') + '#sec-team')


@login_required
@require_POST
def decline_invite(request, member_id):
    pending = get_object_or_404(TeamMember, pk=member_id, user=request.user, status='pending')
    team_name = pending.team.name
    pending.delete()
    Notification.objects.filter(recipient=request.user, type='invite', link=str(member_id)).update(is_read=True)
    messages.success(request, f'You declined the invite to team "{team_name}".')
    return redirect(reverse('dashboard:student') + '#sec-team')


@login_required
@require_POST
def admin_dissolve_team(request, team_id):
    if not request.user.is_administrator():
        return redirect('dashboard:index')
    team = get_object_or_404(Team, pk=team_id)
    team_name = team.name
    team.delete()
    messages.success(request, f'Team "{team_name}" has been dissolved and deleted.')
    return redirect(reverse('dashboard:admin') + '?panel=teams_projects')


@login_required
@require_POST
def remove_member(request, member_id):
    membership = TeamMember.objects.filter(user=request.user, status='active').first()
    if not membership or membership.role != 'leader':
        messages.error(request, 'Only the team leader can remove members.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    try:
        target = TeamMember.objects.get(pk=member_id, team=membership.team)
    except TeamMember.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    if target.user == request.user:
        messages.error(request, 'You cannot remove yourself.')
        return redirect(reverse('dashboard:student') + '#sec-team')

    team = membership.team
    target.delete()
    if not team.memberships.filter(status='active').exists():
        team.delete()
        messages.success(request, 'Member removed — team deleted (no members remaining).')
        return redirect(reverse('dashboard:student') + '#sec-dashboard')
    messages.success(request, 'Member removed from team.')
    return redirect(reverse('dashboard:student') + '#sec-team')


@login_required
@require_POST
def admin_remove_member(request, member_id):
    if not request.user.is_administrator():
        return redirect('dashboard:admin')
    member = get_object_or_404(TeamMember, pk=member_id)
    team    = member.team
    team_id = team.pk
    member.delete()
    if not team.memberships.filter(status='active').exists():
        team.delete()
        messages.success(request, 'Member removed — team automatically deleted (no members remaining).')
        return redirect(reverse('dashboard:admin') + '?panel=teams_projects')
    messages.success(request, 'Member removed.')
    return redirect(reverse('dashboard:admin') + f'?panel=teams_projects&open={team_id}')


@login_required
@require_POST
def admin_cancel_invite(request, member_id):
    if not request.user.is_administrator():
        return redirect('dashboard:admin')
    invite = get_object_or_404(TeamMember, pk=member_id, status='pending')
    team_id = invite.team.pk
    invite.delete()
    messages.success(request, 'Invite cancelled.')
    return redirect(reverse('dashboard:admin') + f'?panel=teams_projects&open={team_id}')


@login_required
@require_POST
def leave_team(request):
    membership = TeamMember.objects.filter(user=request.user, status='active').first()
    if not membership:
        messages.error(request, 'You are not in a team.')
        return redirect(reverse('dashboard:student') + '#sec-team')
    if membership.role == 'leader':
        messages.error(request, 'Team leaders cannot leave — delete the team instead.')
        return redirect(reverse('dashboard:student') + '#sec-team')
    team_name = membership.team.name
    membership.delete()
    messages.success(request, f'You have left team "{team_name}".')
    return redirect(reverse('dashboard:student') + '#sec-dashboard')


@login_required
@require_POST
def delete_team(request):
    membership = TeamMember.objects.filter(user=request.user, status='active', role='leader').first()
    if not membership:
        messages.error(request, 'Only the team leader can delete the team.')
        return redirect(reverse('dashboard:student') + '#sec-team')
    team = membership.team
    team_name = team.name
    team.memberships.all().delete()
    team.is_active = False
    team.save()
    if hasattr(team, 'project'):
        project = team.project
        project.supervisor = None
        project.reviewers.clear()
        project.status = 'draft'
        project.save()
    messages.success(request, f'Team "{team_name}" has been deleted.')
    return redirect(reverse('dashboard:student') + '#sec-dashboard')
