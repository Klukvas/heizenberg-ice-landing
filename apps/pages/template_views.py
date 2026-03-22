from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from apps.catalog.models import Product, Category
from apps.delivery.models import DeliveryZone
from apps.blog.models import BlogPost
from .models import FAQ, PageSEO, ContactMessage


def index_view(request):
    categories = Category.objects.all()
    products = Product.objects.filter(is_available=True).select_related('category')

    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    faqs = FAQ.objects.filter(is_active=True)
    zones = DeliveryZone.objects.filter(is_active=True)
    seo = PageSEO.objects.filter(page_slug='index').first()
    latest_posts = BlogPost.objects.filter(is_published=True)[:3]

    return render(request, 'pages/index.html', {
        'categories': categories,
        'products': products,
        'faqs': faqs,
        'zones': zones,
        'seo': seo,
        'latest_posts': latest_posts,
    })


def robots_txt(request):
    from django.conf import settings as django_settings
    hosts = getattr(django_settings, 'ALLOWED_HOSTS', [])
    domain = hosts[0] if hosts and hosts[0] != '*' else request.get_host()
    content = """User-agent: *
Allow: /
Disallow: /heizenberg-admin/
Disallow: /api/

Sitemap: https://{}/sitemap.xml
""".format(domain)
    return HttpResponse(content, content_type='text/plain')


@require_POST
def contact_submit(request):
    name = request.POST.get('name', '').strip()[:200]
    phone = request.POST.get('phone', '').strip()[:20]
    message = request.POST.get('message', '').strip()[:2000]

    if name and phone and message:
        from apps.orders.models import normalize_phone
        phone = normalize_phone(phone)
        ContactMessage.objects.create(
            name=name,
            phone=phone,
            message=message,
        )
        return HttpResponse(
            '<div class="text-green-400 font-bold p-4">'
            'Дякуємо! Ми зателефонуємо вам найближчим часом.'
            '</div>'
        )

    return HttpResponse(
        '<div class="text-red-400 font-bold p-4">'
        'Будь ласка, заповніть всі поля.'
        '</div>',
        status=400
    )
