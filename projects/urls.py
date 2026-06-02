from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('request/<int:supervisor_id>/',        views.request_supervision,  name='request_supervision'),
    path('supervision/<int:req_id>/accept/',    views.accept_supervision,   name='accept_supervision'),
    path('supervision/<int:req_id>/decline/',   views.decline_supervision,  name='decline_supervision'),
    path('<int:project_id>/remove-supervisor/', views.admin_remove_supervisor,    name='remove_supervisor'),
    path('<int:project_id>/remove-reviewer/',   views.admin_remove_reviewer,     name='remove_reviewer'),
    path('<int:project_id>/propose-edit/',      views.student_propose_project_edit, name='propose_edit'),
    path('<int:project_id>/approve-edit/',      views.supervisor_approve_edit,   name='approve_edit'),
    path('<int:project_id>/reject-edit/',       views.supervisor_reject_edit,    name='reject_edit'),
]
