from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',              views.login_view,  name='login'),
    path('logout/',             views.logout_view, name='logout'),
    path('edit/<int:user_id>/', views.edit_user,   name='edit_user'),
]
