from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLES = [
        ('student',       'Student'),
        ('supervisor',    'Supervisor'),
        ('administrator', 'Administrator'),
        ('reviewer',      'Reviewer'),
    ]
    role       = models.CharField(max_length=20, choices=ROLES, default='student')
    full_name  = models.CharField(max_length=150, blank=True)
    student_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    department = models.CharField(max_length=100, blank=True)
    avatar     = models.ImageField(upload_to='avatars/', blank=True, null=True)
    can_review = models.BooleanField(default=False)
    expertise  = models.TextField(blank=True)
    max_teams  = models.PositiveIntegerField(default=2)
    available  = models.BooleanField(default=True)

    def is_student(self):       return self.role == 'student'
    def is_supervisor(self):    return self.role == 'supervisor'
    def is_administrator(self): return self.role == 'administrator'
    def is_reviewer(self):      return self.role == 'reviewer' or self.can_review

    def current_load(self):
        return self.supervised_projects.filter(status='active').count()

    def is_at_capacity(self):
        return self.current_load() >= self.max_teams

    def __str__(self): return self.full_name or self.username
