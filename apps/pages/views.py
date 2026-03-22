from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from .models import ContactMessage


class ContactCreateView(APIView):
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        name = request.data.get('name', '').strip()[:200]
        phone = request.data.get('phone', '').strip()[:20]
        message = request.data.get('message', '').strip()[:2000]

        errors = {}
        if not name:
            errors['name'] = "Вкажіть ім'я"
        if not phone:
            errors['phone'] = 'Вкажіть телефон'
        if not message:
            errors['message'] = 'Напишіть повідомлення'

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        ContactMessage.objects.create(
            name=name,
            phone=phone,
            message=message,
        )
        return Response({'success': True})
