from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('<int:pk>/open/', views.open, name='open'),
]
