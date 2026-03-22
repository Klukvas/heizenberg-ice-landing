from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import BlogPost


def blog_list(request):
    posts = BlogPost.objects.filter(is_published=True)
    paginator = Paginator(posts, 9)
    page = request.GET.get('page')
    posts_page = paginator.get_page(page)

    return render(request, 'blog/list.html', {
        'posts': posts_page,
        'page_title': 'Блог — Heizenberg Ice',
        'page_description': 'Статті про лід, коктейлі, зберігання та доставку. Корисні поради від Heizenberg Ice.',
    })


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)

    related = BlogPost.objects.filter(
        is_published=True,
    ).exclude(id=post.id)[:3]

    return render(request, 'blog/detail.html', {
        'post': post,
        'related_posts': related,
    })
