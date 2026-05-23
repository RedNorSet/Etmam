from django.db import models
from django.conf import settings


class Team(models.Model):
    name       = models.CharField(max_length=100)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='created_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    def __str__(self): return self.name

    def leader(self):
        m = self.memberships.filter(role='leader').first()
        return m.user if m else None

    def member_count(self):
        return self.memberships.count()


class TeamMember(models.Model):
    ROLES    = [('leader', 'Leader'), ('member', 'Member')]
    STATUS   = [('active', 'Active'), ('pending', 'Pending')]
    team      = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='team_memberships')
    role      = models.CharField(max_length=10, choices=ROLES, default='member')
    status    = models.CharField(max_length=10, choices=STATUS, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'user')

    def __str__(self): return f"{self.user} — {self.team} ({self.role})"
