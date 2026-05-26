from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('<int:pk>/open/',  views.open,          name='open'),
    path('mark-all-read/', views.mark_all_read,  name='mark_all_read'),
]
