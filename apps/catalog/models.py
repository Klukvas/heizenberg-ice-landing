import logging
import os
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from PIL import Image

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = 20_000_000  # ~4600x4300 max


def convert_to_webp(image_field, max_width=1200):
    """Convert an image field to WebP format, resizing if necessary."""
    if not image_field or not image_field.name:
        return

    if image_field.name.lower().endswith('.webp'):
        return

    try:
        image_field.seek(0)
        img = Image.open(image_field)
        img.verify()
        image_field.seek(0)
        img = Image.open(image_field)
    except Exception as exc:
        logger.error("Cannot open image %s: %s", image_field.name, exc)
        raise ValidationError("Неможливо обробити завантажене зображення.") from exc

    # Handle transparency correctly
    if img.mode == 'P':
        img = img.convert('RGBA') if 'transparency' in img.info else img.convert('RGB')
    elif img.mode in ('RGBA', 'LA'):
        img = img.convert('RGBA')
    else:
        img = img.convert('RGB')

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=85)
    buffer.seek(0)

    original_name = image_field.name
    new_name = os.path.splitext(os.path.basename(image_field.name))[0] + '.webp'

    image_field.save(new_name, ContentFile(buffer.read()), save=False)

    # Clean up original file if different
    if original_name and original_name != image_field.name:
        try:
            image_field.storage.delete(original_name)
        except Exception:
            pass


class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name='Назва')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        verbose_name='Зображення',
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        ordering = ['order']
        verbose_name = 'Категорія'
        verbose_name_plural = 'Категорії'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image.file, 'content_type'):
            convert_to_webp(self.image)
        super().save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField(max_length=300, verbose_name='Назва')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Опис')
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Ціна, ₴',
    )
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Вага, кг',
    )
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        verbose_name='Зображення',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='Категорія',
    )
    is_available = models.BooleanField(default=True, verbose_name='В наявності')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')

    class Meta:
        ordering = ['order']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товари'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f'/#catalog'  # Single-page app, products are on index

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image.file, 'content_type'):
            convert_to_webp(self.image)
        super().save(*args, **kwargs)
