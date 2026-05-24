from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

from accounts.models import User
from teams.models import Team, TeamMember
from projects.models import Project, SupervisionRequest
from milestones.models import Milestone
from submissions.models import Submission
from reviews.models import Grade
from notifications.models import Notification
from meetings.models import Meeting, MeetingParticipant, RescheduleProposal
from meetings.views import eligible_participants


@login_required
def index(request):
    u = request.user
    if u.is_administrator():
        return redirect('dashboard:admin')
    if u.is_supervisor():
        return redirect('dashboard:supervisor')
    if u.is_reviewer() and not u.is_supervisor():
        return redirect('dashboard:reviewer')
    return redirect('dashboard:student')


@login_required
def student_dashboard(request):
    user        = request.user
    membership     = TeamMember.objects.filter(user=user, status='active').select_related('team').first()
    team           = membership.team if membership else None
    team_members   = TeamMember.objects.filter(team=team, status='active').select_related('user') if team else []
    pending_invite = TeamMember.objects.filter(user=user, status='pending').select_related('team').first()

    project    = getattr(team, 'project', None) if team else None
    milestones = project.milestones.all() if project else []

    notifications  = Notification.objects.filter(recipient=user).order_by('-created_at')[:15]
    unread_count   = Notification.objects.filter(recipient=user, is_read=False).count()
    upcoming       = Meeting.objects.filter(project=project, datetime__gte=timezone.now()).order_by('datetime')[:5] if project else []
    past_meetings  = Meeting.objects.filter(project=project, datetime__lt=timezone.now()).order_by('-datetime')[:5] if project else []
    supervisors    = User.objects.filter(role='supervisor', available=True).order_by('full_name')
    pending_request = SupervisionRequest.objects.filter(team=team, status='pending').first() if team else None

    pending_invitations = (
        MeetingParticipant.objects
        .filter(user=user, response='pending')
        .exclude(meeting__status__in=['cancelled', 'completed'])
        .select_related('meeting', 'meeting__scheduled_by')
        .order_by('meeting__datetime')
    )
    pending_proposals = (
        RescheduleProposal.objects
        .filter(meeting__scheduled_by=user, status='open')
        .select_related('meeting', 'proposed_by')
        .order_by('-created_at')
    )

    return render(request, 'dashboard/student.html', {
        'membership':           membership,
        'team':                 team,
        'team_members':         team_members,
        'pending_invite':       pending_invite,
        'project':              project,
        'milestones':           milestones,
        'notifications':        notifications,
        'unread_count':         unread_count,
        'upcoming':             upcoming,
        'past_meetings':        past_meetings,
        'supervisors':          supervisors,
        'pending_request':      pending_request,
        'eligible_participants':eligible_participants(user),
        'pending_invitations':  pending_invitations,
        'pending_proposals':    pending_proposals,
    })


@login_required
def supervisor_dashboard(request):
    user        = request.user
    supervised  = Project.objects.filter(supervisor=user).select_related('team')
    reviewed    = Project.objects.filter(reviewers=user).select_related('team') if user.can_review else []
    pending_req = SupervisionRequest.objects.filter(supervisor=user, status='pending').select_related('team')
    upcoming    = Meeting.objects.filter(project__supervisor=user, datetime__gte=timezone.now()).order_by('datetime')[:10]
    past        = Meeting.objects.filter(project__supervisor=user, datetime__lt=timezone.now()).order_by('-datetime')[:5]
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')[:15]
    unread_count  = Notification.objects.filter(recipient=user, is_read=False).count()

    pending_invitations = (
        MeetingParticipant.objects
        .filter(user=user, response='pending')
        .exclude(meeting__status__in=['cancelled', 'completed'])
        .select_related('meeting', 'meeting__scheduled_by')
        .order_by('meeting__datetime')
    )
    pending_proposals = (
        RescheduleProposal.objects
        .filter(meeting__scheduled_by=user, status='open')
        .select_related('meeting', 'proposed_by')
        .order_by('-created_at')
    )

    return render(request, 'dashboard/supervisor.html', {
        'supervised':           supervised,
        'reviewed':             reviewed,
        'pending_req':          pending_req,
        'upcoming':             upcoming,
        'past':                 past,
        'notifications':        notifications,
        'unread_count':         unread_count,
        'eligible_participants':eligible_participants(user),
        'pending_invitations':  pending_invitations,
        'pending_proposals':    pending_proposals,
    })


