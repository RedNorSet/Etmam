from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLES = [
        ('student',       'Student'),
        ('supervisor',    'Supervisor'),
        ('administrator', 'Administrator'),
        ('reviewer',      'Reviewer'),
    ]
    GENDERS = [('male', 'Male'), ('female', 'Female')]

    role       = models.CharField(max_length=20, choices=ROLES, default='student')
    gender     = models.CharField(max_length=10, choices=GENDERS, blank=True)
    full_name  = models.CharField(max_length=150, blank=True)
    student_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    department = models.CharField(max_length=100, blank=True)
    avatar     = models.ImageField(upload_to='avatars/', blank=True, null=True)
    can_review    = models.BooleanField(default=False)
    expertise     = models.TextField(blank=True)
    max_teams_supervise = models.PositiveIntegerField(default=2)
    max_teams_review    = models.PositiveIntegerField(default=2)
    available     = models.BooleanField(default=True)
    bio           = models.TextField(blank=True)
    office_hours  = models.CharField(max_length=200, blank=True)
    past_projects = models.TextField(blank=True)

    def is_student(self):       return self.role == 'student'
    def is_supervisor(self):    return self.role == 'supervisor'
    def is_administrator(self): return self.role == 'administrator'
    def is_reviewer(self):      return self.role == 'reviewer' or self.can_review

    def current_load(self):
        return self.supervised_projects.exclude(status='rejected').count()

    def is_at_capacity(self):
        active_load = self.supervised_projects.filter(
            status__in=['draft', 'submitted', 'approved', 'active']
        ).count()
        return active_load >= self.max_teams_supervise

    def current_review_load(self):
        return self.reviewed_projects.count()

    def is_at_review_capacity(self):
        return self.reviewed_projects.count() >= self.max_teams_review

    def __str__(self): return self.full_name or self.username
