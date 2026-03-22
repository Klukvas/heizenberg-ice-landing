from django import forms
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import SiteSettings, FAQ, PageSEO, ContactMessage


class SiteSettingsForm(forms.ModelForm):
    monobank_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full border rounded px-3 py-2',
            'placeholder': 'Вставте токен або залиште порожнім',
            'autocomplete': 'off',
        }),
        help_text='Токен мерчанта з api.monobank.ua (тестовий) або кабінету ФОП (бойовий)',
    )

    clear_monobank_token = forms.BooleanField(
        required=False,
        label='Очистити токен',
        help_text='Поставте галочку щоб видалити збережений токен',
    )

    class Meta:
        model = SiteSettings
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.monobank_token:
            masked = self.instance.monobank_token[:6] + '••••••' + self.instance.monobank_token[-4:]
            self.fields['monobank_token'].widget.attrs['placeholder'] = masked

    def clean_monobank_token(self):
        if self.cleaned_data.get('clear_monobank_token'):
            return ''
        new_token = self.cleaned_data.get('monobank_token', '').strip()
        if not new_token and self.instance:
            return self.instance.monobank_token or ''
        return new_token


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    form = SiteSettingsForm

    fieldsets = (
        ('Контакти', {
            'fields': ('address_pickup', 'phone', 'working_hours', 'instagram_url'),
        }),
        ('Monobank', {
            'fields': ('monobank_token', 'clear_monobank_token', 'monobank_status'),
            'description': (
                '<div style="background:#f0f9f0;border:1px solid #c3e6c3;border-radius:8px;'
                'padding:12px;margin-bottom:8px;font-size:13px;">'
                'Тестовий токен: <a href="https://api.monobank.ua/" target="_blank" '
                'style="color:#1a7a1a;font-weight:bold;">api.monobank.ua</a> → авторизація через QR<br>'
                'Бойовий токен: <a href="https://web.monobank.ua/" target="_blank" '
                'style="color:#1a7a1a;">web.monobank.ua</a> → Підприємець → Еквайринг → API'
                '</div>'
            ),
        }),
    )
    readonly_fields = ('monobank_status',)

    def monobank_status(self, obj):
        if not obj or not obj.monobank_token:
            return format_html(
                '<span style="color:#dc2626;">Не налаштовано</span>'
            )
        return format_html(
            '<span style="color:#16a34a;">Токен встановлено ({}...{})</span>',
            obj.monobank_token[:6], obj.monobank_token[-4:],
        )
    monobank_status.short_description = 'Статус'

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FAQ)
class FAQAdmin(ModelAdmin):
    list_display = ('question', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)


@admin.register(PageSEO)
class PageSEOAdmin(ModelAdmin):
    list_display = ('page_slug', 'title')
    search_fields = ('page_slug', 'title', 'description')


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ('name', 'phone', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    list_editable = ('is_read',)
    readonly_fields = ('name', 'phone', 'message', 'created_at')

    def has_add_permission(self, request):
        return False
