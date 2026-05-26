from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .models import Submission


@login_required
@require_POST
def supervisor_grade_submission(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id)
    project = sub.project
    if not project or project.supervisor != request.user:
        messages.error(request, 'You are not the supervisor for this project.')
        return redirect('dashboard:supervisor')

    grade_raw = request.POST.get('grade', '').strip()
    feedback  = request.POST.get('feedback', '').strip()

    grade = None
    if grade_raw:
        try:
            grade = float(grade_raw)
            if not (0 <= grade <= 100):
                messages.error(request, 'Grade must be between 0 and 100.')
                return redirect('dashboard:supervisor')
        except ValueError:
            messages.error(request, 'Invalid grade value.')
            return redirect('dashboard:supervisor')

    sub.supervisor_grade     = grade
    sub.supervisor_feedback  = feedback
    sub.supervisor_graded_by = request.user
    sub.supervisor_graded_at = timezone.now()

    if sub.supervisor_grade is not None and sub.reviewer_grade is not None:
        sub.grade = round((float(sub.supervisor_grade) + float(sub.reviewer_grade)) / 2, 2)

    sub.save()
    messages.success(request, 'Grade saved.')
    return redirect('dashboard:supervisor')


@login_required
@require_POST
def reviewer_grade_submission(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id)
    project = sub.project
    if not project or not project.reviewers.filter(pk=request.user.pk).exists():
        messages.error(request, 'You are not a reviewer for this project.')
        return redirect('dashboard:supervisor')

    grade_raw = request.POST.get('grade', '').strip()
    feedback  = request.POST.get('feedback', '').strip()

    grade = None
    if grade_raw:
        try:
            grade = float(grade_raw)
            if not (0 <= grade <= 100):
                messages.error(request, 'Grade must be between 0 and 100.')
                return redirect('dashboard:supervisor')
        except ValueError:
            messages.error(request, 'Invalid grade value.')
            return redirect('dashboard:supervisor')

    sub.reviewer_grade     = grade
    sub.reviewer_feedback  = feedback
    sub.reviewer_graded_by = request.user
    sub.reviewer_graded_at = timezone.now()

    if sub.supervisor_grade is not None and sub.reviewer_grade is not None:
        sub.grade = round((float(sub.supervisor_grade) + float(sub.reviewer_grade)) / 2, 2)

    sub.save()
    messages.success(request, 'Grade saved.')
    return redirect('dashboard:supervisor')


@login_required
@require_POST
def supervisor_update_status(request, submission_id):
    sub = get_object_or_404(Submission, pk=submission_id)
    project = sub.project
    if not project or project.supervisor != request.user:
        messages.error(request, 'You are not the supervisor for this project.')
        return redirect('dashboard:supervisor')

    status = request.POST.get('status', '').strip()
    if status in dict(Submission.STATUS):
        sub.status = status
        sub.save()
        messages.success(request, f'Submission marked as "{sub.get_status_display()}".')
    else:
        messages.error(request, 'Invalid status.')
    return redirect('dashboard:supervisor')
