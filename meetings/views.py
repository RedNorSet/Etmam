from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.models import User
from notifications.models import Notification
from projects.models import Project
from teams.models import TeamMember

from .models import Meeting, MeetingParticipant, ProposedSlot, RescheduleProposal


# ── helpers ─────────────────────────────────────────────────────────

def eligible_participants(user):
    """Project-circle: teammates + supervisor for students; supervised students for supervisors."""
    users = {}
    if user.is_student():
        membership = TeamMember.objects.filter(user=user, status='active').select_related('team').first()
        if membership:
            team = membership.team
            for m in TeamMember.objects.filter(team=team, status='active').exclude(user=user).select_related('user'):
                if m.user.is_active:
                    users[m.user.id] = m.user
            project = getattr(team, 'project', None)
            if project and project.supervisor_id and project.supervisor.is_active:
                users[project.supervisor_id] = project.supervisor
    elif user.is_supervisor():
        for project in Project.objects.filter(supervisor=user).select_related('team'):
            team = project.team
            for m in TeamMember.objects.filter(team=team, status='active').select_related('user'):
                if m.user.is_active:
                    users[m.user.id] = m.user
    return sorted(users.values(), key=lambda u: (u.full_name or u.username).lower())


def eligible_teams_for_supervisor(user):
    """Returns list of {project, members} dicts for each supervised team — used for grouped participant picker."""
    result = []
    for project in Project.objects.filter(supervisor=user).select_related('team').order_by('title'):
        members = [
            m.user for m in
            TeamMember.objects.filter(team=project.team, status='active').select_related('user')
        ]
        if members:
            result.append({'project': project, 'members': members})
    return result


def _user_project_for(user, participant_user):
    """Find the project that connects user and participant (team membership or supervision)."""
    if user.is_student():
        membership = TeamMember.objects.filter(user=user, status='active').select_related('team__project').first()
        return getattr(membership.team, 'project', None) if membership else None
    if user.is_supervisor():
        # find the project where this supervisor supervises and the participant is on the team
        return Project.objects.filter(
            supervisor=user, team__memberships__user=participant_user, team__memberships__status='active'
        ).first() or Project.objects.filter(supervisor=user).first()
    return None


def _parse_local_dt(date_str, time_str):
    if not (date_str and time_str):
        return None
    dt = parse_datetime(f"{date_str}T{time_str}")
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_datetime_local(raw):
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _notify(recipient, title, message, link=''):
    if not recipient:
        return
    Notification.objects.create(
        recipient=recipient,
        type='meeting',
        title=title,
        message=message,
        link=link,
    )


def _meeting_link(meeting):
    return f"/dashboard/?meeting={meeting.id}#sec-meetings"


def _back_to_dashboard(user):
    if user.is_supervisor():
        return redirect('dashboard:supervisor')
    if user.is_administrator():
        return redirect('dashboard:admin')
    return redirect('dashboard:student')


def _color_for(meeting):
    return {
        'pending':      '#f59e0b',
        'confirmed':    '#10b981',
        'rescheduling': '#3b82f6',
        'declined':     '#ef4444',
        'cancelled':    '#6b7280',
        'completed':    '#64748b',
    }.get(meeting.status, '#6b7280')


# ── views ───────────────────────────────────────────────────────────

@login_required
def events_api(request):
    user = request.user
    qs = Meeting.objects.filter(
        Q(scheduled_by=user) | Q(participants__user=user)
    ).distinct().select_related('scheduled_by')

    events = []
    for m in qs:
        events.append({
            'id':              m.id,
            'title':           m.title,
            'start':           m.datetime.isoformat(),
            'end':             m.end_datetime.isoformat(),
            'backgroundColor': _color_for(m),
            'borderColor':     _color_for(m),
            'extendedProps': {
                'status':       m.status,
                'statusLabel':  m.get_status_display(),
                'location':     m.location,
                'importance':   m.get_importance_display(),
                'notes':        m.notes,
                'scheduledBy':  (m.scheduled_by.full_name or m.scheduled_by.username) if m.scheduled_by else '',
                'isScheduler':  m.scheduled_by_id == user.id,
                'detailUrl':    reverse('meetings:detail', args=[m.id]),
            },
        })
    return JsonResponse(events, safe=False)


@login_required
def detail(request, pk):
    user = request.user
    meeting = get_object_or_404(
        Meeting.objects.select_related('scheduled_by', 'project'),
        pk=pk,
    )
    is_scheduler = meeting.scheduled_by_id == user.id
    participant = MeetingParticipant.objects.filter(meeting=meeting, user=user).first()
    if not (is_scheduler or participant or user.is_administrator()):
        raise Http404()

    participants = meeting.participants.select_related('user').all()
    proposals = (
        meeting.reschedule_proposals
        .select_related('proposed_by')
        .prefetch_related('slots')
        .all()
    )

    template = 'meetings/_detail_panel.html' if request.GET.get('modal') else 'meetings/detail.html'
    return render(request, template, {
        'meeting':       meeting,
        'participants':  participants,
        'proposals':     proposals,
        'is_scheduler':  is_scheduler,
        'participant':   participant,
    })


