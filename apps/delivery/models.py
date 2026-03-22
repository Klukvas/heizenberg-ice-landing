from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

hex_color_validator = RegexValidator(
    r'^#[0-9a-fA-F]{6}$',
    'Введіть коректний HEX колір, наприклад #1a4a1a'
)


class DeliveryZone(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name='Назва зони',
    )
    delivery_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Вартість доставки, ₴',
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Мінімальна сума замовлення, ₴',
    )
    polygon = models.JSONField(
        verbose_name='Полігон (GeoJSON)',
        help_text=(
            'Вставте весь JSON з geojson.io — геометрію буде витягнуто автоматично.'
        ),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
    )
    color = models.CharField(
        max_length=7,
        default='#1a4a1a',
        validators=[hex_color_validator],
        verbose_name='Колір на карті',
        help_text='HEX колір для відображення на карті',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Зона доставки'
        verbose_name_plural = 'Зони доставки'

    def clean(self):
        super().clean()
        if self.polygon:
            if not isinstance(self.polygon, dict):
                raise ValidationError({'polygon': 'Polygon повинен бути JSON об\'єктом.'})

            # Auto-extract geometry from FeatureCollection or Feature
            self.polygon = self._extract_geometry(self.polygon)

            geo_type = self.polygon.get('type')
            if geo_type not in ('Polygon', 'MultiPolygon'):
                raise ValidationError({
                    'polygon': (
                        f'type повинен бути Polygon або MultiPolygon, отримано: "{geo_type}". '
                        'Можна вставляти повний JSON з geojson.io — геометрію буде витягнуто автоматично.'
                    ),
                })
            if not self.polygon.get('coordinates'):
                raise ValidationError({'polygon': 'coordinates не може бути порожнім.'})
            try:
                from shapely.geometry import shape
                shape(self.polygon)
            except Exception as exc:
                raise ValidationError({'polygon': f'Невалідна геометрія: {exc}'})

    @staticmethod
    def _extract_geometry(data):
        """Extract Polygon geometry from FeatureCollection, Feature, or raw geometry."""
        if data.get('type') == 'FeatureCollection':
            features = data.get('features', [])
            if not features:
                raise ValidationError({'polygon': 'FeatureCollection не містить жодного Feature.'})
            if len(features) > 1:
                raise ValidationError({
                    'polygon': (
                        f'FeatureCollection містить {len(features)} обʼєктів. '
                        'Залиште лише один полігон на geojson.io.'
                    ),
                })
            data = features[0]

        if data.get('type') == 'Feature':
            geometry = data.get('geometry')
            if not geometry:
                raise ValidationError({'polygon': 'Feature не містить geometry.'})
            return geometry

        return data

    def __str__(self):
        return self.name
