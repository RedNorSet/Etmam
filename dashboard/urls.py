from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',            views.index,                name='index'),
    path('student/',    views.student_dashboard,    name='student'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor'),
    path('admin/',      views.admin_dashboard,      name='admin'),
    path('reviewer/',              views.reviewer_dashboard,  name='reviewer'),
    path('supervisor/teams/<int:project_id>/', views.supervisor_team_detail, name='supervisor_team_detail'),
    path('admin/teams/<int:team_id>/', views.admin_team_detail, name='admin_team_detail'),
]
