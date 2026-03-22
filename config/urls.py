from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from apps.pages.sitemaps import StaticSitemap
from apps.catalog.sitemaps import ProductSitemap
from apps.blog.sitemaps import BlogSitemap

sitemaps = {
    'static': StaticSitemap,
    'products': ProductSitemap,
    'blog': BlogSitemap,
}

urlpatterns = [
    path('heizenberg-admin/', admin.site.urls),
    path('api/', include('apps.catalog.api_urls')),
    path('api/', include('apps.orders.api_urls')),
    path('api/', include('apps.delivery.api_urls')),
    path('api/', include('apps.pages.api_urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('', include('apps.blog.urls')),
    path('', include('apps.pages.urls')),
    path('', include('apps.orders.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
