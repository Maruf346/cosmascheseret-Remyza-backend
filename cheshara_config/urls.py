from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/v1/', include('accounts.urls')),
    path('api/v1/', include('ai.urls')),
    path('api/v1/', include('business.urls')),
    path('api/v1/', include('communications.urls')),
    path('api/v1/', include('core.urls')),
    path('api/v1/', include('crm.urls')),
    path('api/v1/', include('subscription.urls')),
    path('api/v1/', include('sentdm.urls')),
]
