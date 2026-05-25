from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from milestones.models import Milestone
from notifications.models import Notification
from projects.models import Project
from reviews.models import Feedback, Grade
from teams.models import TeamMember

from .forms import SubmissionReviewForm, SubmissionUploadForm
from .models import Submission, SubmissionFile, ensure_submission_shell


def _active_membership(user):
    return TeamMember.objects.filter(user=user, status='active').select_related('team').first()


def _student_project(user):
    membership = _active_membership(user)
    if not membership:
        return None, None
    return getattr(membership.team, 'project', None), membership


def _user_can_view_project(user, project):
    if user.is_administrator():
        return True
    if user.is_supervisor() and project.supervisor_id == user.id:
        return True
    if user.is_reviewer() and project.reviewer_id == user.id:
        return True
    if user.is_student():
        student_project, _ = _student_project(user)
        return student_project and student_project.id == project.id
    return False


def _review_dashboard_name(user):
    if user.is_administrator():
        return 'dashboard:admin'
    if user.is_supervisor():
        return 'dashboard:supervisor'
    return 'dashboard:index'


def _grade_type_for(milestone):
    if milestone.type in {'mid', 'final'}:
        return milestone.type
    return None


def _is_submission_shell(submission):
    return (
        submission
        and submission.submitted_by_id is None
        and submission.status == 'pending'
        and not submission.files.exists()
    )


@login_required
def milestone_list(request):
    if not request.user.is_student():
        return redirect('dashboard:index')

    project, membership = _student_project(request.user)
    if not project:
        messages.error(request, 'You must be in a team with a project to view milestones.')
        return redirect('dashboard:student')

    milestones = list(
        project.milestones
        .select_related('project', 'project__team', 'project__supervisor')
        .prefetch_related('submissions__files')
        .order_by('due_date')
    )
    for milestone in milestones:
        ensure_submission_shell(milestone)

    return render(request, 'submissions/milestone_list.html', {
        'project': project,
        'membership': membership,
        'milestones': milestones,
    })


@login_required
def milestone_detail(request, milestone_id):
    if not request.user.is_student():
        return redirect('dashboard:index')

    milestone = get_object_or_404(
        Milestone.objects.select_related('project', 'project__team', 'project__supervisor', 'project__reviewer'),
        pk=milestone_id,
    )
    project, membership = _student_project(request.user)
    if not project or milestone.project_id != project.id:
        messages.error(request, 'You do not have access to this milestone.')
        return redirect('dashboard:student')
    ensure_submission_shell(milestone)

    if request.method == 'POST':
        form = SubmissionUploadForm(request.POST, request.FILES, files=request.FILES)
        if form.is_valid():
            with transaction.atomic():
                latest_submission = (
                    milestone.submissions
                    .select_for_update()
                    .filter(is_latest=True)
                    .prefetch_related('files')
                    .first()
                )
                if _is_submission_shell(latest_submission):
                    submission = latest_submission
                    submission.submitted_by = request.user
                    submission.notes = form.cleaned_data['notes'].strip()
                    submission.submitted_at = timezone.now()
                    submission.status = 'pending'
                    submission.save(update_fields=['submitted_by', 'notes', 'submitted_at', 'status'])
                else:
                    submission = Submission.objects.create(
                        milestone=milestone,
                        submitted_by=request.user,
                        notes=form.cleaned_data['notes'].strip(),
                        status='pending',
                    )
                for uploaded_file in form.uploaded_files:
                    SubmissionFile.objects.create(
                        submission=submission,
                        file=uploaded_file,
                        file_name=uploaded_file.name,
                        file_type=getattr(uploaded_file, 'content_type', '') or '',
                        file_size=uploaded_file.size,
                    )
                if milestone.status in {'pending', 'in_progress', 'overdue'}:
                    milestone.status = 'submitted'
                    milestone.save(update_fields=['status'])

                recipients = []
                if milestone.project.supervisor_id:
                    recipients.append(milestone.project.supervisor)
                if milestone.project.reviewer_id and milestone.project.reviewer_id != milestone.project.supervisor_id:
                    recipients.append(milestone.project.reviewer)
                for recipient in recipients:
                    Notification.objects.create(
                        recipient=recipient,
                        type='general',
                        title='New submission received',
                        message=f'{milestone.project.team.name} submitted {milestone.title} v{submission.version}.',
                        link=f'/submissions/submission/{submission.id}/',
                    )

            messages.success(request, f'Submission v{submission.version} submitted successfully.')
            if request.POST.get('next') == 'dashboard':
                return redirect('/dashboard/student/?section=milestones')
            return redirect('submissions:milestone_detail', milestone_id=milestone.id)
    else:
        form = SubmissionUploadForm()

    submissions = milestone.submissions.select_related('submitted_by').prefetch_related('files')
    latest_submission = submissions.filter(is_latest=True).first()

    return render(request, 'submissions/milestone_detail.html', {
        'milestone': milestone,
        'membership': membership,
        'form': form,
        'latest_submission': latest_submission,
        'submissions': submissions,
        'is_overdue': milestone.due_date < timezone.localdate() and milestone.status not in {'submitted', 'approved'},
    })


