import logging

from shapely.geometry import Point, shape

logger = logging.getLogger(__name__)


def find_zone_for_coordinates(lat, lng, zones):
    """Find which delivery zone contains the given coordinates."""
    point = Point(lng, lat)
    for zone in zones:
        if not isinstance(zone.polygon, dict):
            logger.error("DeliveryZone id=%s has non-dict polygon: %r", zone.pk, type(zone.polygon))
            continue
        try:
            polygon = shape(zone.polygon)
            if polygon.contains(point):
                return zone
        except Exception as exc:
            logger.error(
                "Failed to parse polygon for DeliveryZone id=%s name=%r: %s",
                zone.pk, zone.name, exc,
            )
            continue
    return None
