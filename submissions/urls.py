from django.urls import path
from . import views

app_name = 'submissions'

urlpatterns = [
    path('', views.submission_list, name='submission_list'),
    path('milestones/', views.milestone_list, name='milestone_list'),
    path('milestone/<int:milestone_id>/', views.milestone_detail, name='milestone_detail'),
    path('submissions/', views.submission_list, name='submission_list_legacy'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    path('file/<int:file_id>/download/', views.download_file, name='download_file'),
]
