"""ShoppingMall URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf.urls.static import static
from ShoppingMall import settings

from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^tinymce/', include('tinymce.urls')),  # 富文本编辑器
    path('user/', include(('apps.user.urls', 'apps.user'), namespace='user')),    # 用户模块
    path('cart/', include(('apps.cart.urls', 'apps.cart'), namespace='cart')),     # 购物车模块
    path('order/', include(('apps.order.urls', 'apps.order'), namespace='order')),   # 订单模块
    re_path('', include(('apps.goods.urls', 'apps.goods'), namespace='goods')),   # 商品模块

    re_path(r'^favicon.ico$', RedirectView.as_view(url=r'/static/favicon.ico', permanent=True)),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# 超级用户：root   密码：root123456
# 普通用户的用户名密码设计：user1, user1123 ; user2, user2123