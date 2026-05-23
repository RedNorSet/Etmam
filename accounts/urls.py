from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',                    views.login_view,         name='login'),
    path('logout/',                   views.logout_view,        name='logout'),
    path('edit/<int:user_id>/',       views.edit_user,          name='edit_user'),
    path('profile/',                  views.supervisor_profile, name='supervisor_profile'),
    path('supervisors/',              views.supervisor_list,    name='supervisor_list'),
    path('supervisors/<int:user_id>/', views.supervisor_detail, name='supervisor_detail'),
]
