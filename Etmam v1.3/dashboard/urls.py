from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',            views.index,                name='index'),
    path('student/',    views.student_dashboard,    name='student'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor'),
    path('admin/',      views.admin_dashboard,      name='admin'),
    path('reviewer/',   views.reviewer_dashboard,   name='reviewer'),

    path('supervisor/teams/<int:project_id>/', views.supervisor_team_detail, name='supervisor_team_detail'),
    path('admin/teams/<int:team_id>/',         views.admin_team_detail,      name='admin_team_detail'),

    path('admin/team/<int:team_id>/add-member/',    views.admin_add_member,    name='admin_add_member'),
    path('admin/team/<int:team_id>/change-leader/', views.admin_change_leader, name='admin_change_leader'),

    path('admin/team/<int:team_id>/create-project/',   views.admin_create_project, name='admin_create_project'),
    path('admin/project/<int:project_id>/update/',     views.admin_update_project, name='admin_update_project'),

    path('admin/project/<int:project_id>/assign-supervisor/', views.admin_assign_supervisor, name='admin_assign_supervisor'),
    path('admin/project/<int:project_id>/remove-supervisor/', views.admin_remove_supervisor, name='admin_remove_supervisor'),

    path('admin/project/<int:project_id>/assign-reviewer/', views.admin_assign_reviewer, name='admin_assign_reviewer'),
    path('admin/project/<int:project_id>/remove-reviewer/', views.admin_remove_reviewer,  name='admin_remove_reviewer'),

    path('admin/search-students/', views.admin_search_students, name='admin_search_students'),

    path('admin/create-team/',      views.admin_create_team,            name='admin_create_team'),
    path('admin/delete-dissolved/', views.admin_delete_dissolved_teams, name='admin_delete_dissolved'),

    path('admin/milestones/create/',               views.admin_create_milestone, name='admin_create_milestone'),
    path('admin/milestones/<int:milestone_id>/update/', views.admin_update_milestone, name='admin_update_milestone'),
    path('admin/milestones/<int:milestone_id>/delete/', views.admin_delete_milestone, name='admin_delete_milestone'),

    path('admin/grades/weights/',     views.admin_update_grade_weights, name='admin_update_grade_weights'),
    path('admin/grades/save/',        views.admin_save_all_grades,      name='admin_save_all_grades'),

    path('admin/users/<int:user_id>/toggle-status/', views.admin_toggle_student_status, name='admin_toggle_student_status'),

    path('admin/submissions/<int:submission_id>/grade/',  views.admin_grade_submission,       name='admin_grade_submission'),
    path('admin/submissions/<int:submission_id>/status/', views.admin_submission_status,      name='admin_submission_status'),
    path('admin/submissions/<int:submission_id>/delete/', views.admin_delete_submission,      name='admin_delete_submission'),
    path('admin/team/<int:team_id>/max-resubmissions/',   views.admin_set_max_resubmissions,  name='admin_set_max_resubmissions'),

    path('student/submit/<int:milestone_id>/', views.student_submit_milestone, name='student_submit_milestone'),

    path('student/task/create/<int:milestone_id>/', views.student_create_task,             name='student_create_task'),
    path('student/task/<int:task_id>/update/',      views.student_update_task,             name='student_update_task'),
    path('student/task/<int:task_id>/delete/',      views.student_delete_task,             name='student_delete_task'),
    path('student/task/<int:task_id>/description/', views.student_update_task_description, name='student_update_task_description'),

    path('archive/',                                        views.archive_view,               name='archive'),
    path('admin/project/<int:project_id>/toggle-archive/', views.admin_toggle_archive,       name='admin_toggle_archive'),
    path('admin/archive/add-project/',                     views.admin_create_archive_project, name='admin_create_archive_project'),
    path('admin/project/<int:project_id>/delete/',         views.admin_delete_archive_project, name='admin_delete_archive_project'),

    path('admin/archive/team/<int:team_id>/add-member/',       views.admin_archive_add_member,    name='admin_archive_add_member'),
    path('admin/archive/member/<int:member_id>/remove/',       views.admin_archive_remove_member, name='admin_archive_remove_member'),
    path('admin/archive/member/<int:member_id>/edit/',         views.admin_archive_edit_member,   name='admin_archive_edit_member'),
    path('admin/archive/member/<int:member_id>/set-leader/',   views.admin_archive_set_leader,    name='admin_archive_set_leader'),

    path('admin/archive/project/<int:project_id>/add-link/',   views.admin_add_archive_link,      name='admin_add_archive_link'),
    path('admin/archive/link/<int:link_id>/delete/',           views.admin_delete_archive_link,   name='admin_delete_archive_link'),

    path('admin/phase/preflight/',  views.admin_phase2_preflight, name='admin_phase2_preflight'),
    path('admin/phase/switch/',    views.admin_switch_phase2,    name='admin_switch_phase2'),
    path('admin/phase/confirm/',   views.admin_confirm_phase2,   name='admin_confirm_phase2'),
    path('admin/phase/cancel/',    views.admin_cancel_phase2,    name='admin_cancel_phase2'),
    path('admin/phase/revert/',    views.admin_revert_phase1,    name='admin_revert_phase1'),
    path('admin/phase/set-date/',  views.admin_set_phase2_date,  name='admin_set_phase2_date'),

    path('student/profile/', views.student_edit_profile, name='student_edit_profile'),
]
