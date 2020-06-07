#_*_coding:utf-8_*_


from django.urls import path, re_path
from apps.cart import views

urlpatterns = [
    re_path(r'^$', views.CartInfoView.as_view(), name='show'),  # 购物车页面

    path('add', views.CartAddView.as_view(), name='add'),
    # path(r'update', views.CartUpdateView.as_view(), name='update'), # 修改购物车中的商品记录
    path(r'delete', views.CartDeleteView.as_view(), name='delete'), # 删除购物车中的商品记录
]
