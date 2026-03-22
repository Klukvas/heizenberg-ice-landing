from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product, convert_to_webp
from apps.catalog.serializers import ProductSerializer
from apps.catalog.sitemaps import ProductSitemap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_category(*, name="Морозиво", slug="morozyvo", order=0):
    return Category.objects.create(name=name, slug=slug, order=order)


def _make_product(
    category=None,
    *,
    name="Пломбір класичний",
    slug="plombir-klasychnyi",
    price=Decimal("89.00"),
    weight_kg=Decimal("0.50"),
    is_available=True,
    order=0,
):
    if category is None:
        category = _make_category()
    return Product.objects.create(
        name=name,
        slug=slug,
        price=price,
        weight_kg=weight_kg,
        category=category,
        is_available=is_available,
        order=order,
    )


def _make_png_bytes(width=100, height=100, color=(255, 0, 0)):
    """Create a minimal in-memory PNG file and return its bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Category model tests
# ---------------------------------------------------------------------------

class CategoryModelTests(TestCase):

    def test_creation_and_fields(self):
        cat = _make_category(name="Сорбети", slug="sorbety", order=5)
        cat.refresh_from_db()

        self.assertEqual(cat.name, "Сорбети")
        self.assertEqual(cat.slug, "sorbety")
        self.assertEqual(cat.order, 5)

    def test_str(self):
        cat = _make_category(name="Фруктове")
        self.assertEqual(str(cat), "Фруктове")

    def test_ordering_by_order_field(self):
        c2 = _make_category(name="Друга", slug="druga", order=2)
        c1 = _make_category(name="Перша", slug="persha", order=1)
        c3 = _make_category(name="Третя", slug="tretya", order=3)

        qs = list(Category.objects.values_list("slug", flat=True))
        self.assertEqual(qs, ["persha", "druga", "tretya"])

    def test_verbose_names(self):
        self.assertEqual(Category._meta.verbose_name, "Категорія")
        self.assertEqual(Category._meta.verbose_name_plural, "Категорії")


# ---------------------------------------------------------------------------
# Product model tests
# ---------------------------------------------------------------------------

class ProductModelTests(TestCase):

    def test_creation_and_fields(self):
        cat = _make_category()
        prod = _make_product(
            cat,
            name="Шоколадне",
            slug="shokoladne",
            price=Decimal("105.50"),
            weight_kg=Decimal("1.00"),
        )
        prod.refresh_from_db()

        self.assertEqual(prod.name, "Шоколадне")
        self.assertEqual(prod.slug, "shokoladne")
        self.assertEqual(prod.price, Decimal("105.50"))
        self.assertEqual(prod.weight_kg, Decimal("1.00"))
        self.assertEqual(prod.category, cat)
        self.assertTrue(prod.is_available)
        self.assertIsNotNone(prod.created_at)

    def test_str(self):
        prod = _make_product(name="Ванільне", slug="vanilne")
        self.assertEqual(str(prod), "Ванільне")

    def test_ordering_by_order_field(self):
        cat = _make_category()
        _make_product(cat, name="B", slug="b", order=2)
        _make_product(cat, name="A", slug="a", order=1)
        _make_product(cat, name="C", slug="c", order=3)

        slugs = list(Product.objects.values_list("slug", flat=True))
        self.assertEqual(slugs, ["a", "b", "c"])

    def test_get_absolute_url(self):
        prod = _make_product()
        self.assertEqual(prod.get_absolute_url(), "/#catalog")

    def test_verbose_names(self):
        self.assertEqual(Product._meta.verbose_name, "Товар")
        self.assertEqual(Product._meta.verbose_name_plural, "Товари")


# ---------------------------------------------------------------------------
# convert_to_webp tests
# ---------------------------------------------------------------------------

class ConvertToWebpTests(TestCase):

    def _build_product_with_image(self, filename, width, height):
        """Create a saved Product whose image is a real ImageFieldFile."""
        cat = _make_category(
            name=f"webp-cat-{filename}",
            slug=f"webp-cat-{filename}",
        )
        png_data = _make_png_bytes(width=width, height=height)
        uploaded = SimpleUploadedFile(
            filename, png_data, content_type="image/png",
        )
        prod = Product(
            name=filename,
            slug=filename,
            price=Decimal("10.00"),
            weight_kg=Decimal("0.50"),
            category=cat,
        )
        prod.image.save(filename, uploaded, save=False)
        # Do not call prod.save() — we want to invoke convert_to_webp manually
        return prod

    def tearDown(self):
        # Clean up any files created during tests
        import shutil
        from django.conf import settings
        for subdir in ("products", "categories"):
            path = settings.MEDIA_ROOT / subdir
            if path.exists():
                shutil.rmtree(path)

    def test_converts_png_to_webp(self):
        prod = self._build_product_with_image("photo.png", 200, 150)

        convert_to_webp(prod.image)

        self.assertTrue(prod.image.name.endswith(".webp"))
        prod.image.seek(0)
        result = Image.open(prod.image)
        self.assertEqual(result.format, "WEBP")
        self.assertEqual(result.size, (200, 150))

    def test_resizes_wide_image(self):
        prod = self._build_product_with_image("wide.png", 2400, 1600)

        convert_to_webp(prod.image, max_width=1200)

        prod.image.seek(0)
        result = Image.open(prod.image)
        self.assertEqual(result.size[0], 1200)
        self.assertEqual(result.size[1], 800)

    def test_does_not_resize_image_within_max_width(self):
        prod = self._build_product_with_image("small.png", 800, 600)

        convert_to_webp(prod.image, max_width=1200)

        prod.image.seek(0)
        result = Image.open(prod.image)
        self.assertEqual(result.size, (800, 600))

    def test_skips_if_already_webp(self):
        """If the file already has a .webp extension, convert_to_webp is a no-op."""
        cat = _make_category(name="webp-skip", slug="webp-skip")
        webp_data = _make_png_bytes(width=50, height=50)
        uploaded = SimpleUploadedFile(
            "already.webp", webp_data, content_type="image/webp",
        )
        prod = Product(
            name="already-webp",
            slug="already-webp",
            price=Decimal("10.00"),
            weight_kg=Decimal("0.50"),
            category=cat,
        )
        prod.image.save("already.webp", uploaded, save=False)

        convert_to_webp(prod.image)

        # Name should still end with .webp (untouched)
        self.assertTrue(prod.image.name.endswith("already.webp"))

    def test_skips_empty_field(self):
        """Passing None or a field without a name should not raise."""
        convert_to_webp(None)


# ---------------------------------------------------------------------------
# ProductListView API tests
# ---------------------------------------------------------------------------

class ProductListViewTests(APITestCase):

    def setUp(self):
        self.cat_a = _make_category(name="Категорія А", slug="cat-a", order=1)
        self.cat_b = _make_category(name="Категорія Б", slug="cat-b", order=2)

        self.p1 = _make_product(
            self.cat_a, name="Товар 1", slug="tovar-1", order=1,
        )
        self.p2 = _make_product(
            self.cat_b, name="Товар 2", slug="tovar-2", order=2,
        )
        self.unavailable = _make_product(
            self.cat_a, name="Немає", slug="nemaye",
            is_available=False, order=3,
        )

    def test_list_returns_available_products(self):
        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)
        slugs = [p["slug"] for p in response.data["results"]]
        self.assertIn("tovar-1", slugs)
        self.assertIn("tovar-2", slugs)

    def test_unavailable_products_excluded(self):
        response = self.client.get("/api/products/")

        slugs = [p["slug"] for p in response.data["results"]]
        self.assertNotIn("nemaye", slugs)

    def test_filter_by_category_slug(self):
        response = self.client.get("/api/products/", {"category": "cat-a"})

        self.assertEqual(response.status_code, 200)
        slugs = [p["slug"] for p in response.data["results"]]
        self.assertEqual(slugs, ["tovar-1"])

    def test_filter_nonexistent_category_returns_empty(self):
        response = self.client.get("/api/products/", {"category": "fake"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])


# ---------------------------------------------------------------------------
# ProductSerializer tests
# ---------------------------------------------------------------------------

class ProductSerializerTests(TestCase):

    def test_serialized_fields(self):
        cat = _make_category(name="Тести", slug="testy")
        prod = _make_product(cat, name="Серіалізований", slug="serializovanyi")

        data = ProductSerializer(prod).data

        expected_fields = {
            "id", "name", "slug", "description", "price",
            "weight_kg", "image", "category", "is_available",
        }
        self.assertEqual(set(data.keys()), expected_fields)

    def test_nested_category(self):
        cat = _make_category(name="Вкладена", slug="vkladena")
        prod = _make_product(cat, name="Продукт", slug="produkt")

        data = ProductSerializer(prod).data

        self.assertIsInstance(data["category"], dict)
        self.assertEqual(data["category"]["slug"], "vkladena")
        self.assertEqual(data["category"]["name"], "Вкладена")
        self.assertIn("id", data["category"])
        self.assertIn("image", data["category"])

    def test_price_is_string_decimal(self):
        prod = _make_product(price=Decimal("123.45"), slug="decimal-test")
        data = ProductSerializer(prod).data
        self.assertEqual(data["price"], "123.45")


# ---------------------------------------------------------------------------
# ProductSitemap tests
# ---------------------------------------------------------------------------

class ProductSitemapTests(TestCase):

    def test_items_returns_only_available(self):
        cat = _make_category(name="Сайтмап", slug="saitmap")
        avail = _make_product(cat, name="Є", slug="ye", is_available=True, order=1)
        _make_product(cat, name="Нема", slug="nema", is_available=False, order=2)

        sm = ProductSitemap()
        items = list(sm.items())

        self.assertEqual(items, [avail])

    def test_items_ordered_by_order_then_id(self):
        cat = _make_category(name="Порядок", slug="poryadok")
        p2 = _make_product(cat, name="Другий", slug="druhyi", order=2)
        p1 = _make_product(cat, name="Перший", slug="pershyi", order=1)
        p3 = _make_product(cat, name="Третій", slug="tretiy", order=3)

        sm = ProductSitemap()
        items = list(sm.items())

        self.assertEqual(items, [p1, p2, p3])

    def test_lastmod_returns_created_at(self):
        prod = _make_product(slug="lastmod-test")

        sm = ProductSitemap()
        self.assertEqual(sm.lastmod(prod), prod.created_at)
