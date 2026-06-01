import uuid
import re as _re

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
from projects.models import Project, SupervisionRequest, SystemConfig, ArchiveLink
from milestones.models import Milestone, ProjectGrade, Task
from submissions.models import Submission, SubmissionFile, ReviewerGrade
from reviews.models import Grade
from notifications.models import Notification
from meetings.models import Meeting, MeetingParticipant, RescheduleProposal
from meetings.views import eligible_participants, eligible_teams_for_supervisor


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


def _refresh_project_statuses():
    """Recalculate and bulk-update project statuses. Deactivates students on newly-completed projects."""
    config  = SystemConfig.get()
    today   = timezone.now().date()

    all_ms   = list(Milestone.objects.filter(is_active=True).order_by('order', 'due_date'))
    last_ms  = all_ms[-1] if all_ms else None
    last_due = last_ms.due_date if last_ms else None
    last_passed = bool(last_due and today > last_due)
    all_ms_ids  = {m.pk for m in all_ms}

    if not all_ms_ids:
        return

    sub_map = {}
    for s in Submission.objects.filter(is_latest=True).values('project_id', 'milestone_id'):
        sub_map.setdefault(s['project_id'], set()).add(s['milestone_id'])

    to_update       = []
    newly_completing = []
    for project in Project.objects.filter(team__is_active=True):   # all projects, including rejected
        # Never downgrade a completed project — once completed it stays in the archive
        if project.status == 'completed':
            continue
        all_submitted = all_ms_ids.issubset(sub_map.get(project.pk, set()))
        if last_passed:
            new_status = 'completed' if all_submitted else 'needs_review'
        elif config.phase >= 2:
            new_status = 'active'
        else:
            new_status = 'in_progress'
        if project.status != new_status:
            if new_status == 'completed':
                newly_completing.append(project)
            project.status = new_status
            to_update.append(project)

    if to_update:
        Project.objects.bulk_update(to_update, ['status'])

    # Deactivate students whose project just became completed
    if newly_completing:
        team_ids = [p.team_id for p in newly_completing]
        user_ids = list(
            TeamMember.objects.filter(
                team_id__in=team_ids, status='active',
                user__role='student', user__is_active=True,
            ).values_list('user_id', flat=True)
        )
        if user_ids:
            User.objects.filter(pk__in=user_ids).update(is_active=False)


def _auto_zero_missed_submissions():
    """Create ProjectGrade(score=0) for any active project that missed an overdue milestone."""
    from milestones.models import ProjectGrade
    today = timezone.now().date()
    overdue_ms = list(Milestone.objects.filter(is_active=True, due_date__lt=today))
    if not overdue_ms:
        return
    active_projects = list(Project.objects.filter(team__is_active=True))
    if not active_projects:
        return
    submitted_pairs = set(
        Submission.objects.filter(is_latest=True)
        .values_list('project_id', 'milestone_id')
    )
    for ms in overdue_ms:
        components = ['report', 'presentation'] if ms.has_split else ['single']
        for project in active_projects:
            if (project.pk, ms.pk) in submitted_pairs:
                continue
            for comp in components:
                ProjectGrade.objects.get_or_create(
                    project=project, milestone=ms, component=comp,
                    defaults={'score': 0},
                )


def _get_archive_data():
    final_milestone = Milestone.objects.filter(order=5, is_active=True).first()
    projects = (Project.objects
        .filter(status='completed', hide_from_archive=False)
        .select_related('team', 'supervisor')
        .prefetch_related('team__memberships__user', 'archive_links')
        .order_by('-approved_at', '-created_at'))
    archive_data = []
    for p in projects:
        final_files = []
        if final_milestone:
            sub = (Submission.objects
                .filter(project=p, milestone=final_milestone, is_latest=True)
                .prefetch_related('files').first())
            if sub:
                final_files = list(sub.files.all())
        active_members = [m for m in p.team.memberships.all() if m.status == 'active']
        archive_data.append({
            'project':     p,
            'members':     active_members,
            'final_files': final_files,
            'links':       list(p.archive_links.all()),
        })
    return archive_data


@login_required
def student_dashboard(request):
    if not request.user.is_student():
        return redirect('dashboard:index')
    user        = request.user
    membership     = TeamMember.objects.filter(user=user, status='active').select_related('team').first()
    team           = membership.team if membership else None
    team_members   = TeamMember.objects.filter(team=team, status__in=['active','pending']).select_related('user').order_by('status') if team else []
    pending_invite = TeamMember.objects.filter(user=user, status='pending').select_related('team').first()

    project    = getattr(team, 'project', None) if team else None

    # Global milestones zipped with this team's latest submission per milestone
    global_milestones_qs = Milestone.objects.filter(is_active=True).order_by('order', 'due_date')
    if project:
        sub_map = {
            s.milestone_id: s
            for s in Submission.objects.filter(project=project, is_latest=True)
                               .select_related('milestone', 'submitted_by')
                               .prefetch_related('files', 'reviewer_grades')
        }
        task_map = {}
        for t in Task.objects.filter(project=project).select_related('assigned_to', 'created_by'):
            task_map.setdefault(t.milestone_id, []).append(t)
        num_reviewers = project.reviewers.count()
    else:
        sub_map       = {}
        task_map      = {}
        num_reviewers = 0
    global_milestones = []
    running_total  = 0.0
    graded_weight  = 0
    for m in global_milestones_qs:
        sub   = sub_map.get(m.pk)
        tasks = task_map.get(m.pk, [])

        all_graded = False
        if sub and project:
            rgs = list(sub.reviewer_grades.all())
            if m.has_split:
                sup_done = (sub.supervisor_report_grade is not None and
                            sub.supervisor_presentation_grade is not None)
                rev_done = len({rg.reviewer_id for rg in rgs
                                if rg.component == 'report' and rg.grade is not None})
            else:
                sup_done = sub.supervisor_grade is not None
                rev_done = len({rg.reviewer_id for rg in rgs
                                if rg.component == 'single' and rg.grade is not None})
            all_graded = sup_done and rev_done >= num_reviewers

        if all_graded and sub and sub.grade is not None and m.weight:
            running_total += float(sub.grade) * (m.weight / 100)
            graded_weight += m.weight

        global_milestones.append({
            'milestone':  m,
            'submission': sub,
            'tasks':      tasks,
            'task_total': len(tasks),
            'task_done':  sum(1 for t in tasks if t.status == 'done'),
            'all_graded': all_graded,
        })

    notifications  = Notification.objects.filter(recipient=user).order_by('-created_at')[:15]
    unread_count   = Notification.objects.filter(recipient=user, is_read=False).count()
    upcoming       = Meeting.objects.filter(project=project, datetime__gte=timezone.now()).order_by('datetime')[:5] if project else []
    past_meetings  = Meeting.objects.filter(project=project, datetime__lt=timezone.now()).order_by('-datetime')[:5] if project else []
    supervisors_qs = User.objects.filter(role='supervisor', available=True)
    if user.department:
        supervisors_qs = supervisors_qs.filter(department=user.department)
    supervisors    = supervisors_qs.order_by('full_name')
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
        'running_total':        round(running_total, 1),
        'graded_weight':        graded_weight,
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
        'archive_data':         _get_archive_data(),
        'current_phase':        SystemConfig.get().phase,
    })


