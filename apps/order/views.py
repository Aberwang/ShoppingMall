from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from django.urls import reverse
from django_redis import get_redis_connection
from django.db import transaction
from django.http import JsonResponse
from datetime import datetime

from alipay import AliPay

from apps.goods.models import GoodsSKU, GoodsType
from apps.user.models import Address
from apps.order.models import OrderInfo, OrderGoods
from utils.mixin import LoginRequiredMixin


class OrderPlaceView(LoginRequiredMixin, View):
    '''提交商品订单页面显示'''
    def post(self,request):
        # 获取登录的用户
        user = request.user

        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids')

        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id

        # 遍历sku_ids获取用户要购买商品的信息
        total_count = 0
        total_price = 0
        skus = []
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户所要购买的商品的数量
            count = conn.hget(cart_key, sku_id)
            count = int(count)
            # 计算商品小计
            amount = sku.price*count
            # 动态给sku增加属性count，保存购买商品的数量
            sku.count = count
            # 动态的给sku增加属性amount，保存每种购买商品的小计
            sku.amount = amount
            skus.append(sku)
            # 累加计算商品的总数量和总价值
            total_count += count
            total_price += amount

        transit_price = 10

        # 实付款
        total_pay = total_price + transit_price

        # 获取用户的收货地址
        addrs = Address.objects.filter(user=user)

        sku_ids = ','.join(sku_ids)  # [1,25]->1,25
        context = {'skus': skus,
                   'total_count': total_count,
                   'total_price': total_price,
                   'transit_price': transit_price,
                   'total_pay': total_pay,
                   'addrs': addrs,
                   'sku_ids': sku_ids}

        return render(request, 'place_order.html', context)


class BuyView(LoginRequiredMixin, View):
    """点击立即购买生成订单视图"""
    def post(self, request):
        user = request.user
        # 获取参数sku_id
        sku_id = request.POST.get('sku_id', None)
        goods_count = request.POST.get('buy_count', 1)
        goods_obj = GoodsSKU.objects.get(id=sku_id)
        price = goods_obj.price

        total_price = int(price)*int(goods_count)
        transit_price = 10
        # 实付款
        total_pay = total_price + transit_price

        addrs = Address.objects.filter(user=user)

        context = {'sku': goods_obj,
                   'total_count': goods_count,
                   'total_price': total_price,
                   'transit_price': transit_price,
                   'total_pay': total_pay,
                   'addrs': addrs,
                   'sku_ids': sku_id}
        return render(request, 'buy_order.html', context)


# 前端传递的参数:地址id(addr_id) 支付方式(pay_method) 用户要购买的商品id字符串(sku_ids)
# mysql事务: 一组sql操作，要么都成功，要么都失败
class OrderCommitView(View):
    '''订单创建'''
    @transaction.atomic
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # 订单id: 年月日时分秒+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置一个事务保存点
        save_id = transaction.savepoint()

        try:
            # todo: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price,
                                             )

            # todo: 用户的订单中有几种商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # 对应的sql语句为：select * from df_goods_goodssku where id=sku_id for update
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except:
                    # 商品不存在
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                # 从redis中获取用户所要购买的商品的数量
                count = conn.hget(cart_key, sku_id)

                # todo: 向df_order_goods表中添加一条记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)

                # todo: 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo: 累加计算订单商品的总数量和总价格
                amount = sku.price * int(count)
                total_count += int(count)
                total_price += amount

            # todo: 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            # 有错误就进行事务回滚
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 没有失败，就提交事务
        transaction.savepoint_commit(save_id)

        # todo: 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res': 5, 'message': '创建成功'})



