#_*_coding:utf-8_*_

'''
将login_required封装到了as_view()，（重写as_view()类方法）
控制在地址栏输入url访问时，控制用户先登录再访问
使用此方法的好处是：在urls.py中配置url和之前一样，显得直观，其次是不用载配置url时，重复的写login_required()
'''

from django.contrib.auth.decorators import login_required

class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)