@login_required
def supervisor_dashboard(request):
    if not request.user.is_supervisor() and not request.user.is_reviewer():
        return redirect('dashboard:index')
    user        = request.user
    supervised_qs = Project.objects.filter(supervisor=user).exclude(status='completed').select_related('team').prefetch_related('team__memberships__user', 'reviewers')
    reviewed_qs   = Project.objects.filter(reviewers=user).exclude(status='completed').select_related('team').prefetch_related('team__memberships__user')

    global_milestones = Milestone.objects.filter(is_active=True).order_by('order', 'due_date')
    global_ms_list    = list(global_milestones)

    supervised_list = list(supervised_qs)
    reviewed_list   = list(reviewed_qs)

    def _build_data(proj_list):
        result = []
        for proj in proj_list:
            members = [m for m in proj.team.memberships.all() if m.status == 'active']
            subs_qs = list(
                Submission.objects.filter(project=proj, is_latest=True)
                .select_related('milestone')
                .prefetch_related('files', 'reviewer_grades')
            )
            sub_map = {s.milestone_id: s for s in subs_qs}
            num_reviewers = proj.reviewers.count()
            milestone_items = []
            for m in global_ms_list:
                sub = sub_map.get(m.pk)
                all_graded = False
                if sub:
                    rgs = list(sub.reviewer_grades.all())
                    if m.has_split:
                        sup_done = (sub.supervisor_report_grade is not None and
                                    sub.supervisor_presentation_grade is not None)
                        rev_done = len({rg.reviewer_id for rg in rgs
                                        if rg.component == 'report' and rg.grade is not None})
                    else:
                        sup_done = sub.supervisor_grade is not None
                        rev_done = len({rg.reviewer_id for rg in rgs
                                        if rg.component == 'single' and rg.grade is not None})
                    all_graded = sup_done and rev_done >= num_reviewers
                milestone_items.append({'milestone': m, 'submission': sub, 'all_graded': all_graded})

            needs_my_grade = any(
                ms['submission'] and (
                    (ms['milestone'].has_split and (
                        ms['submission'].supervisor_report_grade is None or
                        ms['submission'].supervisor_presentation_grade is None
                    )) or
                    (not ms['milestone'].has_split and ms['submission'].supervisor_grade is None)
                )
                for ms in milestone_items
            )
            result.append({
                'project':        proj,
                'members':        members,
                'milestones':     milestone_items,
                'needs_my_grade': needs_my_grade,
            })
        return result

    supervised_data = _build_data(supervised_list)

    # For reviewed projects, also pass this reviewer's per-component grades
    reviewed_data = []
    for proj in reviewed_list:
        members = [m for m in proj.team.memberships.all() if m.status == 'active']
        subs_qs = list(
            Submission.objects.filter(project=proj, is_latest=True)
            .select_related('milestone')
            .prefetch_related('files', 'reviewer_grades')
        )
        sub_map = {s.milestone_id: s for s in subs_qs}
        num_rev = proj.reviewers.count()
        # Build {submission_id: {component: ReviewerGrade}} for THIS reviewer
        rg_by_sub = {}
        for rg in ReviewerGrade.objects.filter(submission__in=subs_qs, reviewer=user):
            rg_by_sub.setdefault(rg.submission_id, {})[rg.component] = rg
        milestones_data = []
        for m in global_ms_list:
            sub = sub_map.get(m.pk)
            all_graded = False
            if sub:
                all_rgs = list(sub.reviewer_grades.all())
                if m.has_split:
                    sup_done = (sub.supervisor_report_grade is not None and
                                sub.supervisor_presentation_grade is not None)
                    rev_done = len({rg.reviewer_id for rg in all_rgs
                                    if rg.component == 'report' and rg.grade is not None})
                else:
                    sup_done = sub.supervisor_grade is not None
                    rev_done = len({rg.reviewer_id for rg in all_rgs
                                    if rg.component == 'single' and rg.grade is not None})
                all_graded = sup_done and rev_done >= num_rev
            milestones_data.append({
                'milestone':          m,
                'submission':         sub,
                'my_reviewer_grades': rg_by_sub.get(sub.pk, {}) if sub else {},
                'all_graded':         all_graded,
            })

        needs_my_grade = any(
            ms['submission'] and (
                (ms['milestone'].has_split and (
                    'report' not in rg_by_sub.get(ms['submission'].pk, {}) or
                    rg_by_sub[ms['submission'].pk]['report'].grade is None
                )) or
                (not ms['milestone'].has_split and (
                    'single' not in rg_by_sub.get(ms['submission'].pk, {}) or
                    rg_by_sub[ms['submission'].pk]['single'].grade is None
                ))
            )
            for ms in milestones_data
        )
        reviewed_data.append({
            'project':        proj,
            'members':        members,
            'milestones':     milestones_data,
            'needs_my_grade': needs_my_grade,
        })

    # Submissions section: milestone-centric, spanning supervised + reviewed projects
    supervised_pks = {p.pk for p in supervised_list}
    all_proj_list  = supervised_list + reviewed_list
    all_proj_pks   = [p.pk for p in all_proj_list]

    all_subs = list(
        Submission.objects.filter(project_id__in=all_proj_pks, is_latest=True)
        .select_related('project__team', 'submitted_by', 'supervisor_graded_by', 'reviewer_graded_by')
        .prefetch_related('files')
    )
    sub_lookup = {(s.project_id, s.milestone_id): s for s in all_subs}

    submissions_sections = []
    for ms in global_ms_list:
        rows = []
        for proj in all_proj_list:
            sub      = sub_lookup.get((proj.pk, ms.pk))
            is_sup   = proj.pk in supervised_pks
            rows.append({'project': proj, 'submission': sub, 'is_supervised': is_sup})
        submitted_count = sum(1 for r in rows if r['submission'])
        graded_count    = sum(
            1 for r in rows if r['submission'] and (
                (r['is_supervised'] and r['submission'].supervisor_grade is not None) or
                (not r['is_supervised'] and ReviewerGrade.objects.filter(submission=r['submission'], reviewer=user).exists())
            )
        )
        submissions_sections.append({
            'milestone':       ms,
            'rows':            rows,
            'submitted_count': submitted_count,
            'total_count':     len(all_proj_list),
            'graded_count':    graded_count,
        })

    pending_subs_count = sum(
        1 for s in all_subs
        if s.project_id in supervised_pks and s.supervisor_grade is None
    )

    supervised = supervised_list
    reviewed   = reviewed_list
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
        'supervised_data':      supervised_data,
        'reviewed':             reviewed,
        'reviewed_data':        reviewed_data,
        'submissions_sections': submissions_sections,
        'pending_subs_count':   pending_subs_count,
        'pending_req':          pending_req,
        'upcoming':             upcoming,
        'past':                 past,
        'notifications':        notifications,
        'unread_count':         unread_count,
        'eligible_participants':eligible_participants(user),
        'eligible_teams':       eligible_teams_for_supervisor(user) if user.is_supervisor() else [],
        'pending_invitations':  pending_invitations,
        'pending_proposals':    pending_proposals,
        'archive_data':         _get_archive_data(),
        'current_phase':        SystemConfig.get().phase,
    })


