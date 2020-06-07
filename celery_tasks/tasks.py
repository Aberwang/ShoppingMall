#_*_coding:utf-8_*_

from celery import Celery   # 导入celery
from django.conf import settings


import os
# # 发邮件和处理邮件的操作使用到了Django的配置参数，所以需要Django环境的初始化，在任务处理者一端加这几句
# import os
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ShoppingMall.settings")
# django.setup()

from apps.goods import models

# 创建一个Celery类的实例对象
app = Celery('celery_tasks.tasks', broker='redis://:wl0928@127.0.0.1:6379/7')
# 第一个参数一般写此文件的路径，也可其它
# 第二个参数为redis的ip和端口号，以及要使用的数据库

# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    from django.core.mail import send_mail
    # 发送邮件，使用Django自带的send_email函数
    subject = "天天生鲜商城用户激活"  # 发送邮件的主题
    message = ''  # 发送邮件的正文信息
    from_email = settings.EMAIL_FROM
    recipient_list = [to_email]  # 目标邮箱列表
    html_message = '<h1>Hi，%s, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br/><a href="http://127.0.0.1:8001/user/active/%s">http://127.0.0.1:8001/user/active/%s</a>' % (
    username, token, token)
    send_mail(subject=subject, message=message, from_email=from_email, recipient_list=recipient_list,
              html_message=html_message)


