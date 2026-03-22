import logging
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.delivery.models import DeliveryZone, hex_color_validator
from apps.delivery.serializers import DeliveryZoneSerializer
from apps.delivery.zone_checker import find_zone_for_coordinates

# Square polygon: (30,50) -> (31,50) -> (31,51) -> (30,51) -> (30,50)
# Center ~ (30.5, 50.5)
VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [30.0, 50.0],
            [31.0, 50.0],
            [31.0, 51.0],
            [30.0, 51.0],
            [30.0, 50.0],
        ]
    ],
}

VALID_FEATURE = {
    "type": "Feature",
    "properties": {},
    "geometry": VALID_POLYGON,
}

VALID_FEATURE_COLLECTION = {
    "type": "FeatureCollection",
    "features": [VALID_FEATURE],
}


def _make_zone(
    name="Zone A",
    polygon=None,
    delivery_price="50.00",
    is_active=True,
    color="#1a4a1a",
    save=True,
):
    """Helper: create a DeliveryZone without running model validation."""
    zone = DeliveryZone(
        name=name,
        polygon=polygon or VALID_POLYGON,
        delivery_price=Decimal(delivery_price),
        min_order_amount=Decimal("0.00"),
        is_active=is_active,
        color=color,
    )
    if save:
        zone.save()
    return zone


# ---------------------------------------------------------------------------
# 1. DeliveryZone model
# ---------------------------------------------------------------------------
class DeliveryZoneModelTests(TestCase):
    """Tests for DeliveryZone model basics and clean() validation."""

    def test_creation_and_str(self):
        zone = _make_zone(name="Центр")
        self.assertEqual(str(zone), "Центр")
        self.assertIsNotNone(zone.pk)

    def test_clean_accepts_valid_polygon(self):
        zone = _make_zone(save=False)
        zone.clean()  # should not raise

    def test_clean_validates_geojson_structure(self):
        zone = _make_zone(
            polygon={"type": "Point", "coordinates": [30.0, 50.0]},
            save=False,
        )
        with self.assertRaises(ValidationError) as ctx:
            zone.clean()
        self.assertIn("polygon", ctx.exception.message_dict)

    def test_clean_rejects_invalid_polygon_coordinates(self):
        zone = _make_zone(
            polygon={"type": "Polygon", "coordinates": []},
            save=False,
        )
        with self.assertRaises(ValidationError) as ctx:
            zone.clean()
        self.assertIn("polygon", ctx.exception.message_dict)

    def test_clean_rejects_non_dict(self):
        zone = _make_zone(polygon="not a dict", save=False)
        # polygon field is JSONField; Django stores the string as-is
        zone.polygon = "not a dict"
        with self.assertRaises(ValidationError) as ctx:
            zone.clean()
        self.assertIn("polygon", ctx.exception.message_dict)

    def test_hex_color_validator_accepts_valid(self):
        for color in ("#1a4a1a", "#FFFFFF", "#000000", "#abcdef", "#ABCDEF"):
            hex_color_validator(color)  # should not raise

    def test_hex_color_validator_rejects_invalid(self):
        for color in ("1a4a1a", "#fff", "#GGGGGG", "red", "#12345", "#1234567"):
            with self.assertRaises(ValidationError):
                hex_color_validator(color)


# ---------------------------------------------------------------------------
# 2. GeoJSON auto-extraction (_extract_geometry)
# ---------------------------------------------------------------------------
class ExtractGeometryTests(TestCase):
    """Tests for DeliveryZone._extract_geometry static method."""

    def test_extracts_from_feature_collection(self):
        result = DeliveryZone._extract_geometry(VALID_FEATURE_COLLECTION)
        self.assertEqual(result["type"], "Polygon")
        self.assertEqual(result, VALID_POLYGON)

    def test_extracts_from_feature(self):
        result = DeliveryZone._extract_geometry(VALID_FEATURE)
        self.assertEqual(result["type"], "Polygon")
        self.assertEqual(result, VALID_POLYGON)

    def test_passes_through_raw_polygon(self):
        result = DeliveryZone._extract_geometry(VALID_POLYGON)
        self.assertEqual(result, VALID_POLYGON)

    def test_rejects_empty_feature_collection(self):
        data = {"type": "FeatureCollection", "features": []}
        with self.assertRaises(ValidationError) as ctx:
            DeliveryZone._extract_geometry(data)
        self.assertIn("polygon", ctx.exception.message_dict)

    def test_rejects_multi_feature_collection(self):
        data = {
            "type": "FeatureCollection",
            "features": [VALID_FEATURE, VALID_FEATURE],
        }
        with self.assertRaises(ValidationError) as ctx:
            DeliveryZone._extract_geometry(data)
        self.assertIn("polygon", ctx.exception.message_dict)


