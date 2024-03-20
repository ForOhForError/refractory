from django.urls import path
from .views import RefractoryLoginView

urlpatterns = [
    path('login/', RefractoryLoginView.as_view()),
]