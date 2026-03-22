import json

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import DeliveryZone


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(ModelAdmin):
    list_display = ('name', 'delivery_price', 'min_order_amount', 'color_preview', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('polygon_preview',)

    fieldsets = (
        (None, {
            'fields': ('name', 'delivery_price', 'min_order_amount', 'is_active', 'color'),
        }),
        ('Полігон', {
            'fields': ('polygon', 'polygon_preview'),
            'description': (
                '<div style="background:#f0f9f0;border:1px solid #c3e6c3;border-radius:8px;'
                'padding:16px;margin-bottom:12px;font-size:13px;line-height:1.6;">'
                '<strong>Як отримати координати полігону:</strong><br>'
                '1. Відкрийте <a href="https://geojson.io" target="_blank" '
                'style="color:#1a7a1a;font-weight:bold;">geojson.io</a><br>'
                '2. Знайдіть потрібну область на карті<br>'
                '3. Оберіть інструмент <b>"Draw a polygon"</b> '
                '(іконка п\'ятикутника на панелі праворуч)<br>'
                '4. Клікайте по карті, обводячи зону доставки<br>'
                '5. У правій панелі з\'явиться JSON — скопіюйте об\'єкт '
                '<code>geometry</code> і вставте у поле нижче<br><br>'
                '<strong>Формат:</strong><br>'
                '<code style="background:#e8f5e9;padding:4px 8px;border-radius:4px;">'
                '{"type": "Polygon", "coordinates": [[[lng, lat], [lng, lat], ...]]}'
                '</code><br><br>'
                '<em>Координати: [довгота, широта]. '
                'Перша і остання точка повинні збігатися (замкнутий полігон).</em>'
                '</div>'
            ),
        }),
    )

    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:20px;height:20px;'
            'background-color:{};border:1px solid #ccc;border-radius:3px;"></span> {}',
            obj.color, obj.color
        )
    color_preview.short_description = 'Колір'

    def polygon_preview(self, obj):
        if not obj.polygon or not isinstance(obj.polygon, dict):
            return format_html('<em>Збережіть полігон, щоб побачити превʼю</em>')

        polygon_json = json.dumps(obj.polygon)
        color = obj.color or '#1a4a1a'

        return format_html(
            '<div id="admin-map-preview" style="height:350px;border-radius:8px;'
            'border:1px solid #ccc;margin-top:8px;"></div>'
            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
            '<script>'
            'document.addEventListener("DOMContentLoaded", function() {{'
            '  var mapEl = document.getElementById("admin-map-preview");'
            '  if (!mapEl || mapEl.dataset.init) return;'
            '  mapEl.dataset.init = "1";'
            '  var map = L.map("admin-map-preview").setView([50.45, 30.52], 11);'
            '  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{'
            '    attribution: "&copy; OpenStreetMap"'
            '  }}).addTo(map);'
            '  try {{'
            '    var geojson = {polygon_json};'
            '    var coords = geojson.coordinates[0].map(function(c) {{ return [c[1], c[0]]; }});'
            '    var poly = L.polygon(coords, {{'
            '      color: "{color}", fillColor: "{color}", fillOpacity: 0.3, weight: 2'
            '    }}).addTo(map);'
            '    map.fitBounds(poly.getBounds().pad(0.2));'
            '  }} catch(e) {{ console.error("Polygon preview error:", e); }}'
            '}});'
            '</script>',
            polygon_json=polygon_json,
            color=color,
        )
    polygon_preview.short_description = 'Превʼю на карті'
