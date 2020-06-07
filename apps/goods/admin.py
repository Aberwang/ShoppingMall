from django.contrib import admin
from apps.goods import models

from django.utils.safestring import mark_safe
from django.core.cache import cache


class GoodsSKUAdmin(admin.ModelAdmin):
    def deletes(self):
        return mark_safe("<a href="">删除</a>")

    list_display = ["id", "name", "type", "price", "unite", "stock", "sales", "status", deletes]
    list_display_links = ["id", "name", "type", "price", "unite", "stock", "sales", "status", deletes]
    search_fields = ["name", "type", "status"]
    list_filter = ["type", "status"]
    list_per_page = 10

class IndexGoodsBannerAdmin(admin.ModelAdmin):
    list_display = ["sku", "index"]
    list_display_links = ["sku", "index"]


class IndexTypeGoodsBannerAdmin(admin.ModelAdmin):
    list_display = ["sku", "type", "display_type", "index"]
    list_display_links = ["sku", "type", "display_type", "index"]


class IndexPromotionBannerAdmin(admin.ModelAdmin):
    list_display =["name", "url", "index"]
    list_display_links = ["name", "url", "index"]

    # 重写admin.ModelAdmin下的save_model和delete_model方法，使得后台在有数据更新或删除时能够将首页缓存的数据删除
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # 清除首页的缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)

        cache.delete('index_page_data')


admin.site.register(models.GoodsType)
admin.site.register(models.IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(models.IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(models.GoodsSKU, GoodsSKUAdmin)
admin.site.register(models.Goods)
admin.site.register(models.GoodsImage)
admin.site.register(models.IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)


