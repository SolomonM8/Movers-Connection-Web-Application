"""
URL configuration for movers_connection project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from accounts.views import LandingView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('coverage/', include('coverage.urls')),
    path('jobs/', include('jobs.urls')),
    path('board/', include('board.urls')),
    path('admin-panel/', include('adminpanel.urls')),
    path('privacy/', TemplateView.as_view(template_name='privacy_policy.html'), name='privacy_policy'),
    # Only the socialaccount + provider URLs (signup, connections, google/facebook
    # login+callback) so allauth's own account app never competes with our
    # accounts:login/accounts:register views. allauth.account.urls is still
    # mounted (unlinked from anywhere) purely so reverse("account_login") -- used
    # internally by SignupView's no-pending-signup fallback redirect -- resolves
    # instead of raising NoReverseMatch.
    path('social-auth/', include('allauth.socialaccount.urls')),
    path('social-auth/', include('allauth.socialaccount.providers.google.urls')),
    path('social-auth/', include('allauth.socialaccount.providers.facebook.urls')),
    path('social-auth/fallback/', include('allauth.account.urls')),
    path('', LandingView.as_view(), name='landing'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
