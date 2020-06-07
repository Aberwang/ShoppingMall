#_*_coding:utf-8_*_


'''
创建一个模型表的基类
由于许多都需要用到下面3个字段，所以将其抽象出一个基类，让需要有此字段的表直接继承即可
'''

from django.db import models

class BaseModel(models.Model):
    '''模型抽象基类'''
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    is_delete = models.BooleanField(default=False, verbose_name='删除标记')

    class Meta:
        # 说明这个类是一个抽象模型类
        abstract = True