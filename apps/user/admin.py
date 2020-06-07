from django.contrib import admin
from apps.user.models import User, Address


admin.site.site_title = "天天生鲜商城后台管理系统"
admin.site.site_header = "天天生鲜商城后台管理系统"


class UserAdmin(admin.ModelAdmin):
    # 设置该表的模块显示哪些字段(注意：不能显示多对多字段)
    list_display = ["username", "phone", "email"]


class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "receiver", "phone", "addr"]
    # 设置所显示的字段是否可以点进去进行编辑操作
    list_display_links = ["user", "receiver", "phone", "addr"]


admin.site.register(User, UserAdmin)
admin.site.register(Address, AddressAdmin)


