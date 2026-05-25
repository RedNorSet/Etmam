from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from projects.models import Project

from .forms import MilestoneForm, MilestoneTemplateForm
from .models import Milestone, MilestoneTemplate


def milestone_list(request):
    return redirect('submissions:milestone_list')


def milestone_detail(request, milestone_id):
    return redirect('submissions:milestone_detail', milestone_id=milestone_id)


def _can_manage_project_milestones(user, project):
    if user.is_administrator():
        return True
    return user.is_supervisor() and project.supervisor_id == user.id


def _safe_next(request, fallback):
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


def _template_due_date(project, template):
    return project.created_at.date() + timedelta(days=template.default_due_offset_days)


def _create_milestone_from_template(project, template, user):
    milestone = Milestone.objects.create(
        project=project,
        template=template,
        title=template.title,
        description=template.description,
        type=template.type,
        due_date=_template_due_date(project, template),
        weight=template.default_weight,
        status='pending',
        created_by=user,
    )
    _ensure_submission_shell(milestone)
    return milestone


def _ensure_submission_shell(milestone):
    from submissions.models import ensure_submission_shell

    return ensure_submission_shell(milestone)


def _has_student_submission(milestone):
    return milestone.submissions.filter(submitted_by__isnull=False).exists()


def _sync_template_to_milestones(template):
    linked = Milestone.objects.filter(template=template)
    updated = 0
    for milestone in linked:
        update_fields = ['title', 'description', 'type', 'weight']
        milestone.title = template.title
        milestone.description = template.description
        milestone.type = template.type
        milestone.weight = template.default_weight

        if not _has_student_submission(milestone) and milestone.status in {'pending', 'in_progress', 'overdue'}:
            milestone.due_date = _template_due_date(milestone.project, template)
            update_fields.append('due_date')

        milestone.save(update_fields=update_fields)
        updated += 1
    return updated


@login_required
@require_POST
def create_milestone(request):
    project_id = request.POST.get('project_id')
    if not project_id:
        messages.error(request, 'Please choose a project before creating a milestone.')
        return _safe_next(request, 'dashboard:index')

    project = get_object_or_404(Project, pk=project_id)
    if not _can_manage_project_milestones(request.user, project):
        messages.error(request, 'You do not have permission to create milestones for this project.')
        return redirect('dashboard:index')

    template_id = request.POST.get('template_id')
    if template_id:
        template = get_object_or_404(MilestoneTemplate, pk=template_id, is_active=True)
        try:
            _create_milestone_from_template(project, template, request.user)
            messages.success(request, 'Milestone created from template.')
        except IntegrityError:
            messages.error(request, 'This project already has a milestone from that template.')
        if request.user.is_administrator():
            return _safe_next(request, '/dashboard/admin/?section=milestones')
        return _safe_next(request, f'/dashboard/supervisor/teams/{project.id}/')

    form = MilestoneForm(request.POST)
    if form.is_valid():
        milestone = form.save(commit=False)
        milestone.project = project
        milestone.created_by = request.user
        milestone.status = 'pending'
        milestone.save()
        _ensure_submission_shell(milestone)
        messages.success(request, 'Milestone created successfully.')
    else:
        messages.error(request, 'Could not create milestone. Please check the form values.')

    if request.user.is_administrator():
        return _safe_next(request, '/dashboard/admin/?section=milestones')
    return _safe_next(request, f'/dashboard/supervisor/teams/{project.id}/')


@login_required
@require_POST
def create_template(request):
    if not request.user.is_administrator():
        messages.error(request, 'Only administrators can manage milestone templates.')
        return redirect('dashboard:index')

    form = MilestoneTemplateForm(request.POST)
    if form.is_valid():
        template = form.save(commit=False)
        template.created_by = request.user
        template.save()
        messages.success(request, 'Milestone template created.')
    else:
        messages.error(request, 'Could not create template. Please check the form values.')
    return _safe_next(request, '/dashboard/admin/?section=milestones')


@login_required
@require_POST
def update_template(request, template_id):
    if not request.user.is_administrator():
        messages.error(request, 'Only administrators can manage milestone templates.')
        return redirect('dashboard:index')

    template = get_object_or_404(MilestoneTemplate, pk=template_id)
    form = MilestoneTemplateForm(request.POST, instance=template)
    if form.is_valid():
        template = form.save()
        if request.POST.get('sync_existing') == 'on':
            updated = _sync_template_to_milestones(template)
            messages.success(request, f'Template updated and synced to {updated} milestone(s).')
        else:
            messages.success(request, 'Template updated.')
    else:
        messages.error(request, 'Could not update template. Please check the form values.')
    return _safe_next(request, '/dashboard/admin/?section=milestones')


@login_required
@require_POST
def apply_template(request, template_id):
    if not request.user.is_administrator():
        messages.error(request, 'Only administrators can apply milestone templates.')
        return redirect('dashboard:index')

    template = get_object_or_404(MilestoneTemplate, pk=template_id, is_active=True)
    project_id = request.POST.get('project_id')
    projects = Project.objects.filter(pk=project_id) if project_id else Project.objects.all()

    created = 0
    skipped = 0
    with transaction.atomic():
        for project in projects:
            if Milestone.objects.filter(project=project, template=template).exists():
                skipped += 1
                continue
            _create_milestone_from_template(project, template, request.user)
            created += 1

    messages.success(request, f'Applied template to {created} project(s). {skipped} already had it.')
    return _safe_next(request, '/dashboard/admin/?section=milestones')


@login_required
@require_POST
def delete_milestone(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.select_related('project'), pk=milestone_id)
    project = milestone.project
    if not _can_manage_project_milestones(request.user, project):
        messages.error(request, 'You do not have permission to delete this milestone.')
        return redirect('dashboard:index')

    if _has_student_submission(milestone):
        messages.error(request, 'Milestones with submissions cannot be deleted.')
    else:
        milestone.delete()
        messages.success(request, 'Milestone deleted.')

    if request.user.is_administrator():
        return _safe_next(request, '/dashboard/admin/?section=milestones')
    return _safe_next(request, f'/dashboard/supervisor/teams/{project.id}/')
