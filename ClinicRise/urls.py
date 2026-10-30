"""
URL configuration for ClinicRise project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def api_root(request):
    return JsonResponse({
        'service': 'ClinicRise API',
        'status': 'online',
        'version': '1.0.0',
        'endpoints': {
            'admin': '/admin/',
            'auth': '/api/auth/',
            'practices': '/api/practices/',
            'websites': '/api/websites/',
            'leads': '/api/leads/',
            'bookings': '/api/bookings/',
            'billing': '/api/billing/',
            'analytics': '/api/analytics/',
            'security': '/api/security/',
            'gbp': '/api/gbp/',
            'whatsapp': '/api/whatsapp/',
            'patients': '/api/patients/',
            'crm': '/api/crm/',
            'reports': '/api/reports/',
        }
    })


urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/practices/', include('practices.urls')),
    path('api/websites/', include('websites.urls')),
    path('api/leads/', include('leads.urls')),
    path('api/bookings/', include('bookings.urls')),
    path('api/billing/', include('billing.urls')),
    path('api/analytics/', include('analytics.urls')),
    path('api/security/', include('security.urls')),
    path('api/gbp/', include('gbp.urls')),
    path('api/whatsapp/', include('whatsapp.urls')),
    path('api/patients/', include('patients.urls')),
    path('api/crm/', include(('patients.urls', 'crm'), namespace='crm')),
    path('api/reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



