from django.urls import path
from .views import DeliveryZoneListView, DeliveryCheckView

urlpatterns = [
    path('zones/', DeliveryZoneListView.as_view(), name='api-zones'),
    path('delivery/check/', DeliveryCheckView.as_view(), name='api-delivery-check'),
]
