from django.urls import path
from . import views

app_name = 'milestones'

urlpatterns = [
    path('', views.milestone_list, name='list'),
    path('create/', views.create_milestone, name='create'),
    path('templates/create/', views.create_template, name='template_create'),
    path('templates/<int:template_id>/update/', views.update_template, name='template_update'),
    path('templates/<int:template_id>/apply/', views.apply_template, name='template_apply'),
    path('<int:milestone_id>/delete/', views.delete_milestone, name='delete'),
    path('<int:milestone_id>/', views.milestone_detail, name='detail'),
]
