"""
URL configuration for inventory_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Inventory Management API",
      default_version='v1',
      description="API documentation for Inventory Management System",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@inventory.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
   path('api/', include('inventory.urls')),
   # Simple landing page
   path('', TemplateView.as_view(template_name='index.html'), name='home'),
   path('register/', TemplateView.as_view(template_name='register.html'), name='register'),
   path('forgot-password/', TemplateView.as_view(template_name='forgot-password.html'), name='forgot_password'),
   path('reset-password/', TemplateView.as_view(template_name='reset-password.html'), name='reset_password'),
   path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
   path('items/', TemplateView.as_view(template_name='items.html'), name='items'),
   path('stock/', TemplateView.as_view(template_name='stock.html'), name='stock'),
   path('requisitions/', TemplateView.as_view(template_name='requisitions.html'), name='requisitions'),
   path('reports/', TemplateView.as_view(template_name='reports.html'), name='reports'),
   path('audit/', TemplateView.as_view(template_name='audit.html'), name='audit'),
   path('roomwise-inventory/', TemplateView.as_view(template_name='roomwise-inventory.html'), name='roomwise_inventory'),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
