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
    path('admin/create-team/',      views.admin_create_team,            name='admin_create_team'),
    path('admin/delete-dissolved/', views.admin_delete_dissolved_teams, name='admin_delete_dissolved'),

    # ── Milestone admin CRUD ───────────────────────────────────────────────
    path('admin/milestones/create/',               views.admin_create_milestone, name='admin_create_milestone'),
    path('admin/milestones/<int:milestone_id>/update/', views.admin_update_milestone, name='admin_update_milestone'),
    path('admin/milestones/<int:milestone_id>/delete/', views.admin_delete_milestone, name='admin_delete_milestone'),

    # ── Grade admin actions ────────────────────────────────────────────────
    path('admin/grades/weights/',     views.admin_update_grade_weights, name='admin_update_grade_weights'),
    path('admin/grades/save/',        views.admin_save_all_grades,      name='admin_save_all_grades'),

    # ── Submission admin actions ───────────────────────────────────────────
    path('admin/submissions/<int:submission_id>/grade/',  views.admin_grade_submission,   name='admin_grade_submission'),
    path('admin/submissions/<int:submission_id>/status/', views.admin_submission_status,  name='admin_submission_status'),
    path('admin/submissions/<int:submission_id>/delete/', views.admin_delete_submission,  name='admin_delete_submission'),

    # ── Student submit milestone ───────────────────────────────────────────
    path('student/submit/<int:milestone_id>/', views.student_submit_milestone, name='student_submit_milestone'),
]
