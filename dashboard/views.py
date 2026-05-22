from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from accounts.models import User
from teams.models import Team, TeamMember
from projects.models import Project, SupervisionRequest
from milestones.models import Milestone
from submissions.models import Submission
from reviews.models import Grade
from notifications.models import Notification
from meetings.models import Meeting


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
    membership  = TeamMember.objects.filter(user=user).select_related('team').first()
    team        = membership.team if membership else None
    team_members = TeamMember.objects.filter(team=team).select_related('user') if team else []

    project    = getattr(team, 'project', None) if team else None
    milestones = project.milestones.all() if project else []

    notifications  = Notification.objects.filter(recipient=user).order_by('-created_at')[:15]
    unread_count   = Notification.objects.filter(recipient=user, is_read=False).count()
    upcoming       = Meeting.objects.filter(project=project, datetime__gte=timezone.now()).order_by('datetime')[:5] if project else []
    past_meetings  = Meeting.objects.filter(project=project, datetime__lt=timezone.now()).order_by('-datetime')[:5] if project else []
    supervisors    = User.objects.filter(role='supervisor', available=True).order_by('full_name')
    pending_request = SupervisionRequest.objects.filter(team=team, status='pending').first() if team else None

    return render(request, 'dashboard/student.html', {
        'membership':     membership,
        'team':           team,
        'team_members':   team_members,
        'project':        project,
        'milestones':     milestones,
        'notifications':  notifications,
        'unread_count':   unread_count,
        'upcoming':       upcoming,
        'past_meetings':  past_meetings,
        'supervisors':    supervisors,
        'pending_request': pending_request,
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

    return render(request, 'dashboard/supervisor.html', {
        'supervised':    supervised,
        'reviewed':      reviewed,
        'pending_req':   pending_req,
        'upcoming':      upcoming,
        'past':          past,
        'notifications': notifications,
        'unread_count':  unread_count,
    })


@login_required
def admin_dashboard(request):
    total_teams       = Team.objects.count()
    total_students    = User.objects.filter(role='student').count()
    total_supervisors = User.objects.filter(role='supervisor').count()
    total_reviewers   = User.objects.filter(role='reviewer').count()
    overdue           = Milestone.objects.filter(due_date__lt=timezone.now().date(), status__in=['pending', 'in_progress']).count()
    pending_grades    = Grade.objects.filter(final_score__isnull=True).count()

    users       = User.objects.order_by('-date_joined')
    teams       = Team.objects.select_related('project').order_by('-created_at')
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
        'users':             users,
        'teams':             teams,
        'projects':          projects,
        'milestones':        milestones,
        'submissions':       submissions,
        'grades':            grades,
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
