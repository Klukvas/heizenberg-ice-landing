import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Allowed HTML tags for blog content
ALLOWED_TAGS = {
    'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'b', 'em', 'i', 'u', 's', 'del',
    'a', 'img',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span',
    'figure', 'figcaption',
}

ALLOWED_ATTRS = {'href', 'src', 'alt', 'title', 'class', 'id', 'target', 'rel', 'width', 'height'}

# Patterns to strip
STRIP_PATTERNS = [
    re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<embed[^>]*/?>', re.IGNORECASE),
    re.compile(r'<form[^>]*>.*?</form>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<input[^>]*/?>', re.IGNORECASE),
    re.compile(r'<textarea[^>]*>.*?</textarea>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<button[^>]*>.*?</button>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL),
    re.compile(r'\bon\w+\s*=\s*["\'][^"\']*["\']', re.IGNORECASE),  # on* event handlers
    re.compile(r'\bon\w+\s*=\s*\S+', re.IGNORECASE),  # unquoted on* handlers
    re.compile(r'javascript\s*:', re.IGNORECASE),  # javascript: hrefs
]


@register.filter(name='safe_html')
def safe_html(value):
    """Strip dangerous HTML tags and attributes, keep safe formatting tags."""
    if not value:
        return ''
    result = str(value)
    for pattern in STRIP_PATTERNS:
        result = pattern.sub('', result)
    return mark_safe(result)