# ---------------------------------------------------------------------------
# 3. zone_checker — find_zone_for_coordinates
# ---------------------------------------------------------------------------
class ZoneCheckerTests(TestCase):
    """Tests for the find_zone_for_coordinates helper."""

    def test_returns_zone_when_point_inside(self):
        zone = _make_zone(name="Inside zone")
        # GeoJSON uses (lng, lat) — polygon covers lng 30-31, lat 50-51
        # Point inside: lat=50.5, lng=30.5
        result = find_zone_for_coordinates(lat=50.5, lng=30.5, zones=[zone])
        self.assertEqual(result, zone)

    def test_returns_none_when_point_outside(self):
        zone = _make_zone(name="Outside zone")
        result = find_zone_for_coordinates(lat=0.0, lng=0.0, zones=[zone])
        self.assertIsNone(result)

    def test_handles_invalid_polygon_data_gracefully(self):
        zone = _make_zone(name="Bad zone", polygon={"type": "Polygon", "coordinates": "bad"})
        with self.assertLogs("apps.delivery.zone_checker", level=logging.ERROR) as cm:
            result = find_zone_for_coordinates(lat=50.5, lng=30.5, zones=[zone])
        self.assertIsNone(result)
        self.assertTrue(any("Failed to parse polygon" in msg for msg in cm.output))


# ---------------------------------------------------------------------------
# 4. DeliveryZoneListView API (GET /api/zones/)
# ---------------------------------------------------------------------------
class DeliveryZoneListViewTests(APITestCase):
    """Tests for the zones list endpoint."""

    def test_returns_active_zones(self):
        _make_zone(name="Active Zone", is_active=True)
        response = self.client.get("/api/zones/")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        names = [z["name"] for z in results]
        self.assertIn("Active Zone", names)

    def test_excludes_inactive_zones(self):
        _make_zone(name="Active", is_active=True)
        _make_zone(name="Inactive", is_active=False)
        response = self.client.get("/api/zones/")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        names = [z["name"] for z in results]
        self.assertIn("Active", names)
        self.assertNotIn("Inactive", names)


# ---------------------------------------------------------------------------
# 5. DeliveryCheckView API (GET /api/delivery/check/)
# ---------------------------------------------------------------------------
class DeliveryCheckViewTests(APITestCase):
    """Tests for the delivery check endpoint."""

    def test_returns_zone_when_coordinates_match(self):
        _make_zone(name="Matched zone")
        response = self.client.get("/api/delivery/check/", {"lat": "50.5", "lng": "30.5"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(response.data["zone"]["name"], "Matched zone")

    def test_returns_not_found_when_outside(self):
        _make_zone(name="Far away zone")
        response = self.client.get("/api/delivery/check/", {"lat": "0", "lng": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["found"])

    def test_validates_lat_lng_required(self):
        response = self.client.get("/api/delivery/check/")
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/delivery/check/", {"lat": "50.5"})
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/delivery/check/", {"lng": "30.5"})
        self.assertEqual(response.status_code, 400)

    def test_validates_lat_range(self):
        response = self.client.get("/api/delivery/check/", {"lat": "91", "lng": "30"})
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/delivery/check/", {"lat": "-91", "lng": "30"})
        self.assertEqual(response.status_code, 400)

    def test_validates_lng_range(self):
        response = self.client.get("/api/delivery/check/", {"lat": "50", "lng": "181"})
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/delivery/check/", {"lat": "50", "lng": "-181"})
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_numeric(self):
        response = self.client.get("/api/delivery/check/", {"lat": "abc", "lng": "30"})
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/delivery/check/", {"lat": "50", "lng": "xyz"})
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# 6. DeliveryZoneSerializer
# ---------------------------------------------------------------------------
class DeliveryZoneSerializerTests(TestCase):
    """Tests for DeliveryZoneSerializer validation."""

    def _serialize(self, polygon):
        data = {
            "name": "Test zone",
            "delivery_price": "50.00",
            "min_order_amount": "0.00",
            "polygon": polygon,
            "color": "#1a4a1a",
        }
        return DeliveryZoneSerializer(data=data)

    def test_validate_polygon_accepts_valid_geojson(self):
        serializer = self._serialize(VALID_POLYGON)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_polygon_rejects_invalid(self):
        serializer = self._serialize({"type": "Point", "coordinates": [0, 0]})
        self.assertFalse(serializer.is_valid())
        self.assertIn("polygon", serializer.errors)

    def test_validate_polygon_auto_extracts_from_feature_collection(self):
        serializer = self._serialize(VALID_FEATURE_COLLECTION)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # After validation the polygon should be the raw geometry
        self.assertEqual(serializer.validated_data["polygon"]["type"], "Polygon")
