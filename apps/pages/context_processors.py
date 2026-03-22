from django.core.cache import cache
from .models import SiteSettings

SITE_SETTINGS_CACHE_KEY = 'pages:site_settings'
SITE_SETTINGS_CACHE_TTL = 60 * 15  # 15 minutes


def site_settings(request):
    obj = cache.get(SITE_SETTINGS_CACHE_KEY)
    if obj is None:
        obj = SiteSettings.load()
        cache.set(SITE_SETTINGS_CACHE_KEY, obj, SITE_SETTINGS_CACHE_TTL)
    return {
        'settings': obj,
        'current_year': __import__('datetime').date.today().year,
    }
