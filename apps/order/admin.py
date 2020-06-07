from django.contrib import admin
from apps.order.models import OrderGoods, OrderInfo


class OrderInfoAdmin(admin.ModelAdmin):
    list_display = ["user", "order_id", "total_count", "total_price", "order_status"]


class OrderGoodsAdmin(admin.ModelAdmin):
    list_display = ["order", "sku", "count", "price", "comment"]
    list_display_links = ["comment"]

admin.site.register(OrderInfo, OrderInfoAdmin)
admin.site.register(OrderGoods, OrderGoodsAdmin)