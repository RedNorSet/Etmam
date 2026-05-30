from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',                    views.login_view,         name='login'),
    path('logout/',                   views.logout_view,        name='logout'),
    path('add/',                      views.add_user,           name='add_user'),
    path('edit/<int:user_id>/',       views.edit_user,          name='edit_user'),
    path('delete/<int:user_id>/',     views.delete_user,        name='delete_user'),
    path('profile/',                  views.supervisor_profile, name='supervisor_profile'),
]
