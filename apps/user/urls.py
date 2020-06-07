from django.urls import path, re_path
from apps.user import views


urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),   # 用户注册页面
    path('login/', views.LoginView.as_view(), name='login'),   # 用户注册页面
    re_path('active/(?P<token>.*)$', views.ActiveView.as_view(), name='active'),   # 用户账号激活路由
    path('logout/', views.LogoutView.as_view(), name='logout'),   # 用户注销登录路由

    re_path(r'^$', views.UserInfoView.as_view(), name='users'),  # 用户中心-信息页
    re_path(r'^order/(?P<page>\d+)$', views.UserOrderView.as_view(), name='order'),  # 用户中心-订单页
    path(r'address/', views.AddressView.as_view(), name='address'),  # 用户中心-地址页

    path(r'get_valid_img/', views.get_valid_img),

]
