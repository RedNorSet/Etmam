from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.contrib import messages

from accounts.models import User
from .models import Team, TeamMember


@login_required
@require_POST
def create_team(request):
    if not request.user.is_student():
        messages.error(request, 'Only students can create teams.')
        return redirect('dashboard:student')

    if TeamMember.objects.filter(user=request.user).exists():
        messages.error(request, 'You are already in a team.')
        return redirect('dashboard:student')

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Team name cannot be empty.')
        return redirect('dashboard:student')

    if Team.objects.filter(name=name).exists():
        messages.error(request, 'A team with that name already exists.')
        return redirect('dashboard:student')

    team = Team.objects.create(name=name, created_by=request.user)
    TeamMember.objects.create(team=team, user=request.user, role='leader')
    messages.success(request, f'Team "{name}" created successfully.')
    return redirect('dashboard:student')


@login_required
@require_POST
def invite_member(request):
    if not request.user.is_student():
        messages.error(request, 'Only students can invite members.')
        return redirect('dashboard:student')

    membership = TeamMember.objects.filter(user=request.user).first()
    if not membership:
        messages.error(request, 'You must be in a team to invite members.')
        return redirect('dashboard:student')

    username = request.POST.get('username', '').strip()
    if not username:
        messages.error(request, 'Please enter a username.')
        return redirect('dashboard:student')

    try:
        invitee = User.objects.get(username=username, role='student')
    except User.DoesNotExist:
        messages.error(request, f'No student found with username "{username}".')
        return redirect('dashboard:student')

    if TeamMember.objects.filter(user=invitee).exists():
        messages.error(request, f'{username} is already in a team.')
        return redirect('dashboard:student')

    TeamMember.objects.create(team=membership.team, user=invitee, role='member')
    messages.success(request, f'{invitee.full_name or username} has been added to your team.')
    return redirect('dashboard:student')


@login_required
@require_POST
def remove_member(request, member_id):
    membership = TeamMember.objects.filter(user=request.user).first()
    if not membership or membership.role != 'leader':
        messages.error(request, 'Only the team leader can remove members.')
        return redirect('dashboard:student')

    try:
        target = TeamMember.objects.get(pk=member_id, team=membership.team)
    except TeamMember.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('dashboard:student')

    if target.user == request.user:
        messages.error(request, 'You cannot remove yourself.')
        return redirect('dashboard:student')

    target.delete()
    messages.success(request, 'Member removed from team.')
    return redirect('dashboard:student')
