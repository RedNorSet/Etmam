from django.urls import path

from . import views

app_name = 'meetings'

urlpatterns = [
    path('api/events/',                       views.events_api,        name='events_api'),
    path('create/',                           views.create_meeting,    name='create'),
    path('<int:pk>/',                         views.detail,            name='detail'),
    path('<int:pk>/respond/',                 views.respond,           name='respond'),
    path('<int:pk>/reschedule/',              views.propose_reschedule,name='reschedule'),
    path('<int:pk>/cancel/',                  views.cancel_meeting,    name='cancel'),
    path('slot/<int:slot_id>/choose/',        views.choose_slot,       name='choose_slot'),
    path('proposal/<int:proposal_id>/reject/',views.reject_proposal,   name='reject_proposal'),
]
