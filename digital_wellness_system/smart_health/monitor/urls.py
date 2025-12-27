from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_page, name="home_page"),
    path("weekday/", views.weekday_page, name="weekday_page"),
    path("weekend/", views.weekend_page, name="weekend_page"),
    path("video_feed/", views.video_feed, name="video_feed"),
    
    # Weekend yoga session routes
    path("weekend/save/", views.save_session, name="save_session"),
    path("weekend/history/", views.session_history, name="session_history"),
    
    # Weekday session routes
    path("weekday/save/", views.save_weekday_session, name="save_weekday_session"),
    path("weekday/reset_session/", views.reset_weekday_session, name="reset_weekday_session"),
    path("weekday/history/", views.weekday_history, name="weekday_history"),
      
    # Combined history route
    path("history/", views.combined_history, name="combined_history"),
]