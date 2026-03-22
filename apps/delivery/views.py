from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import DeliveryZone
from .serializers import DeliveryZoneSerializer
from .zone_checker import find_zone_for_coordinates


class DeliveryZoneListView(generics.ListAPIView):
    serializer_class = DeliveryZoneSerializer
    queryset = DeliveryZone.objects.filter(is_active=True)


class DeliveryCheckView(APIView):
    """Check which delivery zone contains given coordinates."""

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')

        if not lat or not lng:
            return Response(
                {'error': 'Параметри lat та lng обовʼязкові'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Невірний формат координат'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (-90 <= lat <= 90):
            return Response(
                {'error': 'lat повинен бути від -90 до 90'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not (-180 <= lng <= 180):
            return Response(
                {'error': 'lng повинен бути від -180 до 180'},
                status=status.HTTP_400_BAD_REQUEST
            )

        zones = DeliveryZone.objects.filter(is_active=True)
        zone = find_zone_for_coordinates(lat, lng, zones)

        if zone:
            return Response({
                'found': True,
                'zone': DeliveryZoneSerializer(zone).data
            })
        return Response({
            'found': False,
            'message': 'На жаль, ваша адреса поза зоною доставки'
        })