@login_required
@require_POST
def create_meeting(request):
    user = request.user
    title       = request.POST.get('title', '').strip()
    date_str    = request.POST.get('date')
    time_str    = request.POST.get('time')
    duration    = request.POST.get('duration') or '30'
    location    = request.POST.get('location', '').strip()
    importance  = request.POST.get('importance', 'medium')
    notes       = request.POST.get('notes', '').strip()
    participant_ids = request.POST.getlist('participants')

    if not (title and date_str and time_str and participant_ids):
        messages.error(request, 'Please fill in title, date, time, and at least one participant.')
        return _back_to_dashboard(user)

    dt = _parse_local_dt(date_str, time_str)
    if not dt:
        messages.error(request, 'Invalid date or time.')
        return _back_to_dashboard(user)

    if dt < timezone.now():
        messages.error(request, 'You cannot schedule a meeting in the past.')
        return _back_to_dashboard(user)

    try:
        duration_int = max(5, min(int(duration), 480))
    except ValueError:
        duration_int = 30

    eligible_ids = {u.id for u in eligible_participants(user)}
    try:
        chosen_ids = [int(p) for p in participant_ids if int(p) in eligible_ids]
    except ValueError:
        messages.error(request, 'Invalid participants.')
        return _back_to_dashboard(user)

    if not chosen_ids:
        messages.error(request, 'None of the selected participants are valid.')
        return _back_to_dashboard(user)

    first_participant = User.objects.filter(pk=chosen_ids[0]).first()
    project = _user_project_for(user, first_participant)

    meeting = Meeting.objects.create(
        project=project,
        scheduled_by=user,
        title=title,
        datetime=dt,
        duration_minutes=duration_int,
        location=location,
        importance=importance if importance in dict(Meeting.IMPORTANCE) else 'medium',
        notes=notes,
        status='pending',
    )
    for pid in chosen_ids:
        MeetingParticipant.objects.create(meeting=meeting, user_id=pid)
        _notify(
            recipient=User.objects.filter(pk=pid).first(),
            title=f'Meeting invitation: {title}',
            message=(
                f'{user.full_name or user.username} invited you to "{title}" on '
                f'{dt.strftime("%b %d, %Y at %I:%M %p")}.'
            ),
            link=_meeting_link(meeting),
        )

    messages.success(request, 'Meeting scheduled. Invitations sent.')
    return _back_to_dashboard(user)


@login_required
@require_POST
def respond(request, pk):
    """Participant accepts or declines."""
    user = request.user
    meeting = get_object_or_404(Meeting, pk=pk)
    participant = get_object_or_404(MeetingParticipant, meeting=meeting, user=user)
    action = request.POST.get('action')

    if meeting.status in ('cancelled', 'completed'):
        messages.error(request, 'This meeting is no longer open.')
        return _back_to_dashboard(user)

    if action == 'accept':
        participant.response = 'accepted'
        participant.responded_at = timezone.now()
        participant.save()

        all_accepted = not meeting.participants.exclude(response='accepted').exists()
        if all_accepted:
            meeting.status = 'confirmed'
            meeting.save(update_fields=['status'])

        _notify(
            recipient=meeting.scheduled_by,
            title=f'Accepted: {meeting.title}',
            message=f'{user.full_name or user.username} accepted your meeting invitation.',
            link=_meeting_link(meeting),
        )
        messages.success(request, 'Meeting confirmed.')

    elif action == 'decline':
        participant.response = 'declined'
        participant.responded_at = timezone.now()
        participant.save()
        _notify(
            recipient=meeting.scheduled_by,
            title=f'Declined: {meeting.title}',
            message=f'{user.full_name or user.username} declined your meeting invitation.',
            link=_meeting_link(meeting),
        )
        messages.success(request, 'Meeting declined.')
    else:
        messages.error(request, 'Unknown action.')

    return _back_to_dashboard(user)