@login_required
def admin_dashboard(request):
    total_teams       = Team.objects.filter(is_active=True).count()
    total_students    = User.objects.filter(role='student').count()
    total_supervisors = User.objects.filter(role='supervisor').count()
    total_reviewers   = User.objects.filter(role='reviewer').count()
    overdue           = Milestone.objects.filter(due_date__lt=timezone.now().date(), status__in=['pending', 'in_progress']).count()
    pending_grades    = Grade.objects.filter(final_score__isnull=True).count()

    students = User.objects.filter(role='student').order_by('full_name', 'username')
    staff    = User.objects.filter(role__in=['supervisor', 'reviewer']).order_by('full_name', 'username')
    admins   = User.objects.filter(role='administrator').order_by('full_name', 'username')

    # All teams (active + inactive for full visibility)
    raw_teams   = Team.objects.all().select_related('project__supervisor').prefetch_related(
                    'memberships__user', 'project__reviewers').order_by('-created_at')
    total_teams = raw_teams.filter(is_active=True).count()

    # Build enriched teams_data for accordion
    teams_data = []
    for team in raw_teams:
        project        = getattr(team, 'project', None)
        active_members = [m for m in team.memberships.all() if m.status == 'active']
        pending_members= [m for m in team.memberships.all() if m.status == 'pending']
        reviewer_ids   = list(project.reviewers.values_list('id', flat=True)) if project else []
        # Supervisor can't be a reviewer → exclude from reviewer dropdown
        supervisor_pk  = project.supervisor.pk if project and project.supervisor else None
        excl_rev_ids   = reviewer_ids + ([supervisor_pk] if supervisor_pk else [])
        teams_data.append({
            'team':            team,
            'project':         project,
            'active_members':  active_members,
            'pending_members': pending_members,
            'reviewer_ids':    reviewer_ids,
            'excl_rev_ids':    excl_rev_ids,
        })

    projects    = Project.objects.select_related('team', 'supervisor').order_by('-created_at')
    milestones  = Milestone.objects.select_related('project').order_by('due_date')
    submissions = Submission.objects.filter(is_latest=True).select_related('milestone', 'submitted_by').order_by('-submitted_at')
    grades      = Grade.objects.select_related('project').order_by('-graded_at')

    # Supervisors and reviewers for assignment dropdowns
    all_supervisors = User.objects.filter(role='supervisor', is_active=True).order_by('full_name', 'username')
    all_reviewers   = User.objects.filter(can_review=True, is_active=True).order_by('full_name', 'username')

    dissolved_count = Team.objects.filter(is_active=False).count()

    return render(request, 'dashboard/admin.html', {
        'total_teams':       total_teams,
        'total_projects':    projects.count(),
        'total_students':    total_students,
        'total_supervisors': total_supervisors,
        'total_reviewers':   total_reviewers,
        'overdue':           overdue,
        'pending_grades':    pending_grades,
        'students':          students,
        'staff':             staff,
        'admins':            admins,
        'teams_data':        teams_data,
        'projects':          projects,
        'milestones':        milestones,
        'submissions':       submissions,
        'grades':            grades,
        'all_supervisors':   all_supervisors,
        'all_reviewers':     all_reviewers,
        'dissolved_count':   dissolved_count,
    })


@login_required
def supervisor_team_detail(request, project_id):
    if not request.user.is_supervisor():
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id, supervisor=request.user)
    members = TeamMember.objects.filter(team=project.team, status='active').select_related('user')
    return render(request, 'dashboard/supervisor_team_detail.html', {
        'project': project,
        'members': members,
    })


@login_required
def admin_team_detail(request, team_id):
    if not request.user.is_administrator():
        return redirect('dashboard:admin')
    team    = get_object_or_404(Team, pk=team_id)
    members = TeamMember.objects.filter(team=team, status='active').select_related('user')
    pending = TeamMember.objects.filter(team=team, status='pending').select_related('user')
    project = getattr(team, 'project', None)
    return render(request, 'dashboard/admin_team_detail.html', {
        'team':    team,
        'members': members,
        'pending': pending,
        'project': project,
    })


