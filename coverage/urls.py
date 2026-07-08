from django.urls import path

from . import views

app_name = "coverage"

urlpatterns = [
    path("service-areas/", views.ServiceAreaView.as_view(), name="service_areas"),
]
