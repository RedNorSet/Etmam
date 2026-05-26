from django.urls import path
from . import views

app_name = 'submissions'

urlpatterns = [
    path('grade/supervisor/<int:submission_id>/', views.supervisor_grade_submission, name='supervisor_grade'),
    path('grade/reviewer/<int:submission_id>/',  views.reviewer_grade_submission,   name='reviewer_grade'),
    path('status/supervisor/<int:submission_id>/', views.supervisor_update_status,  name='supervisor_status'),
]
