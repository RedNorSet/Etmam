from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    path('create/',                      views.create_team,        name='create'),
    path('invite/',                      views.invite_member,      name='invite'),
    path('accept/<int:member_id>/',      views.accept_invite,      name='accept_invite'),
    path('decline/<int:member_id>/',     views.decline_invite,     name='decline_invite'),
    path('remove/<int:member_id>/',      views.remove_member,      name='remove_member'),
    path('leave/',                       views.leave_team,         name='leave'),
    path('delete/',                      views.delete_team,        name='delete'),
    path('search-students/',             views.search_students,    name='search_students'),
    path('dissolve/<int:team_id>/',           views.admin_dissolve_team,  name='dissolve'),
    path('admin-remove/<int:member_id>/',     views.admin_remove_member,  name='admin_remove_member'),
    path('admin-cancel-invite/<int:member_id>/', views.admin_cancel_invite, name='admin_cancel_invite'),
]
