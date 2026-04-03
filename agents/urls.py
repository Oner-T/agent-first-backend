from django.urls import path
from . import views

urlpatterns = [
    path('ask/', views.orchestrate_agent, name='orchestrate_agent'),
    path('history/<uuid:session_id>/', views.get_session_history, name='get_session_history'), # <-- Add this line
]