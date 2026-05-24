from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',            views.index,                name='index'),
    path('student/',    views.student_dashboard,    name='student'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor'),
    path('admin/',      views.admin_dashboard,      name='admin'),
    path('reviewer/',   views.reviewer_dashboard,   name='reviewer'),

    # Legacy detail pages (still functional as fallback)
    path('supervisor/teams/<int:project_id>/', views.supervisor_team_detail, name='supervisor_team_detail'),
    path('admin/teams/<int:team_id>/',         views.admin_team_detail,      name='admin_team_detail'),

    # ── Admin inline accordion actions ────────────────────────────────────
    # Team member management
    path('admin/team/<int:team_id>/add-member/',    views.admin_add_member,    name='admin_add_member'),
    path('admin/team/<int:team_id>/change-leader/', views.admin_change_leader, name='admin_change_leader'),

    # Project CRUD
    path('admin/team/<int:team_id>/create-project/',   views.admin_create_project, name='admin_create_project'),
    path('admin/project/<int:project_id>/update/',     views.admin_update_project, name='admin_update_project'),

    # Supervisor assignment
    path('admin/project/<int:project_id>/assign-supervisor/', views.admin_assign_supervisor, name='admin_assign_supervisor'),
    path('admin/project/<int:project_id>/remove-supervisor/', views.admin_remove_supervisor, name='admin_remove_supervisor'),

    # Reviewer assignment
    path('admin/project/<int:project_id>/assign-reviewer/', views.admin_assign_reviewer, name='admin_assign_reviewer'),
    path('admin/project/<int:project_id>/remove-reviewer/', views.admin_remove_reviewer,  name='admin_remove_reviewer'),

    # Student search (JSON)
    path('admin/search-students/', views.admin_search_students, name='admin_search_students'),

    # Team creation & dissolved-team cleanup
    path('admin/create-team/',        views.admin_create_team,            name='admin_create_team'),
    path('admin/delete-dissolved/',   views.admin_delete_dissolved_teams, name='admin_delete_dissolved'),
]