@login_required
@require_POST
def propose_reschedule(request, pk):
    """Invitee proposes 2-3 alternative times."""
    user = request.user
    meeting = get_object_or_404(Meeting, pk=pk)
    participant = get_object_or_404(MeetingParticipant, meeting=meeting, user=user)

    if meeting.status in ('cancelled', 'completed'):
        messages.error(request, 'This meeting is no longer open.')
        return _back_to_dashboard(user)

    raw_slots = request.POST.getlist('slots')
    now = timezone.now()
    slots = []
    for s in raw_slots:
        dt = _parse_datetime_local(s)
        if dt:
            slots.append(dt)

    if not (2 <= len(slots) <= 3):
        messages.error(request, 'Please propose 2 or 3 alternative times.')
        return _back_to_dashboard(user)

    if any(dt < now for dt in slots):
        messages.error(request, 'Proposed times must be in the future.')
        return _back_to_dashboard(user)

    # Close any earlier proposals from this user on this meeting
    RescheduleProposal.objects.filter(meeting=meeting, proposed_by=user, status='open').update(status='rejected')

    proposal = RescheduleProposal.objects.create(meeting=meeting, proposed_by=user)
    for s in slots:
        ProposedSlot.objects.create(proposal=proposal, datetime=s)

    participant.response = 'proposed'
    participant.responded_at = timezone.now()
    participant.save()

    meeting.status = 'rescheduling'
    meeting.save(update_fields=['status'])

    _notify(
        recipient=meeting.scheduled_by,
        title=f'Reschedule requested: {meeting.title}',
        message=(
            f'{user.full_name or user.username} proposed new times for "{meeting.title}". '
            f'Open the meeting to pick one.'
        ),
        link=_meeting_link(meeting),
    )
    messages.success(request, 'New times proposed. The organizer will pick one.')
    return _back_to_dashboard(user)


@login_required
@require_POST
def choose_slot(request, slot_id):
    """Original sender chooses one of the proposed slots."""
    user = request.user
    slot = get_object_or_404(ProposedSlot.objects.select_related('proposal__meeting'), pk=slot_id)
    proposal = slot.proposal
    meeting = proposal.meeting

    if meeting.scheduled_by_id != user.id:
        messages.error(request, 'Only the organizer can choose a new time.')
        return _back_to_dashboard(user)

    if proposal.status != 'open':
        messages.error(request, 'This proposal is no longer open.')
        return _back_to_dashboard(user)

    slot.selected = True
    slot.save(update_fields=['selected'])
    proposal.status = 'chosen'
    proposal.decided_at = timezone.now()
    proposal.save(update_fields=['status', 'decided_at'])

    # Reject any other open proposals on this meeting
    RescheduleProposal.objects.filter(meeting=meeting, status='open').update(status='rejected')

    meeting.datetime = slot.datetime
    meeting.status = 'pending'
    meeting.save(update_fields=['datetime', 'status'])

    # Reset all participant responses so they can re-confirm
    meeting.participants.update(response='pending', responded_at=None)

    for p in meeting.participants.select_related('user'):
        _notify(
            recipient=p.user,
            title=f'Meeting rescheduled: {meeting.title}',
            message=(
                f'New time: {meeting.datetime.strftime("%b %d, %Y at %I:%M %p")}. '
                f'Please confirm or propose another time.'
            ),
            link=_meeting_link(meeting),
        )

    messages.success(request, 'Meeting rescheduled. Participants notified.')
    return _back_to_dashboard(user)


@login_required
@require_POST
def reject_proposal(request, proposal_id):
    """Scheduler rejects a reschedule proposal without picking any slot."""
    user = request.user
    proposal = get_object_or_404(
        RescheduleProposal.objects.select_related('meeting', 'proposed_by'),
        pk=proposal_id,
    )
    meeting = proposal.meeting
    if meeting.scheduled_by_id != user.id:
        messages.error(request, 'Only the organizer can reject a proposal.')
        return _back_to_dashboard(user)

    proposal.status = 'rejected'
    proposal.decided_at = timezone.now()
    proposal.save(update_fields=['status', 'decided_at'])

    # If no other open proposals remain, keep meeting at original time and mark pending
    if not RescheduleProposal.objects.filter(meeting=meeting, status='open').exists():
        meeting.status = 'pending'
        meeting.save(update_fields=['status'])

    _notify(
        recipient=proposal.proposed_by,
        title=f'Reschedule declined: {meeting.title}',
        message='The organizer kept the original time. You can propose again or accept.',
        link=_meeting_link(meeting),
    )
    messages.success(request, 'Proposal rejected.')
    return _back_to_dashboard(user)


@login_required
@require_POST
def cancel_meeting(request, pk):
    user = request.user
    meeting = get_object_or_404(Meeting, pk=pk)
    if meeting.scheduled_by_id != user.id:
        messages.error(request, 'Only the organizer can cancel.')
        return _back_to_dashboard(user)
    meeting.status = 'cancelled'
    meeting.save(update_fields=['status'])
    for p in meeting.participants.select_related('user'):
        _notify(
            recipient=p.user,
            title=f'Meeting cancelled: {meeting.title}',
            message=f'The meeting on {meeting.datetime.strftime("%b %d, %Y at %I:%M %p")} was cancelled.',
            link=_meeting_link(meeting),
        )
    messages.success(request, 'Meeting cancelled.')
    return _back_to_dashboard(user)