@login_required
def admin_dashboard(request):
    if not request.user.is_administrator():
        return redirect('dashboard:index')
    # Auto-trigger Phase 2 if scheduled date has been reached
    _cfg = SystemConfig.get()
    if (_cfg.phase == 1 and _cfg.phase2_start_date and
            timezone.now().date() >= _cfg.phase2_start_date):
        _r = _execute_phase2_switch(request.user)
        if _r['no_sup_projects']:
            messages.warning(request, f'{_r["no_sup_projects"]} project(s) could not be auto-assigned a supervisor.')
        messages.success(
            request,
            f'⚡ Phase 2 auto-activated (scheduled {_cfg.phase2_start_date}). '
            f'{_r["auto_teams"]} auto team(s) created, '
            f'{_r["assigned_count"]} supervisor(s) assigned.'
        )

    # Recalculate project statuses on every admin page load
    _refresh_project_statuses()
    _auto_zero_missed_submissions()

    total_students    = User.objects.filter(role='student').count()
    total_supervisors = User.objects.filter(role='supervisor').count()
    total_reviewers   = User.objects.filter(role='reviewer').count()

    from django.db.models import Case, When, IntegerField as _IntField
    students = (User.objects.filter(role='student')
                .annotate(_inactive=Case(When(is_active=False, then=1), default=0, output_field=_IntField()))
                .order_by('_inactive', 'full_name', 'username'))
    staff    = User.objects.filter(role__in=['supervisor', 'reviewer']).order_by('full_name', 'username')
    admins   = User.objects.filter(role='administrator').order_by('full_name', 'username')

    # All teams except those whose project is already completed (those live in Archive)
    raw_teams   = (Team.objects
                   .exclude(project__status='completed')
                   .select_related('project__supervisor')
                   .prefetch_related('memberships__user', 'project__reviewers')
                   .order_by('-created_at'))
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
        is_overdue = bool(m.due_date and m.due_date < timezone.now().date())
        submissions_data.append({
            'milestone':       m,
            'submissions':     subs,
            'not_submitted':   not_submitted,
            'submitted_count': len(submitted_project_ids),
            'total_count':     len(active_projects),
            'is_overdue':      is_overdue,
        })

    overdue = sum(len(item['not_submitted']) for item in submissions_data if item['is_overdue'])

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

    # Count grading slots that have a submission but no grade yet
    submitted_pairs = set(
        Submission.objects.filter(project__in=grade_projects, is_latest=True)
        .values_list('project_id', 'milestone_id')
    )
    pending_grades = 0
    for _col in grade_columns:
        for _gp in grade_projects:
            if (_gp.pk, _col['milestone'].pk) in submitted_pairs:
                _key = (_gp.pk, _col['milestone'].pk, _col['component'])
                _g   = grade_map.get(_key)
                if _g is None or _g.score is None:
                    pending_grades += 1

    # Supervisors and reviewers for assignment dropdowns
    all_supervisors = User.objects.filter(role='supervisor', is_active=True, available=True).order_by('full_name', 'username')
    all_reviewers   = User.objects.filter(can_review=True, is_active=True).order_by('full_name', 'username')

    dissolved_count = Team.objects.filter(is_active=False).count()

    # Archive: completed projects with team members, final submitted files, and links
    _arc_final_ms = Milestone.objects.filter(order=5, is_active=True).first()
    archive_qs = (
        Project.objects.filter(status='completed')
        .select_related('team', 'supervisor')
        .prefetch_related('team__memberships__user', 'reviewers', 'archive_links')
        .order_by('-created_at')
    )
    archive_data = []
    for ap in archive_qs:
        active_members = [m for m in ap.team.memberships.all() if m.status == 'active']
        final_files = []
        if _arc_final_ms:
            _sub = (Submission.objects
                .filter(project=ap, milestone=_arc_final_ms, is_latest=True)
                .prefetch_related('files')
                .first())
            if _sub:
                final_files = list(_sub.files.all())
        archive_data.append({
            'project':     ap,
            'members':     active_members,
            'final_files': final_files,
            'links':       list(ap.archive_links.all()),
        })

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
        'system_config':          SystemConfig.get(),
        'archive_data':           archive_data,
        'first_milestone':        Milestone.objects.order_by('order', 'id').first(),
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
    if not request.user.is_reviewer() and not request.user.is_administrator():
        return redirect('dashboard:index')
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


