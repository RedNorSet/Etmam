import logging
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import Submission, ReviewerGrade
from milestones.models import ProjectGrade
from notifications.models import Notification

_log = logging.getLogger('gpms.grades')

def _parse_grade(raw):
    if not raw:
        return None
    g = float(raw)
    if not (0 <= g <= 100):
        raise ValueError
    return g

def _recalculate_submission_grade(sub):
    milestone = sub.milestone

    if milestone.has_split:
        report_vals = []
        if sub.supervisor_report_grade is not None:
            report_vals.append(float(sub.supervisor_report_grade))
        for rg in sub.reviewer_grades.filter(component='report'):
            if rg.grade is not None:
                report_vals.append(float(rg.grade))

        pres_vals = []
        if sub.supervisor_presentation_grade is not None:
            pres_vals.append(float(sub.supervisor_presentation_grade))
        for rg in sub.reviewer_grades.filter(component='presentation'):
            if rg.grade is not None:
                pres_vals.append(float(rg.grade))

        report_avg = round(sum(report_vals) / len(report_vals), 2) if report_vals else None
        pres_avg   = round(sum(pres_vals)   / len(pres_vals),   2) if pres_vals   else None

        if sub.project:
            if report_avg is not None:
                ProjectGrade.objects.update_or_create(
                    project=sub.project, milestone=milestone, component='report',
                    defaults={'score': report_avg, 'graded_at': timezone.now()},
                )
            if pres_avg is not None:
                ProjectGrade.objects.update_or_create(
                    project=sub.project, milestone=milestone, component='presentation',
                    defaults={'score': pres_avg, 'graded_at': timezone.now()},
                )

        if report_avg is not None and pres_avg is not None:
            rw = milestone.report_weight / 100
            pw = milestone.presentation_weight / 100
            sub.grade = round(report_avg * rw + pres_avg * pw, 2)
        elif report_avg is not None:
            sub.grade = round(report_avg * (milestone.report_weight / 100), 2)
        elif pres_avg is not None:
            sub.grade = round(pres_avg * (milestone.presentation_weight / 100), 2)
        else:
            sub.grade = None

    else:
        vals = []
        if sub.supervisor_grade is not None:
            vals.append(float(sub.supervisor_grade))
        for rg in sub.reviewer_grades.filter(component='single'):
            if rg.grade is not None:
                vals.append(float(rg.grade))

        sub.grade = round(sum(vals) / len(vals), 2) if vals else None

        if sub.grade is not None and sub.project:
            ProjectGrade.objects.update_or_create(
                project=sub.project, milestone=milestone, component='single',
                defaults={'score': sub.grade, 'graded_at': timezone.now()},
            )

    sub.save(update_fields=['grade'])

def _notify_all_graded(sub):
    """Send a notification to students when every grader has submitted their grade."""
    milestone = sub.milestone
    project   = sub.project
    if not project:
        return
    num_reviewers = project.reviewers.count()
    if milestone.has_split:
        sup_done = (sub.supervisor_report_grade is not None and
                    sub.supervisor_presentation_grade is not None)
        rev_done = (sub.reviewer_grades
                    .filter(component='report', grade__isnull=False)
                    .values('reviewer').distinct().count())
    else:
        sup_done = sub.supervisor_grade is not None
        rev_done = (sub.reviewer_grades
                    .filter(component='single', grade__isnull=False)
                    .values('reviewer').distinct().count())
    if not (sup_done and rev_done >= num_reviewers):
        return
    grade_str = f"{sub.grade:.1f}/100" if sub.grade is not None else "—"
    title   = f'All Grades Submitted — {milestone.title}'
    message = f'Your submission for "{milestone.title}" has been fully graded. Final grade: {grade_str}.'
    for tm in project.team.memberships.filter(status='active').select_related('user'):
        Notification.objects.create(
            recipient=tm.user, type='feedback',
            title=title, message=message, link='/dashboard/',
        )

@login_required
@require_POST
def supervisor_grade_submission(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id)
    project = sub.project
    if not project or project.supervisor != request.user:
        messages.error(request, 'You are not the supervisor for this project.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    feedback = request.POST.get('feedback', '').strip()
    milestone = sub.milestone

    try:
        if milestone.has_split:
            report_grade = _parse_grade(request.POST.get('grade_report', '').strip())
            pres_grade   = _parse_grade(request.POST.get('grade_presentation', '').strip())
            sub.supervisor_report_grade       = report_grade
            sub.supervisor_presentation_grade = pres_grade
            if report_grade is not None and pres_grade is not None:
                rw = milestone.report_weight / 100
                pw = milestone.presentation_weight / 100
                sub.supervisor_grade = round(report_grade * rw + pres_grade * pw, 2)
        else:
            sub.supervisor_grade = _parse_grade(request.POST.get('grade', '').strip())
    except ValueError:
        messages.error(request, 'Grade must be a number between 0 and 100.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    sub.supervisor_feedback  = feedback
    sub.supervisor_graded_by = request.user
    sub.supervisor_graded_at = timezone.now()
    sub.save(update_fields=[
        'supervisor_grade', 'supervisor_report_grade', 'supervisor_presentation_grade',
        'supervisor_feedback', 'supervisor_graded_by', 'supervisor_graded_at',
    ])

    _recalculate_submission_grade(sub)
    _notify_all_graded(sub)
    _log.info(
        'SUP_GRADE user=%s project=%s milestone=%s grade=%s',
        request.user.username,
        project.title,
        sub.milestone.title,
        sub.supervisor_grade,
    )
    messages.success(request, 'Grade saved.')
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')

@login_required
@require_POST
def reviewer_grade_submission(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id)
    project = sub.project
    if not project or not project.reviewers.filter(pk=request.user.pk).exists():
        messages.error(request, 'You are not a reviewer for this project.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    feedback  = request.POST.get('feedback', '').strip()
    milestone = sub.milestone

    try:
        if milestone.has_split:
            report_grade = _parse_grade(request.POST.get('grade_report', '').strip())
            pres_grade   = _parse_grade(request.POST.get('grade_presentation', '').strip())
            ReviewerGrade.objects.update_or_create(
                submission=sub, reviewer=request.user, component='report',
                defaults={'grade': report_grade, 'feedback': feedback},
            )
            ReviewerGrade.objects.update_or_create(
                submission=sub, reviewer=request.user, component='presentation',
                defaults={'grade': pres_grade, 'feedback': feedback},
            )
        else:
            grade = _parse_grade(request.POST.get('grade', '').strip())
            ReviewerGrade.objects.update_or_create(
                submission=sub, reviewer=request.user, component='single',
                defaults={'grade': grade, 'feedback': feedback},
            )
    except ValueError:
        messages.error(request, 'Grade must be a number between 0 and 100.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    _recalculate_submission_grade(sub)
    _notify_all_graded(sub)
    messages.success(request, 'Grade saved.')
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')

@login_required
@require_POST
def supervisor_update_status(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id)
    project = sub.project
    if not project or project.supervisor != request.user:
        messages.error(request, 'You are not the supervisor for this project.')
        return redirect(reverse('dashboard:supervisor') + '#sec-teams')

    status = request.POST.get('status', '').strip()
    if status in dict(Submission.STATUS):
        sub.status = status
        sub.save()
        messages.success(request, f'Submission marked as "{sub.get_status_display()}".')
    else:
        messages.error(request, 'Invalid status.')
    return redirect(reverse('dashboard:supervisor') + '#sec-teams')
