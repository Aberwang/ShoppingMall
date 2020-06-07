#_*_coding:utf-8_*_


from django.urls import path, re_path
from apps.goods import views

urlpatterns = [
    path('index/', views.IndexView.as_view(), name='index'),   # 用户注册页面
    re_path(r'^goods/(?P<goods_id>\d+)$', views.DetailView.as_view(), name='detail'),  # 详情页
    re_path(r'list/(?P<type_id>\d+)/(?P<page>\d+)', views.ListView.as_view(), name='list'),  # 列表页
    re_path(r'search/(?P<page>\d+)', views.SearchView.as_view(), name='search'),
]
