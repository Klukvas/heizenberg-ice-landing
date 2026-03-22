from rest_framework import serializers
from .models import DeliveryZone


class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = ('id', 'name', 'delivery_price', 'min_order_amount', 'polygon', 'color')

    def validate_polygon(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("polygon повинен бути GeoJSON об'єктом.")

        # Auto-extract geometry from FeatureCollection/Feature
        value = DeliveryZone._extract_geometry(value)

        geo_type = value.get("type")
        if geo_type not in ("Polygon", "MultiPolygon"):
            raise serializers.ValidationError("polygon.type повинен бути 'Polygon' або 'MultiPolygon'.")
        if not value.get("coordinates"):
            raise serializers.ValidationError("polygon.coordinates не може бути порожнім.")
        try:
            from shapely.geometry import shape
            shape(value)
        except Exception as exc:
            raise serializers.ValidationError(f"Невалідна GeoJSON геометрія: {exc}")
        return value
