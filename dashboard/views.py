from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.db import connection
from django.db.models import Q

from accounts.models import User
from teams.models import Team, TeamMember
from projects.models import Project, SupervisionRequest
from milestones.models import Milestone, ProjectGrade
from submissions.models import Submission, SubmissionFile
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

    # Global milestones zipped with this team's latest submission per milestone
    global_milestones_qs = Milestone.objects.filter(is_active=True).order_by('order', 'due_date')
    if project:
        sub_map = {
            s.milestone_id: s
            for s in Submission.objects.filter(project=project, is_latest=True)
                               .select_related('milestone', 'submitted_by')
                               .prefetch_related('files')
        }
    else:
        sub_map = {}
    global_milestones = [
        {'milestone': m, 'submission': sub_map.get(m.pk)}
        for m in global_milestones_qs
    ]

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
        'global_milestones':    global_milestones,
        'notifications':        notifications,
        'unread_count':         unread_count,
        'upcoming':             upcoming,
        'past_meetings':        past_meetings,
        'supervisors':          supervisors,
        'pending_request':      pending_request,
        'eligible_participants':eligible_participants(user),
        'pending_invitations':  pending_invitations,
        'pending_proposals':    pending_proposals,
        'today':                timezone.now().date(),
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
    total_students    = User.objects.filter(role='student').count()
    total_supervisors = User.objects.filter(role='supervisor').count()
    total_reviewers   = User.objects.filter(role='reviewer').count()
    overdue           = Milestone.objects.filter(due_date__lt=timezone.now().date(), is_active=True).count()

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

    # Global milestones (objectives)
    milestones  = Milestone.objects.filter(is_active=True).order_by('order', 'due_date')

    # Build submissions-by-milestone data for the Submissions panel
    active_projects = list(
        Project.objects.filter(team__is_active=True).select_related('team').order_by('title')
    )
    submissions_data = []
    for m in milestones:
        subs = list(
            Submission.objects.filter(milestone=m, is_latest=True)
            .select_related('project__team', 'submitted_by')
            .prefetch_related('files')
            .order_by('project__title')
        )
        submitted_project_ids = {s.project_id for s in subs if s.project_id}
        not_submitted = [p for p in active_projects if p.pk not in submitted_project_ids]
        submissions_data.append({
            'milestone':       m,
            'submissions':     subs,
            'not_submitted':   not_submitted,
            'submitted_count': len(submitted_project_ids),
            'total_count':     len(active_projects),
        })

    # ── Grades panel ─────────────────────────────────────────────────────────
    grade_milestones = list(Milestone.objects.filter(is_active=True).order_by('order', 'due_date'))
    grade_projects   = list(
        Project.objects.filter(team__is_active=True)
        .select_related('team', 'supervisor')
        .order_by('team__name')
    )

    # Build column descriptors (one per gradeable component)
    grade_columns = []
    for gm in grade_milestones:
        if gm.has_split:
            r_eff = round(gm.weight * gm.report_weight / 100, 1)
            p_eff = round(gm.weight * gm.presentation_weight / 100, 1)
            grade_columns.append({
                'milestone': gm, 'component': 'report',
                'label': 'Report', 'effective_weight': r_eff, 'is_new_milestone': True,
            })
            grade_columns.append({
                'milestone': gm, 'component': 'presentation',
                'label': 'Presentation', 'effective_weight': p_eff, 'is_new_milestone': False,
            })
        else:
            grade_columns.append({
                'milestone': gm, 'component': 'single',
                'label': gm.title, 'effective_weight': gm.weight, 'is_new_milestone': True,
            })

    # Load all grades into a dict for O(1) lookup
    all_pgs   = ProjectGrade.objects.filter(project__in=grade_projects).select_related('graded_by')
    grade_map = {(g.project_id, g.milestone_id, g.component): g for g in all_pgs}

    # Build grade table rows
    grade_rows = []
    for gp in grade_projects:
        cells = []
        total_earned = 0.0
        all_graded   = True
        for col in grade_columns:
            key = (gp.pk, col['milestone'].pk, col['component'])
            g   = grade_map.get(key)
            cells.append({
                'grade':            g,
                'score_val':        str(g.score) if g and g.score is not None else '',
                'project_id':       gp.pk,
                'milestone_id':     col['milestone'].pk,
                'component':        col['component'],
                'eff_weight':       col['effective_weight'],
                'is_new_milestone': col['is_new_milestone'],
            })
            if g and g.score is not None:
                total_earned += float(g.score) * col['effective_weight'] / 100
            else:
                all_graded = False
        grade_rows.append({
            'project':       gp,
            'cells':         cells,
            'total':         round(total_earned, 1) if all_graded else None,
            'partial_total': round(total_earned, 1),
            'all_graded':    all_graded,
        })

    total_milestone_weight = sum(m.weight for m in grade_milestones)

    # Count ungraded slots for the sidebar badge
    total_grade_slots  = sum(2 if m.has_split else 1 for m in grade_milestones) * len(grade_projects)
    filled_grade_slots = ProjectGrade.objects.filter(
        project__in=grade_projects, score__isnull=False
    ).count()
    pending_grades = max(0, total_grade_slots - filled_grade_slots)

    # Supervisors and reviewers for assignment dropdowns
    all_supervisors = User.objects.filter(role='supervisor', is_active=True).order_by('full_name', 'username')
    all_reviewers   = User.objects.filter(can_review=True, is_active=True).order_by('full_name', 'username')

    dissolved_count = Team.objects.filter(is_active=False).count()

    return render(request, 'dashboard/admin.html', {
        'total_teams':            total_teams,
        'total_projects':         projects.count(),
        'total_students':         total_students,
        'total_supervisors':      total_supervisors,
        'total_reviewers':        total_reviewers,
        'overdue':                overdue,
        'pending_grades':         pending_grades,
        'students':               students,
        'staff':                  staff,
        'admins':                 admins,
        'teams_data':             teams_data,
        'projects':               projects,
        'milestones':             milestones,
        'submissions_data':       submissions_data,
        'grade_milestones':       grade_milestones,
        'grade_columns':          grade_columns,
        'grade_rows':             grade_rows,
        'total_milestone_weight': total_milestone_weight,
        'all_supervisors':        all_supervisors,
        'all_reviewers':          all_reviewers,
        'dissolved_count':        dissolved_count,
        'today':                  timezone.now().date(),
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
        .filter(Q(full_name__icontains=q) | Q(username__icontains=q) | Q(student_id__icontains=q))
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


# ════════════════════════════════════════════════════════════════════════════════
#  MILESTONE ADMIN VIEWS
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_create_milestone(request):
    if not _require_admin(request):
        return redirect('dashboard:index')
    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'Title is required.')
        return redirect(reverse('dashboard:admin') + '?panel=milestones')
    start_date = request.POST.get('start_date') or None
    due_date   = request.POST.get('due_date') or None
    if start_date and due_date and due_date < start_date:
        messages.error(request, 'Due date cannot be before start date.')
        return redirect(reverse('dashboard:admin') + '?panel=milestones')
    order = Milestone.objects.count() + 1
    Milestone.objects.create(
        title=title,
        description=request.POST.get('description', '').strip(),
        start_date=start_date,
        due_date=due_date,
        weight=int(request.POST.get('weight') or 10),
        order=order,
        created_by=request.user,
    )
    messages.success(request, f'Milestone "{title}" created.')
    return redirect(reverse('dashboard:admin') + '?panel=milestones')


@login_required
@require_POST
def admin_update_milestone(request, milestone_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    m = get_object_or_404(Milestone, pk=milestone_id)
    start_date = request.POST.get('start_date') or None
    due_date   = request.POST.get('due_date') or None
    if start_date and due_date and due_date < start_date:
        messages.error(request, 'Due date cannot be before start date.')
        return redirect(reverse('dashboard:admin') + '?panel=milestones')
    m.title       = request.POST.get('title', m.title).strip()
    m.description = request.POST.get('description', '').strip()
    m.start_date  = start_date
    m.due_date    = due_date
    m.weight      = int(request.POST.get('weight') or m.weight)
    m.order       = int(request.POST.get('order') or m.order)
    # Split settings (only update if included in this form submission)
    if 'has_split' in request.POST or 'has_split_present' in request.POST:
        m.has_split = request.POST.get('has_split') == 'on'
    if 'report_weight' in request.POST:
        m.report_weight       = max(0, min(100, int(request.POST.get('report_weight') or m.report_weight)))
        m.presentation_weight = max(0, min(100, int(request.POST.get('presentation_weight') or m.presentation_weight)))
    m.save()
    messages.success(request, f'Milestone "{m.title}" updated.')
    return redirect(reverse('dashboard:admin') + '?panel=milestones')


@login_required
@require_POST
def admin_delete_milestone(request, milestone_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    m = get_object_or_404(Milestone, pk=milestone_id)
    title = m.title
    m.delete()
    messages.success(request, f'Milestone "{title}" deleted.')
    return redirect(reverse('dashboard:admin') + '?panel=milestones')


# ════════════════════════════════════════════════════════════════════════════════
#  GRADE ADMIN VIEWS
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_update_grade_weights(request):
    """Update milestone weights and split settings from the Grades panel."""
    if not _require_admin(request):
        return redirect('dashboard:index')
    for m in Milestone.objects.filter(is_active=True):
        changed = False
        w = request.POST.get(f'weight_{m.pk}', '').strip()
        if w:
            try:
                m.weight = max(0, min(100, int(w)))
                changed  = True
            except ValueError:
                pass
        # Checkbox: present == checked, absent == unchecked
        has_split = request.POST.get(f'has_split_{m.pk}') == 'on'
        if has_split != m.has_split:
            m.has_split = has_split
            changed     = True
        if has_split:
            rw_raw = request.POST.get(f'report_weight_{m.pk}', '').strip()
            pw_raw = request.POST.get(f'presentation_weight_{m.pk}', '').strip()
            try:
                rw = max(0, min(100, int(rw_raw))) if rw_raw else m.report_weight
                pw = max(0, min(100, int(pw_raw))) if pw_raw else m.presentation_weight
            except ValueError:
                rw, pw = m.report_weight, m.presentation_weight
            if rw + pw != 100:
                messages.error(
                    request,
                    f'"{m.title}" split weights must add up to 100% '
                    f'(Report {rw}% + Presentation {pw}% = {rw + pw}%). '
                    f'Nothing was saved for this milestone\'s split.'
                )
                # Skip saving split for this milestone; still save overall weight
            else:
                m.report_weight       = rw
                m.presentation_weight = pw
                changed               = True
        if changed:
            m.save()

    total = sum(m.weight for m in Milestone.objects.filter(is_active=True))
    if total != 100:
        messages.warning(request, f'Milestone weights saved — total is {total}% (should be 100%).')
    else:
        messages.success(request, 'Weights saved. Total is 100%.')
    return redirect(reverse('dashboard:admin') + '?panel=grades')


@login_required
@require_POST
def admin_save_all_grades(request):
    """Bulk save grades from the grade-sheet table. Field names: grade-{pid}-{mid}-{comp}."""
    if not _require_admin(request):
        return redirect('dashboard:index')
    saved  = 0
    skipped = 0
    now = timezone.now()
    for key, val in request.POST.items():
        if not key.startswith('grade-'):
            continue
        parts = key.split('-', 3)          # ['grade', pid, mid, comp]
        if len(parts) != 4:
            continue
        _, pid_s, mid_s, comp = parts
        try:
            project   = Project.objects.get(pk=int(pid_s))
            milestone = Milestone.objects.get(pk=int(mid_s))
        except (ValueError, Project.DoesNotExist, Milestone.DoesNotExist):
            skipped += 1
            continue
        if comp not in ('single', 'report', 'presentation'):
            skipped += 1
            continue
        score = None
        raw = val.strip()
        if raw:
            try:
                score = float(raw)
                if score < 0 or score > 100:
                    skipped += 1
                    continue
            except ValueError:
                skipped += 1
                continue
        ProjectGrade.objects.update_or_create(
            project=project, milestone=milestone, component=comp,
            defaults={'score': score, 'graded_by': request.user, 'graded_at': now},
        )
        saved += 1

    if skipped:
        messages.warning(request, f'{saved} grade(s) saved. {skipped} value(s) skipped (invalid).')
    else:
        messages.success(request, f'{saved} grade(s) saved.')
    return redirect(reverse('dashboard:admin') + '?panel=grades')


# ════════════════════════════════════════════════════════════════════════════════
#  SUBMISSION ADMIN VIEWS
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_grade_submission(request, submission_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    sub   = get_object_or_404(Submission, pk=submission_id)
    grade = request.POST.get('grade', '').strip()
    sub.grade = grade if grade else None
    sub.save()
    messages.success(request, f'Grade saved for submission #{sub.pk}.')
    return redirect(reverse('dashboard:admin') + '?panel=submissions')


@login_required
@require_POST
def admin_submission_status(request, submission_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    sub    = get_object_or_404(Submission, pk=submission_id)
    status = request.POST.get('status', '').strip()
    if status in dict(Submission.STATUS):
        sub.status = status
        sub.save()
        messages.success(request, f'Submission marked as "{sub.get_status_display()}".')
    else:
        messages.error(request, 'Invalid status.')
    return redirect(reverse('dashboard:admin') + '?panel=submissions')


@login_required
@require_POST
def admin_delete_submission(request, submission_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    sub = get_object_or_404(Submission, pk=submission_id)
    sub.delete()
    messages.success(request, 'Submission deleted.')
    return redirect(reverse('dashboard:admin') + '?panel=submissions')


# ════════════════════════════════════════════════════════════════════════════════
#  STUDENT — SUBMIT MILESTONE
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def student_submit_milestone(request, milestone_id):
    if not request.user.is_student():
        return redirect('dashboard:index')

    milestone = get_object_or_404(Milestone, pk=milestone_id, is_active=True)

    # Must be in an active team
    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership:
        messages.error(request, 'You must be in an active team to submit.')
        return redirect('dashboard:student')

    # Only the team leader can submit
    if membership.role != 'leader':
        messages.error(request, 'Only the team leader can submit deliverables.')
        return redirect('dashboard:student')

    # Team must have a project
    project = getattr(membership.team, 'project', None)
    if not project:
        messages.error(request, 'Your team does not have a project yet.')
        return redirect('dashboard:student')

    # Milestone must have started (start_date <= today)
    today = timezone.now().date()
    if milestone.start_date and milestone.start_date > today:
        messages.error(request, f'"{milestone.title}" has not started yet (starts {milestone.start_date}).')
        return redirect('dashboard:student')

    files = request.FILES.getlist('files')
    if not files:
        messages.error(request, 'Please attach at least one file.')
        return redirect('dashboard:student')

    sub = Submission.objects.create(
        milestone=milestone,
        project=project,
        submitted_by=request.user,
        notes=request.POST.get('notes', '').strip(),
        status='pending',
    )
    for f in files:
        SubmissionFile.objects.create(
            submission=sub,
            file=f,
            file_name=f.name,
            file_type=f.content_type or '',
            file_size=f.size,
        )

    messages.success(request, f'Submitted "{milestone.title}" (v{sub.version}).')
    return redirect('dashboard:student')
