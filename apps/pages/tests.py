from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, RequestFactory, override_settings

from apps.catalog.models import Category, Product
from apps.delivery.models import DeliveryZone
from apps.pages.context_processors import site_settings as site_settings_processor
from apps.pages.models import ContactMessage, FAQ, PageSEO, SiteSettings
from apps.pages.sitemaps import StaticSitemap


VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [30.5, 50.4],
            [30.6, 50.4],
            [30.6, 50.5],
            [30.5, 50.5],
            [30.5, 50.4],
        ]
    ],
}


# ── Model Tests ──────────────────────────────────────────────────────────


class SiteSettingsModelTest(TestCase):
    """SiteSettings singleton: pk is always 1, load() creates-or-returns."""

    def test_load_creates_when_missing(self):
        self.assertFalse(SiteSettings.objects.exists())
        obj = SiteSettings.load()
        self.assertEqual(obj.pk, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_load_returns_existing(self):
        SiteSettings.objects.create(
            pk=1,
            address_pickup="Test Address",
            phone="+380000000000",
            working_hours="9-18",
        )
        obj = SiteSettings.load()
        self.assertEqual(obj.pk, 1)
        self.assertEqual(obj.address_pickup, "Test Address")
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_save_forces_pk_one(self):
        obj = SiteSettings(
            pk=999,
            address_pickup="A",
            phone="B",
            working_hours="C",
        )
        obj.save()
        self.assertEqual(obj.pk, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_save_invalidates_cache(self):
        cache.set("pages:site_settings", "stale", 300)
        obj = SiteSettings(address_pickup="X", phone="Y", working_hours="Z")
        obj.save()
        self.assertIsNone(cache.get("pages:site_settings"))

    def test_str(self):
        obj = SiteSettings.load()
        self.assertEqual(str(obj), "Налаштування сайту")


class FAQModelTest(TestCase):
    """FAQ: ordering, __str__ truncation."""

    def test_creation(self):
        faq = FAQ.objects.create(
            question="Як замовити?",
            answer="Через сайт",
            order=1,
        )
        self.assertEqual(faq.question, "Як замовити?")
        self.assertTrue(faq.is_active)

    def test_ordering(self):
        FAQ.objects.create(question="Second", answer="A", order=2)
        FAQ.objects.create(question="First", answer="B", order=1)
        qs = FAQ.objects.values_list("question", flat=True)
        self.assertEqual(list(qs), ["First", "Second"])

    def test_str_truncates_at_80(self):
        long_q = "Q" * 120
        faq = FAQ.objects.create(question=long_q, answer="A")
        self.assertEqual(str(faq), long_q[:80])


class PageSEOModelTest(TestCase):
    """PageSEO: creation, __str__."""

    def test_creation_and_str(self):
        seo = PageSEO.objects.create(
            page_slug="index",
            title="Home Page",
            description="Welcome",
        )
        self.assertEqual(str(seo), "SEO: index")

    def test_unique_slug(self):
        PageSEO.objects.create(page_slug="about", title="About")
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            PageSEO.objects.create(page_slug="about", title="About 2")


class ContactMessageModelTest(TestCase):
    """ContactMessage: defaults, ordering, __str__."""

    def test_creation_defaults(self):
        msg = ContactMessage.objects.create(
            name="Test",
            phone="+380000000000",
            message="Hello",
        )
        self.assertFalse(msg.is_read)
        self.assertIsNotNone(msg.created_at)

    def test_ordering_newest_first(self):
        m1 = ContactMessage.objects.create(name="A", phone="1", message="x")
        m2 = ContactMessage.objects.create(name="B", phone="2", message="y")
        qs = list(ContactMessage.objects.values_list("name", flat=True))
        # newest first
        self.assertEqual(qs, ["B", "A"])

    def test_str_format(self):
        msg = ContactMessage.objects.create(
            name="Ivan",
            phone="+380000000000",
            message="Test message",
        )
        expected = f"Ivan — {msg.created_at:%d.%m.%Y}"
        self.assertEqual(str(msg), expected)


# ── Template-View Tests ──────────────────────────────────────────────────


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
)
class IndexViewTest(TestCase):
    """GET / should return 200 with products, categories, faqs, zones."""

    def setUp(self):
        SiteSettings.objects.create(
            pk=1,
            address_pickup="Addr",
            phone="000",
            working_hours="9-18",
        )
        self.category = Category.objects.create(name="Ice", slug="ice")
        self.product = Product.objects.create(
            name="Classic Ice",
            slug="classic-ice",
            price=Decimal("100.00"),
            weight_kg=Decimal("1.00"),
            category=self.category,
            is_available=True,
        )
        self.faq = FAQ.objects.create(
            question="Q?",
            answer="A.",
            is_active=True,
        )
        self.zone = DeliveryZone.objects.create(
            name="Zone 1",
            delivery_price=Decimal("50.00"),
            polygon=VALID_POLYGON,
            is_active=True,
        )

    def test_index_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_index_context_products(self):
        response = self.client.get("/")
        self.assertIn(self.product, response.context["products"])

    def test_index_context_categories(self):
        response = self.client.get("/")
        self.assertIn(self.category, response.context["categories"])

    def test_index_context_faqs(self):
        response = self.client.get("/")
        self.assertIn(self.faq, response.context["faqs"])

    def test_index_context_zones(self):
        response = self.client.get("/")
        self.assertIn(self.zone, response.context["zones"])


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
)
class RobotsTxtViewTest(TestCase):
    """GET /robots.txt should return text/plain with expected directives."""

    def setUp(self):
        SiteSettings.objects.create(
            pk=1, address_pickup="", phone="", working_hours=""
        )

    def test_content_type(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_disallow_admin(self):
        response = self.client.get("/robots.txt")
        self.assertIn("Disallow: /heizenberg-admin/", response.content.decode())

    def test_disallow_api(self):
        response = self.client.get("/robots.txt")
        self.assertIn("Disallow: /api/", response.content.decode())


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
)
class ContactSubmitViewTest(TestCase):
    """POST /contact/submit/ — form-based contact submission."""

    def setUp(self):
        SiteSettings.objects.create(
            pk=1, address_pickup="", phone="", working_hours=""
        )

    def test_post_valid_creates_message(self):
        response = self.client.post(
            "/contact/submit/",
            {"name": "Test", "phone": "+380000000000", "message": "Hello"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_post_valid_returns_success_html(self):
        response = self.client.post(
            "/contact/submit/",
            {"name": "Test", "phone": "+380000000000", "message": "Hello"},
        )
        content = response.content.decode()
        self.assertIn("Дякуємо", content)

    def test_post_missing_fields_returns_400(self):
        response = self.client.post("/contact/submit/", {"name": "OnlyName"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_get_returns_405(self):
        response = self.client.get("/contact/submit/")
        self.assertEqual(response.status_code, 405)


# ── DRF API View Tests ──────────────────────────────────────────────────


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {"anon": None},
    },
)
class ContactCreateViewAPITest(TestCase):
    """POST /api/contact/ — DRF endpoint for contact messages."""

    def test_post_creates_message(self):
        response = self.client.post(
            "/api/contact/",
            {"name": "API User", "phone": "+380111111111", "message": "Hi"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 1)
        msg = ContactMessage.objects.first()
        self.assertEqual(msg.name, "API User")

    def test_post_missing_name_returns_400(self):
        response = self.client.post(
            "/api/contact/",
            {"phone": "+380111111111", "message": "Hi"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

    def test_post_missing_phone_returns_400(self):
        response = self.client.post(
            "/api/contact/",
            {"name": "X", "message": "Hi"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.json())

    def test_post_missing_message_returns_400(self):
        response = self.client.post(
            "/api/contact/",
            {"name": "X", "phone": "+380111111111"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.json())

    def test_post_empty_body_returns_400(self):
        response = self.client.post(
            "/api/contact/",
            {},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


# ── Context Processor Tests ──────────────────────────────────────────────


class SiteSettingsContextProcessorTest(TestCase):
    """site_settings() returns settings object and current year."""

    def setUp(self):
        cache.clear()

    def test_returns_settings_and_year(self):
        factory = RequestFactory()
        request = factory.get("/")
        ctx = site_settings_processor(request)

        self.assertIn("settings", ctx)
        self.assertIn("current_year", ctx)
        self.assertIsInstance(ctx["settings"], SiteSettings)
        self.assertEqual(ctx["current_year"], date.today().year)

    def test_creates_settings_if_missing(self):
        self.assertFalse(SiteSettings.objects.exists())
        factory = RequestFactory()
        request = factory.get("/")
        ctx = site_settings_processor(request)

        self.assertEqual(ctx["settings"].pk, 1)
        self.assertTrue(SiteSettings.objects.exists())

    def test_caches_settings(self):
        factory = RequestFactory()
        request = factory.get("/")

        # First call populates cache
        site_settings_processor(request)
        cached = cache.get("pages:site_settings")
        self.assertIsNotNone(cached)

        # Second call uses cached value (no extra DB query)
        with self.assertNumQueries(0):
            ctx = site_settings_processor(request)
            self.assertEqual(ctx["settings"].pk, 1)


# ── Sitemap Tests ────────────────────────────────────────────────────────


class StaticSitemapTest(TestCase):
    """StaticSitemap returns expected page names."""

    def test_items(self):
        sitemap = StaticSitemap()
        self.assertEqual(sitemap.items(), ["pages:index"])

    def test_location_resolves(self):
        sitemap = StaticSitemap()
        for item in sitemap.items():
            location = sitemap.location(item)
            self.assertTrue(location.startswith("/"))
