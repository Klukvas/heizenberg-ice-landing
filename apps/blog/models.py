from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import convert_to_webp


class BlogPost(models.Model):
    title = models.CharField(max_length=300, verbose_name='Заголовок')
    slug = models.SlugField(unique=True, max_length=300, verbose_name='Slug')
    excerpt = models.TextField(
        max_length=500,
        verbose_name='Короткий опис',
        help_text='Відображається в списку статей та в meta description',
    )
    content = models.TextField(
        verbose_name='Контент',
        help_text='HTML content',
    )
    image = models.ImageField(
        upload_to='blog/',
        blank=True,
        verbose_name='Зображення',
    )
    author = models.CharField(
        max_length=200,
        default='Heizenberg Ice',
        verbose_name='Автор',
    )
    is_published = models.BooleanField(default=False, verbose_name='Опубліковано')
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата публікації',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at']
        verbose_name = 'Стаття'
        verbose_name_plural = 'Статті'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:post-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()

        if self.image and hasattr(self.image, 'file') and hasattr(self.image.file, 'content_type'):
            convert_to_webp(self.image)

        super().save(*args, **kwargs)

    @property
    def meta_title(self):
        return self.title

    @property
    def meta_description(self):
        return self.excerpt
