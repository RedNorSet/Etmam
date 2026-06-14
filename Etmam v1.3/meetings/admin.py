from django.contrib import admin
from .models import Meeting, MeetingParticipant, RescheduleProposal, ProposedSlot

class ParticipantInline(admin.TabularInline):
    model = MeetingParticipant
    extra = 0

class SlotInline(admin.TabularInline):
    model = ProposedSlot
    extra = 0

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display  = ('title', 'project', 'importance', 'datetime', 'status', 'scheduled_by')
    list_filter   = ('importance', 'status')
    search_fields = ('title', 'project__title')
    inlines       = [ParticipantInline]

@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(admin.ModelAdmin):
    list_display  = ('meeting', 'user', 'response', 'responded_at')
    list_filter   = ('response',)
    search_fields = ('meeting__title', 'user__username', 'user__full_name')

@admin.register(RescheduleProposal)
class RescheduleProposalAdmin(admin.ModelAdmin):
    list_display  = ('meeting', 'proposed_by', 'status', 'created_at')
    list_filter   = ('status',)
    inlines       = [SlotInline]