class OrderCommitView1(View):
    '''# 使用乐观锁的提交订单视图'''
    @transaction.atomic
    def post(self, request):
        '''订单创建'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})

        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res':1, 'errmsg':'参数不完整'})

        # 校验支付方式
        # if pay_method not in models.OrderInfo.PAY_METHODS.keys():
        #     return JsonResponse({'res':2, 'errmsg':'非法的支付方式'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            # 地址不存在
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # todo: 创建订单核心业务

        # 组织参数
        # 订单id: 20171122181630+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

        # 运费
        transit_price = 10.00

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # todo: 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 循环3次进行尝试，如果3次都不能创建订单成功，就认为真正失败。
                # （循环3次是为了解决虽然一个用户的下单修改了库存导致另一用户查询时的库存和他校验时的库存不一样，但库存有足够的情况）
                # 一般在有库存的情况下，循环3次能够创建订单成功的概率很大
                for i in range(3):
                    # 获取商品的信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        # 商品不存在
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4, 'errmsg':'商品不存在'})

                    # 从redis中获取用户所要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)
                    print(count, type(count))

                    # todo: 判断商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6, 'errmsg':'商品库存不足'})

                    # todo: 更新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # print('user:%d times:%d stock:%d' % (user.id, i, sku.stock))

                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock = orgin_stock

                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 尝试的第3次
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败2'})
                        continue

                    # todo: 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # todo: 累加计算订单商品的总数量和总价格
                    amount = sku.price*int(count)
                    total_count += int(count)
                    total_price += amount

                    # 跳出循环
                    break

            # todo: 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            print(e)
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7, 'errmsg':'下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # todo: 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 5, 'message': '创建成功'})


class OrderPayView(View):
    '''订单支付'''
    def post(self, request):
        '''订单支付'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        app_private_key_string="""-----BEGIN RSA PRIVATE KEY-----
MIIEuwIBADANBgkqhkiG9w0BAQEFAASCBKUwggShAgEAAoIBAQDC+X0j0BGRHgcO2UHsAj01JODOqzJFx0xBbkSbxLK9+ND52cSKuLNRWNzyhU2mIZrXBZECguDOKTzJwm5ZtbD6zV7ZggSyTEwJCpHBQR+0ubPZxQT9br0f7RXQya9KCJ5lb4xdSIbePjx0FvTGB249fROGRwVnpH5yPajzJAMZk2EEKUNyhgyhG2B5H9QygZyWDquXXF69oBk+29fzEQRLnPxpdwrzSmElA7Qvy2WKpQbcbu2xKvhRXhQVJCNjLn1f//wwE5WpVUIcdjQL08K5Rp/KXaEJUbQ+70OSpg6F6P9+kdn/XnNk/1cYO9UIGQtC5Eu6c9+8qJkFeWe18anZAgMBAAECgf94VYLml4RADEhO4cfN4ZPlON2GsCJW7qoht+ygNsYaeXaAveaPt270xeOXyq4h2pu2Gbll02Dr3Ien/lgdBgY0xIvFsnkzkeNbsSpEG+11nSdjQDXUNISFL85HDjMhfjBEapQ2/ow+niqxe3mWvv9K8+cY+LxdOyjPWT7s0U0Yeskt5h/x/DrV6yR8ubbAYJGNTL61qKFIT8qmZr4qQV51SnBJmtEsz3IIXKIOWuNFQlG4Ul9M2WtYqxr0QSLCK5B1IAZYx3JCda3DCGeZ4hTWTI8NigY5XdLl9BntlHTRqXWqwWzWDdycfcwFGghWMkD4i3S3PWpaDP400c2XpRkCgYEA7G8Bm1BRSLa3SKtLp4Wchjgy5Xr76Okw55WBUm6Q/x4kV+GwvqlHpzsqd3J1i2cocRaJiufUIHhk2Nv1iZX3Z+Ui15BKnClHIAFgLDhfG2F7O+ojf8UODNaiWhOy3iYb4xm73iB5StP5er1VRaIs3Lqw/ncUej8+Lxl39uh60WcCgYEA0xwlizi2GhRG9r3XFtbftUQl0w7CvtYmKZ9RyKaHQZdWyNv1HaiWyMAIxCnpYti3lC/LT/S6Ig/riZtvQ+hDheFxbMVeX4NysFRDILkQtmDmSwB5MdpQidBbfsBG0cDTI/ZPWoHDn2MVZt5OK9o1wbRGDaazb99+6yAoT7rqYr8CgYA46Cb82QIXfFL1HLWi5pfb/l7RuR402xu4QdXUn2Qq43hf5qSB34CtkaIRCe2c1gF35rLISjBWeGPdhmO87+mSiiYuuD4dBBpoa6xYOGE71+SvcRWGRUmycV62S5N7wLRpnuIG/s3y4r5jenqxve0KW60KMmMtYVd4QqsLNL2K9QKBgGtqTOgTyQRoANuXKJPkbRtMO3qybgCv8ecHu5M+uF91Y6D72jJnD6HBpDQ7pxa2cmIiF27tdK/ULeJshialTYYXeaEAo84xke+KUEWcJJbHoyXSbdgh3wzgSU2rA93CISyRLTs9/41f2wnmXxwNAYE3+tUDVxW7QFbem+RFlPD9AoGBAM3PvzZ8EBRt3bjOuWEWAWQJJiMUbSNKigcUdUt6z/wFwqtiKXSYaQMZ9kuf5aoUT5Dy9OjgZN16UmhURBKfacy+Ko4+6V5oLm4Plfw1jp/Aa7MrZmmGzMRLd1bTDeA3bTjh00g3wTl8b5qQKCdnI4lErWR4nCjky+XsZ/rLPh7u
-----END RSA PRIVATE KEY-----"""

        alipay_public_key_string="""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwvl9I9ARkR4HDtlB7AI9NSTgzqsyRcdMQW5Em8SyvfjQ+dnEirizUVjc8oVNpiGa1wWRAoLgzik8ycJuWbWw+s1e2YIEskxMCQqRwUEftLmz2cUE/W69H+0V0MmvSgieZW+MXUiG3j48dBb0xgduPX0ThkcFZ6R+cj2o8yQDGZNhBClDcoYMoRtgeR/UMoGclg6rl1xevaAZPtvX8xEES5z8aXcK80phJQO0L8tliqUG3G7tsSr4UV4UFSQjYy59X//8MBOVqVVCHHY0C9PCuUafyl2hCVG0Pu9DkqYOhej/fpHZ/15zZP9XGDvVCBkLQuRLunPfvKiZBXlntfGp2QIDAQAB
