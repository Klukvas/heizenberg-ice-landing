from django.db import models


class SiteSettings(models.Model):
    address_pickup = models.TextField(
        verbose_name='Адреса самовивозу',
    )
    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон',
    )
    instagram_url = models.URLField(
        blank=True,
        verbose_name='Instagram URL',
    )
    monobank_token = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Monobank токен',
        help_text='Токен мерчанта з https://api.monobank.ua/ (тестовий) або кабінету ФОП (бойовий)',
    )
    working_hours = models.CharField(
        max_length=200,
        verbose_name='Графік роботи',
    )

    class Meta:
        verbose_name = 'Налаштування сайту'
        verbose_name_plural = 'Налаштування сайту'

    def __str__(self):
        return 'Налаштування сайту'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalidate cache
        from django.core.cache import cache
        cache.delete('pages:site_settings')

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'address_pickup': '',
                'phone': '',
                'working_hours': '',
            }
        )
        return obj


class FAQ(models.Model):
    question = models.TextField(
        verbose_name='Питання',
    )
    answer = models.TextField(
        verbose_name='Відповідь',
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активне',
    )

    class Meta:
        ordering = ['order']
        verbose_name = 'Питання та відповідь'
        verbose_name_plural = 'Питання та відповіді'

    def __str__(self):
        return self.question[:80]


class PageSEO(models.Model):
    page_slug = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Slug сторінки',
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Title',
    )
    description = models.TextField(
        blank=True,
        verbose_name='Description',
    )
    og_image = models.ImageField(
        upload_to='seo/',
        blank=True,
        null=True,
        verbose_name='OG Image',
    )

    class Meta:
        verbose_name = 'SEO сторінки'
        verbose_name_plural = 'SEO сторінок'

    def __str__(self):
        return f'SEO: {self.page_slug}'


class ContactMessage(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="Ім'я",
    )
    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон',
    )
    message = models.TextField(
        verbose_name='Повідомлення',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Створено',
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Повідомлення'
        verbose_name_plural = 'Повідомлення'

    def __str__(self):
        return f'{self.name} — {self.created_at:%d.%m.%Y}'