# ════════════════════════════════════════════════════════════════════════════════
#  STUDENT — TASK MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def student_create_task(request, milestone_id):
    if not request.user.is_student():
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership or membership.role != 'leader':
        messages.error(request, 'Only the team leader can create tasks.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    project = getattr(membership.team, 'project', None)
    if not project:
        messages.error(request, 'Your team does not have a project yet.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    milestone = get_object_or_404(Milestone, pk=milestone_id, is_active=True)
    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'Task title is required.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    assigned_id = request.POST.get('assigned_to', '').strip()
    try:
        assigned_to = User.objects.get(pk=int(assigned_id))
    except (User.DoesNotExist, ValueError, TypeError):
        messages.error(request, 'Please select a valid team member.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    if not TeamMember.objects.filter(team=membership.team, user=assigned_to, status='active').exists():
        messages.error(request, 'You can only assign tasks to active team members.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    Task.objects.create(
        project=project,
        milestone=milestone,
        title=title,
        description=request.POST.get('description', '').strip(),
        assigned_to=assigned_to,
        created_by=request.user,
        due_date=request.POST.get('due_date') or None,
    )

    if assigned_to != request.user:
        Notification.objects.create(
            recipient=assigned_to,
            type='general',
            title=f'Task Assigned — {milestone.title}',
            message=f'{request.user.full_name or request.user.username} assigned you: "{title}" for "{milestone.title}".',
        )

    messages.success(request, 'Task created.')
    return redirect(reverse('dashboard:student') + '#sec-milestones')


@login_required
@require_POST
def student_update_task(request, task_id):
    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership:
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    task = get_object_or_404(Task, pk=task_id, project__team=membership.team)
    if task.assigned_to != request.user and membership.role != 'leader':
        messages.error(request, 'You cannot update this task.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    status = request.POST.get('status', '').strip()
    if status in dict(Task.STATUS):
        task.status = status
        task.save()
    return redirect(reverse('dashboard:student') + '#sec-milestones')


@login_required
@require_POST
def student_delete_task(request, task_id):
    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership or membership.role != 'leader':
        messages.error(request, 'Only the team leader can delete tasks.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')

    task = get_object_or_404(Task, pk=task_id, project__team=membership.team)
    task.delete()
    return redirect(reverse('dashboard:student') + '#sec-milestones')


@login_required
@require_POST
def student_update_task_description(request, task_id):
    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership or membership.role != 'leader':
        messages.error(request, 'Only the team leader can edit task descriptions.')
        return redirect(reverse('dashboard:student') + '#sec-milestones')
    task = get_object_or_404(Task, pk=task_id, project__team=membership.team)
    task.description = request.POST.get('description', '').strip()
    task.save(update_fields=['description'])
    return redirect(reverse('dashboard:student') + '#sec-milestones')


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
    existing = team.memberships.filter(status='active').select_related('user').first()
    if existing:
        if existing.user.gender and (student.gender or '') != existing.user.gender:
            messages.error(request, f'Cannot add {student.full_name or username}: this is a {existing.user.gender} team.')
            return _admin_redirect(team_id)
        if existing.user.department and student.department != existing.user.department:
            messages.error(request, f'Cannot add {student.full_name or username}: team department is "{existing.user.department}" but student is in "{student.department or "unset"}".')
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
    Project.objects.create(team=team, title=title, description=description, status='active')
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

    # Supervisor assignment from the archive panel edit form
    if request.POST.get('source') == 'archive':
        sup_raw = request.POST.get('supervisor_id', '').strip()
        if sup_raw == '0':
            project.supervisor = None
        elif sup_raw:
            try:
                project.supervisor = User.objects.get(pk=int(sup_raw), role='supervisor')
            except (User.DoesNotExist, ValueError):
                pass

    project.save()
    messages.success(request, f'Project "{project.title}" updated.')
    if request.POST.get('source') == 'archive':
        return redirect(reverse('dashboard:admin') + '?panel=archive')
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
    # Block unavailable supervisors
    if not supervisor.available:
        messages.error(request, f'{supervisor.full_name or supervisor.username} is marked as unavailable and cannot be assigned.')
        return _admin_redirect(project.team.pk)
    # Block if supervisor is at capacity (unless they're already assigned to this project)
    if project.supervisor != supervisor and supervisor.is_at_capacity():
        _lim = supervisor.max_teams_supervise
        messages.error(request, f'{supervisor.full_name or supervisor.username} has reached their supervision limit ({_lim} team{"s" if _lim != 1 else ""}).')
        return _admin_redirect(project.team.pk)

    old_supervisor = project.supervisor
    project.supervisor = supervisor
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
    if reviewer.is_at_review_capacity():
        messages.error(request, f'{reviewer.full_name or reviewer.username} has reached their review limit ({reviewer.max_teams_review} teams).')
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
    team_dept = None
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
        if team_dept is None:
            team_dept = student.department
        elif student.department != team_dept:
            skipped.append(f'{student.full_name or username} (department "{student.department}" ≠ team "{team_dept}")')
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
    # archives_archivedproject may not exist yet (archives app not yet deployed).
    project_ids = list(Project.objects.filter(team__in=dissolved_teams).values_list('pk', flat=True))
    if project_ids and 'archives_archivedproject' in connection.introspection.table_names():
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

    # If searching within an existing team, restrict to that team's gender AND department
    gender_filter = None
    dept_filter   = None
    raw_team_id = request.GET.get('team_id')
    if raw_team_id:
        try:
            first_member = (
                TeamMember.objects
                .filter(team_id=int(raw_team_id), status='active')
                .select_related('user')
                .first()
            )
            if first_member:
                if first_member.user.gender:
                    gender_filter = first_member.user.gender
                if first_member.user.department:
                    dept_filter = first_member.user.department
        except (ValueError, TypeError):
            pass

    # Build mapping: user_id → team_name for already-assigned students
    assigned_map = {
        tm.user_id: tm.team.name
        for tm in TeamMember.objects.filter(status='active').select_related('team')
    }

    qs = (
        User.objects
        .filter(role='student', is_active=True)
        .filter(Q(full_name__icontains=q) | Q(username__icontains=q) | Q(student_id__icontains=q))
    )
    if gender_filter:
        qs = qs.filter(gender=gender_filter)
    if dept_filter:
        qs = qs.filter(department=dept_filter)
    qs = qs.order_by('full_name', 'username')[:15]

    data = [
        {
            'username':     s.username,
            'full_name':    s.full_name or '',
            'student_id':   s.student_id or '',
            'department':   s.department or '',
            'current_team': assigned_map.get(s.pk),
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
    m = Milestone(
        title=title,
        description=request.POST.get('description', '').strip(),
        start_date=start_date,
        due_date=due_date,
        weight=int(request.POST.get('weight') or 10),
        order=order,
        created_by=request.user,
    )
    guide_file = request.FILES.get('guide_file')
    if guide_file:
        m.guide_file = guide_file
    m.save()
    messages.success(request, f'Milestone "{title}" created.')
    _total_w = sum(Milestone.objects.filter(is_active=True).values_list('weight', flat=True))
    if _total_w != 100:
        messages.warning(
            request,
            f'Reminder: milestone weights now total {_total_w}% — '
            f'please go to the Grades panel and adjust all weights so they add up to 100%.'
        )
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
    guide_file = request.FILES.get('guide_file')
    if guide_file:
        m.guide_file = guide_file
    elif request.POST.get('clear_guide_file'):
        m.guide_file = None
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
        messages.warning(request, f'{saved} grade(s) saved. {skipped} value(s) skipped — grades must be between 0 and 100.')
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
#  ARCHIVE
# ════════════════════════════════════════════════════════════════════════════════

@login_required
def archive_view(request):
    if request.user.role not in ['student', 'supervisor', 'administrator']:
        return redirect('dashboard:index')

    final_milestone = Milestone.objects.filter(order=5, is_active=True).first()

    projects = (Project.objects
        .filter(status='completed', hide_from_archive=False)
        .select_related('team', 'supervisor')
        .prefetch_related('team__memberships__user')
        .order_by('-approved_at', '-created_at'))

    archive_data = []
    for p in projects:
        final_files = []
        if final_milestone:
            sub = (Submission.objects
                .filter(project=p, milestone=final_milestone, is_latest=True)
                .prefetch_related('files')
                .first())
            if sub:
                final_files = list(sub.files.all())
        active_members = [m for m in p.team.memberships.all() if m.status == 'active']
        archive_data.append({'project': p, 'members': active_members, 'final_files': final_files})

    return render(request, 'dashboard/archive.html', {'archive_data': archive_data})


@login_required
@require_POST
def admin_toggle_archive(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id, status='completed')
    project.hide_from_archive = not project.hide_from_archive
    project.save(update_fields=['hide_from_archive'])
    action = 'hidden from' if project.hide_from_archive else 'visible in'
    messages.success(request, f'"{project.title}" is now {action} the archive.')
    return redirect(reverse('dashboard:admin') + '?panel=archive')


def _make_archive_user(full_name, email=''):
    """Create an inactive placeholder User with gap-filling username: Inactive1, Inactive2, …"""
    existing = set(
        User.objects.filter(username__regex=r'^Inactive\d+$')
        .values_list('username', flat=True)
    )
    n = 1
    while f'Inactive{n}' in existing:
        n += 1
    return User.objects.create(
        username=f'Inactive{n}',
        full_name=full_name,
        email=email,
        role='student',
        is_active=False,
    )


@login_required
@require_POST
def admin_create_archive_project(request):
    """Create a completed archive project with optional supervisor, members, and links."""
    if not _require_admin(request):
        return redirect('dashboard:index')

    title       = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    team_name   = request.POST.get('team_name', '').strip() or title

    if not title:
        messages.error(request, 'Project title is required.')
        return _archive_redirect()

    team    = Team.objects.create(name=team_name, created_by=request.user, is_active=True)
    project = Project.objects.create(
        team=team, title=title, description=description, status='completed',
    )

    # Supervisor
    sup_id = request.POST.get('supervisor_id', '').strip()
    if sup_id and sup_id != '0':
        try:
            project.supervisor = User.objects.get(pk=int(sup_id), role='supervisor')
            project.save(update_fields=['supervisor'])
        except (User.DoesNotExist, ValueError):
            pass

    # Members — parallel lists: member_names[], member_emails[]
    member_names  = request.POST.getlist('member_names')
    member_emails = request.POST.getlist('member_emails')
    added = 0
    for i, name in enumerate(member_names):
        name  = name.strip()
        email = member_emails[i].strip() if i < len(member_emails) else ''
        if not name:
            continue
        user = _make_archive_user(name, email)
        TeamMember.objects.create(
            team=team, user=user,
            role='leader' if added == 0 else 'member',
            status='active',
        )
        added += 1

    # Links — parallel lists: link_labels[], link_urls[]
    link_labels = request.POST.getlist('link_labels')
    link_urls   = request.POST.getlist('link_urls')
    for i, label in enumerate(link_labels):
        label = label.strip()
        url   = link_urls[i].strip() if i < len(link_urls) else ''
        if label and url:
            ArchiveLink.objects.create(project=project, label=label, url=url)

    messages.success(request, f'Archive project "{title}" added ({added} member(s)).')
    return _archive_redirect()


# ════════════════════════════════════════════════════════════════════════════════
#  PHASE MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

def _execute_phase2_switch(admin_user):
    """Run the full Phase 2 switch logic. Returns a stats dict. Does NOT save messages or redirect."""
    import random
    from collections import defaultdict

    config = SystemConfig.get()

    cancelled_invites = TeamMember.objects.filter(status='pending').count()
    TeamMember.objects.filter(status='pending').delete()

    students_in_teams = TeamMember.objects.filter(status='active').values_list('user_id', flat=True)
    teamless = list(
        User.objects.filter(role='student', is_active=True).exclude(pk__in=students_in_teams)
    )
    random.shuffle(teamless)

    buckets = defaultdict(list)
    for student in teamless:
        buckets[(student.gender or '', student.department or '')].append(student)

    fill_count = 0
    existing_teams = list(
        Team.objects.filter(is_active=True, auto_created=False)
        .prefetch_related('memberships__user').order_by('created_at')
    )
    for team in existing_teams:
        active_members = [m for m in team.memberships.all() if m.status == 'active']
        if len(active_members) >= 5:
            continue
        first = next(iter(active_members), None)
        if not first:
            continue
        key  = (first.user.gender or '', first.user.department or '')
        pool = buckets.get(key, [])
        needed = 5 - len(active_members)
        for student in pool[:needed]:
            if not TeamMember.objects.filter(team=team, user=student).exists():
                TeamMember.objects.create(team=team, user=student, role='member', status='active')
                fill_count += 1
        del pool[:needed]

    groups = []
    bucket_leftovers = {}
    for key, pool in buckets.items():
        gender = key[0]
        i = 0
        while len(pool) - i >= 5:
            groups.append((gender, pool[i:i + 5]))
            i += 5
        leftover = pool[i:]
        if len(leftover) >= 4:
            groups.append((gender, leftover))
            bucket_leftovers[key] = []
        else:
            bucket_leftovers[key] = leftover

    for i, (gender, group) in enumerate(groups):
        team_name = f'Auto Team {i + 1}'
        n = 1; base = team_name
        while Team.objects.filter(name=team_name).exists():
            team_name = f'{base} ({n})'; n += 1
        team = Team.objects.create(name=team_name, created_by=admin_user, is_active=True, auto_created=True)
        for j, student in enumerate(group):
            if not TeamMember.objects.filter(team=team, user=student).exists():
                TeamMember.objects.create(
                    team=team, user=student,
                    role='leader' if j == 0 else 'member', status='active',
                )
        Project.objects.create(
            team=team, title=f'{team_name} Project',
            description='Auto-generated project.', status='in_progress',
        )

    distributed_count = 0
    for (gender, dept), leftover_students in bucket_leftovers.items():
        if not leftover_students:
            continue
        target_teams = []
        for t in Team.objects.filter(is_active=True).prefetch_related('memberships__user'):
            active = [m for m in t.memberships.all() if m.status == 'active']
            if len(active) != 5:
                continue
            first = active[0]
            if (first.user.gender or '') != gender or (first.user.department or '') != dept:
                continue
            target_teams.append(t)
        for idx, student in enumerate(leftover_students):
            if idx >= len(target_teams):
                break
            if not TeamMember.objects.filter(team=target_teams[idx], user=student).exists():
                TeamMember.objects.create(team=target_teams[idx], user=student, role='member', status='active')
                distributed_count += 1

    unsupervised = list(
        Project.objects.filter(supervisor__isnull=True, team__is_active=True).select_related('team')
    )
    sups_by_gender = defaultdict(list)
    for sup in User.objects.filter(role='supervisor', is_active=True, available=True):
        sups_by_gender[sup.gender or ''].append(sup)

    counters = defaultdict(int)
    assigned_count = 0
    no_sup_projects = 0
    for project in unsupervised:
        first_member = project.team.memberships.filter(status='active').select_related('user').first()
        team_gender  = (first_member.user.gender or '') if first_member else ''
        sups = sups_by_gender.get(team_gender, [])
        if not sups:
            no_sup_projects += 1
            continue
        supervisor = sups[counters[team_gender] % len(sups)]
        counters[team_gender] += 1
        project.supervisor = supervisor
        project.auto_assigned_supervisor = True
        project.save(update_fields=['supervisor', 'auto_assigned_supervisor'])
        Notification.objects.create(
            recipient=supervisor, type='approval',
            title=f'Auto Supervisor Assignment — {project.team.name}',
            message=f'You have been automatically assigned as supervisor for "{project.title}" (Phase 2 activation).',
        )
        assigned_count += 1

    rev_pool = list(User.objects.filter(can_review=True, is_active=True))
    random.shuffle(rev_pool)
    rev_idx = 0
    reviewer_assigned_count = 0
    for project in Project.objects.filter(team__is_active=True).select_related('supervisor').prefetch_related('reviewers'):
        if not rev_pool:
            break
        current_reviewers = list(project.reviewers.all())
        if len(current_reviewers) >= 2:
            continue
        needed = 2 - len(current_reviewers)
        excluded_pks = {r.pk for r in current_reviewers}
        if project.supervisor:
            excluded_pks.add(project.supervisor.pk)
        added = 0
        pool_size = len(rev_pool)
        attempts = 0
        while added < needed and attempts < pool_size:
            candidate = rev_pool[rev_idx % pool_size]
            rev_idx += 1; attempts += 1
            if candidate.pk in excluded_pks:
                continue
            project.reviewers.add(candidate)
            excluded_pks.add(candidate.pk)
            Notification.objects.create(
                recipient=candidate, type='approval',
                title=f'Auto Reviewer Assignment — {project.team.name}',
                message=f'You have been automatically assigned as reviewer for "{project.title}" (Phase 2 activation).',
            )
            reviewer_assigned_count += 1
            added += 1

    config.phase = 2
    config.phase_switched_at = timezone.now()
    config.save()

    declined_count = SupervisionRequest.objects.filter(status='pending').update(status='declined')

    return {
        'cancelled_invites':     cancelled_invites,
        'fill_count':            fill_count,
        'auto_teams':            len(groups),
        'distributed_count':     distributed_count,
        'assigned_count':        assigned_count,
        'no_sup_projects':       no_sup_projects,
        'reviewer_assigned_count': reviewer_assigned_count,
        'declined_count':        declined_count,
    }


@login_required
@require_POST
def admin_switch_phase2(request):
    if not _require_admin(request):
        return redirect('dashboard:index')
    config = SystemConfig.get()
    if config.phase == 2:
        messages.warning(request, 'System is already in Phase 2.')
        return redirect(reverse('dashboard:admin') + '?panel=system')
    r = _execute_phase2_switch(request.user)
    if r['no_sup_projects']:
        messages.warning(request, f'{r["no_sup_projects"]} project(s) could not be assigned a supervisor — no matching-gender supervisor available.')
    messages.success(
        request,
        f'Switched to Phase 2. '
        f'{r["cancelled_invites"]} invite(s) cancelled, '
        f'{r["fill_count"]} student(s) added to existing teams, '
        f'{r["auto_teams"]} auto team(s) created, '
        f'{r["distributed_count"]} student(s) distributed, '
        f'{r["assigned_count"]} project(s) auto-assigned supervisors, '
        f'{r["reviewer_assigned_count"]} reviewer(s) assigned, '
        f'{r["declined_count"]} supervision request(s) declined.'
    )
    return redirect(reverse('dashboard:admin') + '?panel=system')


@login_required
@require_POST
def admin_revert_phase1(request):
    if not _require_admin(request):
        return redirect('dashboard:index')

    config = SystemConfig.get()
    if config.phase == 1:
        messages.warning(request, 'System is already in Phase 1.')
        return redirect(reverse('dashboard:admin') + '?panel=system')

    # Step 1 — remove auto-assigned supervisors
    unassigned = Project.objects.filter(auto_assigned_supervisor=True).update(
        supervisor=None, auto_assigned_supervisor=False
    )

    # Step 2 — dissolve auto-created teams (delete members, projects, then team)
    auto_teams = Team.objects.filter(auto_created=True)
    TeamMember.objects.filter(team__in=auto_teams).delete()
    Project.objects.filter(team__in=auto_teams).delete()
    dissolved_count = auto_teams.count()
    auto_teams.delete()

    # Step 3 — flip back to Phase 1; clear auto-trigger date so it doesn't re-fire
    config.phase = 1
    config.phase_switched_at = None
    config.phase2_start_date = None
    config.save()

    # Step 4 — re-open all declined supervision requests
    reopened = SupervisionRequest.objects.filter(status='declined').update(status='pending')

    messages.success(
        request,
        f'Reverted to Phase 1. '
        f'{unassigned} auto supervisor assignment(s) removed, '
        f'{dissolved_count} auto team(s) dissolved, '
        f'{reopened} supervision request(s) re-opened.'
    )
    return redirect(reverse('dashboard:admin') + '?panel=system')


# ════════════════════════════════════════════════════════════════════════════════
#  STUDENT — SUBMIT MILESTONE
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def student_submit_milestone(request, milestone_id):
    if not request.user.is_student():
        return redirect('dashboard:index')

    milestone = get_object_or_404(Milestone, pk=milestone_id, is_active=True)

    # Submissions only open in Phase 2
    _ms_url = reverse('dashboard:student') + '#sec-milestones'

    if SystemConfig.get().phase < 2:
        messages.error(request, 'Submissions are not open yet. The system is still in Phase 1 (team formation).')
        return redirect(_ms_url)

    # Must be in an active team
    membership = TeamMember.objects.filter(user=request.user, status='active').select_related('team').first()
    if not membership:
        messages.error(request, 'You must be in an active team to submit.')
        return redirect(_ms_url)

    # Only the team leader can submit
    if membership.role != 'leader':
        messages.error(request, 'Only the team leader can submit deliverables.')
        return redirect(_ms_url)

    # Team must have a project
    project = getattr(membership.team, 'project', None)
    if not project:
        messages.error(request, 'Your team does not have a project yet.')
        return redirect(_ms_url)

    if project.status == 'completed':
        messages.error(request, 'This project is completed. No further submissions are accepted.')
        return redirect(_ms_url)

    today = timezone.now().date()
    if milestone.start_date and milestone.start_date > today:
        messages.error(request, f'"{milestone.title}" has not started yet (starts {milestone.start_date}).')
        return redirect(_ms_url)
    if milestone.due_date and today > milestone.due_date:
        messages.error(request, f'The submission deadline for "{milestone.title}" has passed ({milestone.due_date}).')
        return redirect(_ms_url)

    files = request.FILES.getlist('files')
    if not files:
        messages.error(request, 'Please attach at least one file.')
        return redirect(_ms_url)

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

    # Notify supervisor and reviewers
    _sub_link = reverse('dashboard:supervisor') + '#sec-submissions'
    _recipients = []
    if project.supervisor:
        _recipients.append(project.supervisor)
    _recipients.extend(project.reviewers.all())
    for _r in _recipients:
        Notification.objects.create(
            recipient=_r,
            type='general',
            title=f'New submission: {milestone.title}',
            message=(
                f'{project.team.name} submitted "{milestone.title}" '
                f'(v{sub.version}). Please review and grade.'
            ),
            link=_sub_link,
        )

    return redirect(_ms_url)


# ════════════════════════════════════════════════════════════════════════════════
#  ARCHIVE — MEMBER MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

def _archive_redirect():
    return redirect(reverse('dashboard:admin') + '?panel=archive')


@login_required
@require_POST
def admin_archive_add_member(request, team_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    team      = get_object_or_404(Team, pk=team_id)
    username  = request.POST.get('username', '').strip()
    full_name = request.POST.get('full_name', '').strip()
    email     = request.POST.get('email', '').strip()

    if username:
        # Link an existing student account
        try:
            student = User.objects.get(username=username, role='student')
        except User.DoesNotExist:
            messages.error(request, f'Student "{username}" not found.')
            return _archive_redirect()
        if TeamMember.objects.filter(team=team, user=student).exists():
            messages.error(request, f'{student.full_name or username} is already on this team.')
            return _archive_redirect()
        TeamMember.objects.create(team=team, user=student, role='member', status='active')
        messages.success(request, f'{student.full_name or username} added.')
    elif full_name:
        # Create a placeholder (inactive) user from name + email
        user = _make_archive_user(full_name, email)
        TeamMember.objects.create(team=team, user=user, role='member', status='active')
        messages.success(request, f'{full_name} added as archive member.')
    else:
        messages.error(request, 'Enter a name or an existing username.')
    return _archive_redirect()


@login_required
@require_POST
def admin_archive_remove_member(request, member_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    member = get_object_or_404(TeamMember, pk=member_id)
    name   = member.user.full_name or member.user.username
    member.delete()
    messages.success(request, f'{name} removed from archive project.')
    return _archive_redirect()


@login_required
@require_POST
def admin_archive_edit_member(request, member_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    member    = get_object_or_404(TeamMember, pk=member_id)
    user      = member.user
    full_name = request.POST.get('full_name', '').strip()
    email     = request.POST.get('email', '').strip()
    if full_name:
        user.full_name = full_name
    if email:
        user.email = email
    user.save(update_fields=['full_name', 'email'])
    messages.success(request, f'Member info updated for {user.full_name or user.username}.')
    return _archive_redirect()


# ════════════════════════════════════════════════════════════════════════════════
#  ARCHIVE — LINK MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_add_archive_link(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id)
    label   = request.POST.get('label', '').strip()
    url     = request.POST.get('url', '').strip()
    if not label or not url:
        messages.error(request, 'Both label and URL are required.')
        return _archive_redirect()
    ArchiveLink.objects.create(project=project, label=label, url=url)
    messages.success(request, f'Link "{label}" added.')
    return _archive_redirect()


@login_required
@require_POST
def admin_delete_archive_link(request, link_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    link = get_object_or_404(ArchiveLink, pk=link_id)
    label = link.label
    link.delete()
    messages.success(request, f'Link "{label}" deleted.')
    return _archive_redirect()


# ════════════════════════════════════════════════════════════════════════════════
#  ARCHIVE — DELETE PROJECT
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_delete_archive_project(request, project_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    project = get_object_or_404(Project, pk=project_id)
    title   = project.title
    team    = project.team
    team.delete()   # cascades: Project, TeamMembers deleted; User records preserved
    messages.success(request, f'Archive project "{title}" permanently deleted.')
    return _archive_redirect()


# ════════════════════════════════════════════════════════════════════════════════
#  ARCHIVE — SET LEADER
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_archive_set_leader(request, member_id):
    if not _require_admin(request):
        return redirect('dashboard:index')
    member = get_object_or_404(TeamMember, pk=member_id)
    member.team.memberships.filter(role='leader').update(role='member')
    member.role = 'leader'
    member.save()
    messages.success(request, f'{member.user.full_name or member.user.username} set as team leader.')
    return _archive_redirect()


# ════════════════════════════════════════════════════════════════════════════════
#  PHASE 2 START DATE
# ════════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def admin_set_phase2_date(request):
    if not _require_admin(request):
        return redirect('dashboard:index')
    config   = SystemConfig.get()
    date_str = request.POST.get('phase2_start_date', '').strip()
    if date_str:
        try:
            from datetime import date as _date
            config.phase2_start_date = _date.fromisoformat(date_str)
            config.save(update_fields=['phase2_start_date'])
            messages.success(
                request,
                f'Phase 2 will auto-activate on {config.phase2_start_date}. '
                f'The system switches automatically when the admin dashboard is first loaded on or after that date.'
            )
        except ValueError:
            messages.error(request, 'Invalid date format.')
    else:
        config.phase2_start_date = None
        config.save(update_fields=['phase2_start_date'])
        messages.success(request, 'Phase 2 scheduled date cleared.')
    return redirect(reverse('dashboard:admin') + '?panel=system')


# ════════════════════════════════════════════════════════════════════════════════
#  STUDENT — PROFILE EDIT
# ════════════════════════════════════════════════════════════════════════════════

@login_required
def student_edit_profile(request):
    user = request.user
    if not user.is_student():
        return redirect('dashboard:index')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'bio':
            user.bio = request.POST.get('bio', '').strip()
            user.save(update_fields=['bio'])
            messages.success(request, 'Profile updated.')

        elif action == 'password':
            current_pw = request.POST.get('current_password', '')
            new_pw     = request.POST.get('new_password', '')
            confirm_pw = request.POST.get('confirm_password', '')
            import re as _re
            if not user.check_password(current_pw):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_pw) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
            elif not _re.search(r'[A-Za-z]', new_pw):
                messages.error(request, 'Password must contain at least one letter.')
            elif not _re.search(r'\d', new_pw):
                messages.error(request, 'Password must contain at least one number.')
            elif not _re.search(r'[^A-Za-z0-9]', new_pw):
                messages.error(request, 'Password must contain at least one special character.')
            elif new_pw != confirm_pw:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_pw)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')

        return redirect('dashboard:student_edit_profile')

    return render(request, 'dashboard/student_profile.html', {'profile_user': user})