@login_required
def reviewer_dashboard(request):
    user          = request.user
    projects      = Project.objects.filter(reviewers=user).select_related('team', 'supervisor')
    grades        = Grade.objects.filter(project__reviewers=user).select_related('project')
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')[:15]
    unread_count  = Notification.objects.filter(recipient=user, is_read=False).count()

    return render(request, 'dashboard/reviewer.html', {
        'projects':      projects,
        'grades':        grades,
        'notifications': notifications,
        'unread_count':  unread_count,
    })


# ─── Admin helper ────────────────────────────────────────────────────────────

def _admin_redirect(team_id):
    """Redirect back to admin Teams & Projects tab with the accordion open."""
    return redirect(reverse('dashboard:admin') + f'?panel=teams_projects&open={team_id}')


def _require_admin(request):
    return request.user.is_authenticated and request.user.is_administrator()


# ─── Team member management ──────────────────────────────────────────────────

@login_required
@require_POST
def admin_add_member(request, team_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    team     = get_object_or_404(Team, pk=team_id)
    username = request.POST.get('username', '').strip()
    if not username:
        messages.error(request, 'No student selected.')
        return _admin_redirect(team_id)
    try:
        student = User.objects.get(username=username, role='student')
    except User.DoesNotExist:
        messages.error(request, f'Student "{username}" not found.')
        return _admin_redirect(team_id)
    if TeamMember.objects.filter(user=student).exists():
        messages.error(request, f'{student.full_name or username} is already in a team.')
        return _admin_redirect(team_id)
    TeamMember.objects.create(team=team, user=student, role='member', status='active')
    messages.success(request, f'{student.full_name or username} added to {team.name}.')
    return _admin_redirect(team_id)


@login_required
@require_POST
def admin_change_leader(request, team_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    team      = get_object_or_404(Team, pk=team_id)
    member_id = request.POST.get('member_id')
    try:
        new_leader = TeamMember.objects.get(pk=member_id, team=team, status='active')
    except TeamMember.DoesNotExist:
        messages.error(request, 'Member not found.')
        return _admin_redirect(team_id)
    # Demote current leader(s)
    team.memberships.filter(role='leader').update(role='member')
    # Promote new leader
    new_leader.role = 'leader'
    new_leader.save()
    messages.success(request, f'{new_leader.user.full_name or new_leader.user.username} is now team leader.')
    return _admin_redirect(team_id)


# ─── Project management ──────────────────────────────────────────────────────

@login_required
@require_POST
def admin_create_project(request, team_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    team  = get_object_or_404(Team, pk=team_id)
    if hasattr(team, 'project'):
        messages.error(request, 'This team already has a project.')
        return _admin_redirect(team_id)
    title       = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    if not title:
        messages.error(request, 'Project title is required.')
        return _admin_redirect(team_id)
    Project.objects.create(team=team, title=title, description=description, status='draft')
    messages.success(request, f'Project "{title}" created for {team.name}.')
    return _admin_redirect(team_id)


@login_required
@require_POST
def admin_update_project(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project     = get_object_or_404(Project, pk=project_id)
    title       = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    status      = request.POST.get('status', '').strip()
    valid_statuses = [s for s, _ in Project.STATUS]
    if not title:
        messages.error(request, 'Project title cannot be empty.')
        return _admin_redirect(project.team.pk)
    project.title       = title
    project.description = description
    if status in valid_statuses:
        project.status = status
    project.save()
    messages.success(request, f'Project "{project.title}" updated.')
    return _admin_redirect(project.team.pk)


# ─── Supervisor management ───────────────────────────────────────────────────

@login_required
@require_POST
def admin_assign_supervisor(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project     = get_object_or_404(Project, pk=project_id)
    sup_id      = request.POST.get('supervisor_id', '').strip()
    if not sup_id:
        messages.error(request, 'No supervisor selected.')
        return _admin_redirect(project.team.pk)
    try:
        supervisor = User.objects.get(pk=int(sup_id), role='supervisor')
    except (User.DoesNotExist, ValueError):
        messages.error(request, 'Supervisor not found.')
        return _admin_redirect(project.team.pk)
    old_supervisor = project.supervisor
    project.supervisor = supervisor
    if project.status == 'draft':
        project.status = 'active'
    project.save()

    # If the new supervisor was already a reviewer, remove them from reviewers
    # (a person cannot be both supervisor and reviewer for the same project)
    reviewer_removed = False
    if project.reviewers.filter(pk=supervisor.pk).exists():
        project.reviewers.remove(supervisor)
        reviewer_removed = True

    # Notify new supervisor
    Notification.objects.create(
        recipient=supervisor,
        type='approval',
        title=f'Supervisor Assignment — {project.team.name}',
        message=f'You have been assigned as supervisor for "{project.title}" (Team: {project.team.name}) by an administrator.',
    )
    # Notify displaced supervisor if there was one
    if old_supervisor and old_supervisor != supervisor:
        Notification.objects.create(
            recipient=old_supervisor,
            type='general',
            title=f'Supervisor Change — {project.team.name}',
            message=f'You have been replaced as supervisor for "{project.title}" (Team: {project.team.name}) by an administrator.',
        )

    msg = f'{supervisor.full_name or supervisor.username} assigned as supervisor.'
    if reviewer_removed:
        msg += ' They were also a reviewer and have been automatically removed from that role.'
    messages.success(request, msg)
    return _admin_redirect(project.team.pk)


@login_required
@require_POST
def admin_remove_supervisor(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project        = get_object_or_404(Project, pk=project_id)
    old_supervisor = project.supervisor
    project.supervisor = None
    project.status     = 'draft'
    project.save()
    if old_supervisor:
        Notification.objects.create(
            recipient=old_supervisor,
            type='general',
            title=f'Supervisor Removed — {project.team.name}',
            message=f'You have been removed as supervisor from "{project.title}" (Team: {project.team.name}) by an administrator.',
        )
    messages.success(request, 'Supervisor removed.')
    return _admin_redirect(project.team.pk)


# ─── Reviewer management ─────────────────────────────────────────────────────

@login_required
@require_POST
def admin_assign_reviewer(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project     = get_object_or_404(Project, pk=project_id)
    rev_id      = request.POST.get('reviewer_id', '').strip()
    if not rev_id:
        messages.error(request, 'No reviewer selected.')
        return _admin_redirect(project.team.pk)
    try:
        reviewer = User.objects.get(pk=int(rev_id), can_review=True)
    except (User.DoesNotExist, ValueError):
        messages.error(request, 'Reviewer not found or cannot review.')
        return _admin_redirect(project.team.pk)
    if project.reviewers.count() >= 2:
        messages.error(request, 'Maximum 2 reviewers already assigned.')
        return _admin_redirect(project.team.pk)
    if project.reviewers.filter(pk=reviewer.pk).exists():
        messages.error(request, f'{reviewer.full_name or reviewer.username} is already a reviewer.')
        return _admin_redirect(project.team.pk)
    # Supervisor cannot be a reviewer for their own team
    if project.supervisor and project.supervisor.pk == reviewer.pk:
        messages.error(request, f'{reviewer.full_name or reviewer.username} is already the supervisor of this project and cannot also be a reviewer.')
        return _admin_redirect(project.team.pk)
    project.reviewers.add(reviewer)
    Notification.objects.create(
        recipient=reviewer,
        type='approval',
        title=f'Reviewer Assignment — {project.team.name}',
        message=f'You have been assigned as reviewer for "{project.title}" (Team: {project.team.name}) by an administrator.',
    )
    messages.success(request, f'{reviewer.full_name or reviewer.username} added as reviewer.')
    return _admin_redirect(project.team.pk)


@login_required
@require_POST
def admin_remove_reviewer(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project    = get_object_or_404(Project, pk=project_id)
    rev_id     = request.POST.get('reviewer_id', '').strip()
    if not rev_id:
        messages.error(request, 'No reviewer specified.')
        return _admin_redirect(project.team.pk)
    try:
        reviewer = User.objects.get(pk=int(rev_id))
        project.reviewers.remove(reviewer)
        Notification.objects.create(
            recipient=reviewer,
            type='general',
            title=f'Reviewer Removed — {project.team.name}',
            message=f'You have been removed as reviewer from "{project.title}" (Team: {project.team.name}) by an administrator.',
        )
        messages.success(request, f'{reviewer.full_name or reviewer.username} removed as reviewer.')
    except (User.DoesNotExist, ValueError):
        messages.error(request, 'Reviewer not found.')
    return _admin_redirect(project.team.pk)


# ─── Team creation (admin-initiated) ────────────────────────────────────────

@login_required
@require_POST
def admin_create_team(request):
    if not _require_admin(request):
        return redirect('dashboard:index')
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Team name is required.')
        return redirect(reverse('dashboard:admin') + '?panel=teams_projects')
    if Team.objects.filter(name=name, is_active=True).exists():
        messages.error(request, f'An active team named "{name}" already exists.')
        return redirect(reverse('dashboard:admin') + '?panel=teams_projects')

    member_usernames = request.POST.getlist('members')   # list of usernames
    leader_username  = request.POST.get('leader', '').strip()

    team = Team.objects.create(name=name, created_by=request.user, is_active=True)
    added, skipped = [], []
    for username in member_usernames:
        username = username.strip()
        if not username:
            continue
        try:
            student = User.objects.get(username=username, role='student')
        except User.DoesNotExist:
            skipped.append(f'"{username}" not found')
            continue
        if TeamMember.objects.filter(user=student).exists():
            skipped.append(f'{student.full_name or username} (already in a team)')
            continue
        role = 'leader' if username == leader_username else 'member'
        TeamMember.objects.create(team=team, user=student, role=role, status='active')
        added.append(student.full_name or username)

    # If no explicit leader was set but we have members, promote the first one
    if added and not leader_username:
        first = team.memberships.first()
        if first:
            first.role = 'leader'
            first.save()

    if skipped:
        messages.warning(request, 'Skipped: ' + ', '.join(skipped))
    if added:
        messages.success(request, f'Team "{name}" created with {len(added)} member(s): {", ".join(added)}.')
    else:
        messages.success(request, f'Team "{name}" created (no members added yet — open the accordion to add members).')
    return _admin_redirect(team.pk)


# ─── Bulk delete dissolved teams ─────────────────────────────────────────────

@login_required
@require_POST
def admin_delete_dissolved_teams(request):
    if not _require_admin(request):
        return redirect('dashboard:index')

    dissolved_teams = Team.objects.filter(is_active=False)
    if not dissolved_teams.exists():
        messages.info(request, 'No dissolved teams to delete.')
        return redirect(reverse('dashboard:admin') + '?panel=teams_projects')

    # Nullify the archive FK reference before deletion to avoid IntegrityError.
    # archives_archivedproject.source_project_id → projects_project(id) has no ON DELETE CASCADE/SET NULL.
    project_ids = list(Project.objects.filter(team__in=dissolved_teams).values_list('pk', flat=True))
    if project_ids:
        from django.db import connection
        placeholders = ','.join(['%s'] * len(project_ids))
        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE archives_archivedproject SET source_project_id = NULL WHERE source_project_id IN ({placeholders})',
                project_ids,
            )

    count, _ = dissolved_teams.delete()
    if count:
        messages.success(request, f'{count} dissolved team{"s" if count != 1 else ""} permanently deleted.')
    else:
        messages.info(request, 'No dissolved teams to delete.')
    return redirect(reverse('dashboard:admin') + '?panel=teams_projects')


# ─── Student search for add-member ──────────────────────────────────────────

@login_required
def admin_search_students(request):
    if not _require_admin(request):
        return JsonResponse([], safe=False)
    from django.db.models import Q as Qobj
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)

    # Build mapping: student_id → team_name for assigned students
    assigned_map = {
        tm.user_id: tm.team.name
        for tm in TeamMember.objects.filter(status='active').select_related('team')
    }

    qs = (
        User.objects
        .filter(role='student', is_active=True)
        .filter(Qobj(full_name__icontains=q) | Qobj(username__icontains=q) | Qobj(student_id__icontains=q))
        .order_by('full_name', 'username')[:15]
    )
    data = [
        {
            'username':     s.username,
            'full_name':    s.full_name or '',
            'student_id':   s.student_id or '',
            'department':   s.department or '',
            'current_team': assigned_map.get(s.pk),   # None if free
        }
        for s in qs
    ]
    return JsonResponse(data, safe=False)
