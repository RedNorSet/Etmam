from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

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
    reviewed    = Project.objects.filter(reviewer=user).select_related('team') if user.can_review else []
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
    teams       = Team.objects.filter(is_active=True).select_related('project').order_by('-created_at')
    projects    = Project.objects.select_related('team', 'supervisor', 'reviewer').order_by('-created_at')
    milestones  = Milestone.objects.select_related('project').order_by('due_date')
    submissions = Submission.objects.filter(is_latest=True).select_related('milestone', 'submitted_by').order_by('-submitted_at')
    grades      = Grade.objects.select_related('project').order_by('-graded_at')

    return render(request, 'dashboard/admin.html', {
        'total_teams':       total_teams,
        'total_students':    total_students,
        'total_supervisors': total_supervisors,
        'total_reviewers':   total_reviewers,
        'overdue':           overdue,
        'pending_grades':    pending_grades,
        'students':          students,
        'staff':             staff,
        'admins':            admins,
        'teams':             teams,
        'projects':          projects,
        'milestones':        milestones,
        'submissions':       submissions,
        'grades':            grades,
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
    projects      = Project.objects.filter(reviewer=user).select_related('team', 'supervisor')
    grades        = Grade.objects.filter(project__reviewer=user).select_related('project')
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')[:15]
    unread_count  = Notification.objects.filter(recipient=user, is_read=False).count()

    return render(request, 'dashboard/reviewer.html', {
        'projects':      projects,
        'grades':        grades,
        'notifications': notifications,
        'unread_count':  unread_count,
    })
