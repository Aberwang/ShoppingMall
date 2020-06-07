

from django.urls import path, re_path
from apps.order import views

urlpatterns = [
    path(r'place', views.OrderPlaceView.as_view(), name='place'),  # 提交订单页面显示
    path(r'commit', views.OrderCommitView.as_view(), name='commit'),  # 订单创建
    path(r'buy', views.BuyView.as_view(), name='buy'),  # 订单创建

    path(r'pay', views.OrderPayView.as_view(), name='pay'), # 订单支付
    path(r'check', views.CheckPayView.as_view(), name='pay'), # 订单校验

    re_path(r'^comment/(?P<order_id>.+)$', views.CommentView.as_view(), name='comment'),  # 订单评论
]