@login_required
def submission_list(request):
    user = request.user
    if user.is_administrator():
        projects = Project.objects.all()
    elif user.is_supervisor():
        projects = Project.objects.filter(supervisor=user)
    elif user.is_reviewer():
        projects = Project.objects.filter(reviewer=user)
    else:
        return redirect('dashboard:index')

    for milestone in Milestone.objects.filter(project__in=projects).prefetch_related('submissions'):
        ensure_submission_shell(milestone)

    submissions = (
        Submission.objects
        .filter(milestone__project__in=projects)
        .select_related('milestone', 'milestone__project', 'milestone__project__team', 'submitted_by', 'reviewed_by')
        .prefetch_related('files')
        .order_by('-submitted_at')
    )

    return render(request, 'submissions/submission_list.html', {
        'submissions': submissions,
    })


@login_required
def submission_detail(request, submission_id):
    submission = get_object_or_404(
        Submission.objects
        .select_related('milestone', 'milestone__project', 'milestone__project__team', 'submitted_by', 'reviewed_by')
        .prefetch_related('files', 'feedback'),
        pk=submission_id,
    )
    project = submission.milestone.project
    if not _user_can_view_project(request.user, project):
        messages.error(request, 'You do not have access to this submission.')
        return redirect('dashboard:index')

    has_student_upload = submission.submitted_by_id is not None and submission.files.exists()
    can_review = has_student_upload and (request.user.is_administrator() or (
        request.user.is_supervisor() and project.supervisor_id == request.user.id
    ))

    if request.method == 'POST':
        if not can_review:
            messages.error(request, 'This submission cannot be reviewed until the student uploads files.')
            return redirect('submissions:submission_detail', submission_id=submission.id)

        form = SubmissionReviewForm(request.POST)
        if form.is_valid():
            feedback_text = form.cleaned_data['feedback'].strip()
            status = form.cleaned_data['status']
            score = form.cleaned_data['score']

            with transaction.atomic():
                submission.status = status
                submission.review_score = score
                submission.reviewed_by = request.user
                submission.reviewed_at = timezone.now()
                submission.save(update_fields=['status', 'review_score', 'reviewed_by', 'reviewed_at'])

                if status == 'approved':
                    submission.milestone.status = 'approved'
                    submission.milestone.save(update_fields=['status'])
                elif status == 'revision':
                    submission.milestone.status = 'in_progress'
                    submission.milestone.save(update_fields=['status'])

                if feedback_text:
                    Feedback.objects.create(
                        project=project,
                        given_by=request.user,
                        submission=submission,
                        comment=feedback_text,
                    )

                grade_type = _grade_type_for(submission.milestone)
                if score is not None and grade_type:
                    Grade.objects.update_or_create(
                        project=project,
                        type=grade_type,
                        defaults={
                            'supervisor_score': score,
                            'comments': feedback_text,
                        },
                    )

                if submission.submitted_by_id:
                    Notification.objects.create(
                        recipient=submission.submitted_by,
                        type='feedback',
                        title='Submission reviewed',
                        message=f'{submission.milestone.title} was marked as {submission.get_status_display()}.',
                        link=f'/submissions/submission/{submission.id}/',
                    )

            messages.success(request, 'Submission review saved.')
            return redirect('submissions:submission_detail', submission_id=submission.id)
    else:
        form = SubmissionReviewForm(initial={
            'status': submission.status if submission.status != 'pending' else 'reviewed',
            'score': submission.review_score,
        })

    return render(request, 'submissions/submission_detail.html', {
        'submission': submission,
        'files': submission.files.all(),
        'feedback_items': submission.feedback.select_related('given_by').order_by('-created_at'),
        'form': form,
        'can_review': can_review,
        'has_student_upload': has_student_upload,
        'return_dashboard': _review_dashboard_name(request.user),
    })


@login_required
def download_file(request, file_id):
    submission_file = get_object_or_404(
        SubmissionFile.objects.select_related(
            'submission',
            'submission__milestone',
            'submission__milestone__project',
        ),
        pk=file_id,
    )
    if not _user_can_view_project(request.user, submission_file.submission.milestone.project):
        messages.error(request, 'You do not have permission to download this file.')
        return redirect('dashboard:index')

    response = FileResponse(submission_file.file.open('rb'))
    filename = submission_file.file_name or submission_file.file.name.rsplit('/', 1)[-1]
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
