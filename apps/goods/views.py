from django.shortcuts import render, redirect
from django.views.generic import View
from django.core.cache import cache
from apps.goods import models
from django_redis import get_redis_connection
from django.urls import reverse
from apps.order.models import OrderGoods
from django.core.paginator import Paginator
from django.db.models import Q


class IndexView(View):
    '''首页'''
    def get(self, request):
        '''显示首页'''
        context = cache.get('index_page_data')
        if context is None:
            # 获取商品种类信息
            types = models.GoodsType.objects.all()
            # 获取首页轮播商品信息
            goods_banners = models.IndexGoodsBanner.objects.all().order_by('index')
            # 获取首页促销活动信息
            promotion_banners = models.IndexPromotionBanner.objects.all().order_by('index')
            # 获取首页分类商品展示信息
            for i in types:
                # 获取type种类首页分类商品的图片展示信息
                image_banners = models.IndexTypeGoodsBanner.objects.filter(type=i, display_type=1).order_by('index')
                # 获取type种类首页分类商品的文字展示信息
                title_banners = models.IndexTypeGoodsBanner.objects.filter(type=i, display_type=0).order_by('index')

                # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
                i.image_banners = image_banners
                i.title_banners = title_banners

            context = {'types': types,
                       'goods_banners': goods_banners,
                       'promotion_banners': promotion_banners,
                    }

            cache.set('index_page_data', context, 3600)

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 存在就更新，不存在就添加
        context.update(cart_count=cart_count)

        return render(request, 'index.html', context)


class DetailView(View):
    """商品详情页视图"""
    def get(self, request, goods_id):
        try:
            goods_sku = models.GoodsSKU.objects.get(id=goods_id)
        except:
            return redirect(reverse('goods:index'))
        # 获取商品的分类信息
        types = models.GoodsType.objects.all()
        # 获取商品的评论信息
        sku_orders = OrderGoods.objects.filter(sku=goods_sku).exclude(comment='')
        # 获取推荐新品的商品信息
        new_skus = models.GoodsSKU.objects.filter(type=goods_sku.type).order_by('-create_time')[:3]
        # 获取同一个SPU的其他规格商品信息
        same_spu_skus = models.GoodsSKU.objects.filter(goods=goods_sku.goods).exclude(id=goods_id)

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户的历史记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 移除列表中的goods_id
            conn.lrem(history_key, 0, goods_id)
            # 把goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条信息
            conn.ltrim(history_key, 0, 7)

        context = {'sku': goods_sku,
                   'types': types,
                   'sku_orders': sku_orders,
                   'new_skus': new_skus,
                   'same_spu_skus': same_spu_skus,
                   'cart_count': cart_count}

        return render(request, 'detail.html', context)


# url设计：/list/种类id/页码？sort=排序方式
class ListView(View):
    '''列表页'''
    def get(self, request, type_id, page):
        '''显示列表页'''
        try:
            type = models.GoodsType.objects.get(id=type_id)
        except:
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = models.GoodsType.objects.all()

        # 获取排序的方式  获取分类商品的信息
        sort = request.GET.get('sort')

        if sort == 'price':
            skus = models.GoodsSKU.objects.filter(type=type, status=1).order_by('price')
        elif sort == 'hot':
            skus = models.GoodsSKU.objects.filter(type=type, status=1).order_by('-sales')
        else:
            sort = 'default'
            skus = models.GoodsSKU.objects.filter(type=type, status=1).order_by('-id')

        # 对数据进行分页
        paginator = Paginator(skus, 8)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page <= 0:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        skus_page = paginator.page(page)

        # 进行页码的控制，页面上最多显示5个页码
        # 1.总页数小于5页，页面上显示所有页码
        # 2.如果当前页是前3页，显示1-5页
        # 3.如果当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 获取新品信息
        new_skus = models.GoodsSKU.objects.filter(type=type).order_by('-create_time')[:3]

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        context = {'type': type, 'types': types,
                   'skus_page': skus_page,
                   'new_skus': new_skus,
                   'cart_count': cart_count,
                   'pages': pages,
                   'sort': sort}

        return render(request, 'list.html', context)


class SearchView(View):
    """搜索视图"""
    def get(self, request, page):
        keywords = request.GET.get('keywords', None)
        if keywords == None:
            return redirect(reverse('goods:index'))

        sort = request.GET.get('sort', 'default')
        # 获取商品种类信息
        types = models.GoodsType.objects.all()

        all_goods = models.GoodsSKU.objects.filter(status=1)
        search_goods = all_goods.filter(Q(name__icontains=keywords)|Q(desc__icontains=keywords))

        if sort == 'price':
            search_goods = search_goods.order_by('price')
        elif sort == 'hot':
            search_goods = search_goods.order_by('-sales')
        else:
            search_goods = search_goods.order_by('-id')

        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page <=0:
            page = 1

        # 对数据进行分页
        paginator = Paginator(search_goods, 6)

        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page <= 0:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        skus_page = paginator.page(page)

        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 获取新品信息
        new_skus = models.GoodsSKU.objects.all().order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context = {'skus_page': skus_page,
                   'cart_count': cart_count,
                   'new_skus':new_skus,
                   'pages': pages,
                   'keywords':keywords,
                   'sort': sort,
                   'types':types,
        }

        return render(request, 'search.html', context)

