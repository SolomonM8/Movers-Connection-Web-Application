from django.urls import path

from . import views

app_name = "coverage"

urlpatterns = [
    path("service-areas/", views.ServiceAreaView.as_view(), name="service_areas"),
    path(
        "api/service-areas/<str:fips>/toggle/",
        views.ToggleServiceAreaAPIView.as_view(),
        name="toggle_service_area",
    ),
    path("map/", views.MapView.as_view(), name="map"),
    path(
        "api/counties/<str:fips>/laborers/",
        views.CountyLaborersAPIView.as_view(),
        name="county_laborers_api",
    ),
]
