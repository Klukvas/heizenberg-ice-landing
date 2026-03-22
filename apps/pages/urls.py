from django.urls import path
from . import template_views

app_name = 'pages'

urlpatterns = [
    path('', template_views.index_view, name='index'),
    path('robots.txt', template_views.robots_txt, name='robots'),
    path('contact/submit/', template_views.contact_submit, name='contact-submit'),
]
