from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('request/<int:supervisor_id>/',        views.request_supervision,  name='request_supervision'),
    path('supervision/<int:req_id>/accept/',    views.accept_supervision,   name='accept_supervision'),
    path('supervision/<int:req_id>/decline/',   views.decline_supervision,  name='decline_supervision'),
    path('<int:project_id>/remove-supervisor/', views.admin_remove_supervisor, name='remove_supervisor'),
    path('<int:project_id>/remove-reviewer/',   views.admin_remove_reviewer,   name='remove_reviewer'),
]
