from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    path('create/',              views.create_team,   name='create'),
    path('invite/',              views.invite_member, name='invite'),
    path('remove/<int:member_id>/', views.remove_member, name='remove_member'),
]