-----END PUBLIC KEY-----"""

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016102200737971", # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            alipay_public_key_string = alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price+order.transit_price # Decimal
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id, # 订单id
            total_amount=str(total_pay), # 支付总金额
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})


# ajax post
# 前端传递的参数:订单id(order_id)
# /order/check
class CheckPayView(View):
    '''查看订单支付的结果'''
    def post(self, request):
        '''查询支付结果'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        app_private_key_string = """-----BEGIN RSA PRIVATE KEY-----
MIIEuwIBADANBgkqhkiG9w0BAQEFAASCBKUwggShAgEAAoIBAQDC+X0j0BGRHgcO2UHsAj01JODOqzJFx0xBbkSbxLK9+ND52cSKuLNRWNzyhU2mIZrXBZECguDOKTzJwm5ZtbD6zV7ZggSyTEwJCpHBQR+0ubPZxQT9br0f7RXQya9KCJ5lb4xdSIbePjx0FvTGB249fROGRwVnpH5yPajzJAMZk2EEKUNyhgyhG2B5H9QygZyWDquXXF69oBk+29fzEQRLnPxpdwrzSmElA7Qvy2WKpQbcbu2xKvhRXhQVJCNjLn1f//wwE5WpVUIcdjQL08K5Rp/KXaEJUbQ+70OSpg6F6P9+kdn/XnNk/1cYO9UIGQtC5Eu6c9+8qJkFeWe18anZAgMBAAECgf94VYLml4RADEhO4cfN4ZPlON2GsCJW7qoht+ygNsYaeXaAveaPt270xeOXyq4h2pu2Gbll02Dr3Ien/lgdBgY0xIvFsnkzkeNbsSpEG+11nSdjQDXUNISFL85HDjMhfjBEapQ2/ow+niqxe3mWvv9K8+cY+LxdOyjPWT7s0U0Yeskt5h/x/DrV6yR8ubbAYJGNTL61qKFIT8qmZr4qQV51SnBJmtEsz3IIXKIOWuNFQlG4Ul9M2WtYqxr0QSLCK5B1IAZYx3JCda3DCGeZ4hTWTI8NigY5XdLl9BntlHTRqXWqwWzWDdycfcwFGghWMkD4i3S3PWpaDP400c2XpRkCgYEA7G8Bm1BRSLa3SKtLp4Wchjgy5Xr76Okw55WBUm6Q/x4kV+GwvqlHpzsqd3J1i2cocRaJiufUIHhk2Nv1iZX3Z+Ui15BKnClHIAFgLDhfG2F7O+ojf8UODNaiWhOy3iYb4xm73iB5StP5er1VRaIs3Lqw/ncUej8+Lxl39uh60WcCgYEA0xwlizi2GhRG9r3XFtbftUQl0w7CvtYmKZ9RyKaHQZdWyNv1HaiWyMAIxCnpYti3lC/LT/S6Ig/riZtvQ+hDheFxbMVeX4NysFRDILkQtmDmSwB5MdpQidBbfsBG0cDTI/ZPWoHDn2MVZt5OK9o1wbRGDaazb99+6yAoT7rqYr8CgYA46Cb82QIXfFL1HLWi5pfb/l7RuR402xu4QdXUn2Qq43hf5qSB34CtkaIRCe2c1gF35rLISjBWeGPdhmO87+mSiiYuuD4dBBpoa6xYOGE71+SvcRWGRUmycV62S5N7wLRpnuIG/s3y4r5jenqxve0KW60KMmMtYVd4QqsLNL2K9QKBgGtqTOgTyQRoANuXKJPkbRtMO3qybgCv8ecHu5M+uF91Y6D72jJnD6HBpDQ7pxa2cmIiF27tdK/ULeJshialTYYXeaEAo84xke+KUEWcJJbHoyXSbdgh3wzgSU2rA93CISyRLTs9/41f2wnmXxwNAYE3+tUDVxW7QFbem+RFlPD9AoGBAM3PvzZ8EBRt3bjOuWEWAWQJJiMUbSNKigcUdUt6z/wFwqtiKXSYaQMZ9kuf5aoUT5Dy9OjgZN16UmhURBKfacy+Ko4+6V5oLm4Plfw1jp/Aa7MrZmmGzMRLd1bTDeA3bTjh00g3wTl8b5qQKCdnI4lErWR4nCjky+XsZ/rLPh7u
-----END RSA PRIVATE KEY-----"""

        alipay_public_key_string = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwvl9I9ARkR4HDtlB7AI9NSTgzqsyRcdMQW5Em8SyvfjQ+dnEirizUVjc8oVNpiGa1wWRAoLgzik8ycJuWbWw+s1e2YIEskxMCQqRwUEftLmz2cUE/W69H+0V0MmvSgieZW+MXUiG3j48dBb0xgduPX0ThkcFZ6R+cj2o8yQDGZNhBClDcoYMoRtgeR/UMoGclg6rl1xevaAZPtvX8xEES5z8aXcK80phJQO0L8tliqUG3G7tsSr4UV4UFSQjYy59X//8MBOVqVVCHHY0C9PCuUafyl2hCVG0Pu9DkqYOhej/fpHZ/15zZP9XGDvVCBkLQuRLunPfvKiZBXlntfGp2QIDAQAB
-----END PUBLIC KEY-----"""

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016102200737971",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付宝的交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(out_trade_no = order_id)

            code = response.get('code')

            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4 # 待评价
                order.save()
                # 返回结果
                return JsonResponse({'res':3, 'message':'支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res':4, 'errmsg':'支付失败'})


class CommentView(LoginRequiredMixin, View):
    """订单评论"""
    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品的小计
            amount = order_sku.count*order_sku.price
            # 动态给order_sku增加属性amount,保存商品小计
            order_sku.amount = amount
        # 动态给order增加属性order_skus, 保存订单商品信息
        order.order_skus = order_skus

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        types = GoodsType.objects.all()

        return render(request, "order_comment.html", {"order": order, "cart_count": cart_count, "types": types})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        # 循环获取订单中商品的评论内容
        for i in range(1, total_count + 1):
            # 获取评论的商品的id
            sku_id = request.POST.get("sku_%d" % i)
            # 获取评论的商品的内容
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status = 5
        order.save()

        return redirect(reverse("user:order", kwargs={"page": 1}))


