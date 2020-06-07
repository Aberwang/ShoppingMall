from django.shortcuts import render, redirect, HttpResponse
from django.views.generic import View   # 使用类视图导入View，让类视图继承
from django.urls import reverse
import re
from apps.user import models
from apps.goods import models as goods_models
from apps.order import models as order_models
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer  # 对信息加密的一个模块
from itsdangerous import SignatureExpired   # 信息过期后报错类型
from ShoppingMall import settings
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
from django.core.paginator import Paginator


# 生成图片验证码
def get_valid_img(request):
    # 生成一个随机颜色背景的图片
    # 安装的pillow库，PIL为其中生成图片的类
    import PIL
    from PIL import Image
    from PIL import ImageDraw, ImageFont
    import random
    def get_random_color():
        color_num = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        return color_num
    image = PIL.Image.new("RGB", size=(170, 40), color=get_random_color())

    # 生成5个随机字符并写在随机图片上
    draw = ImageDraw.Draw(image)    # 使用ImageDraw.Draw生成一个画笔对象
    font = ImageFont.truetype("static/font/kumo.ttf", size=33)  # 设置字体
    temp = []
    for i in range(4):
        random_num = str(random.randint(0, 9))        # 随机生成一个0-9的数字
        random_low_alpha = chr(random.randint(97, 122))  # 随机生成一个小写字母
        random_upper_alpha = chr(random.randint(65, 90)) # 随机生成一个大写字母
        random_char = random.choice([random_num, random_low_alpha, random_upper_alpha]) # 从随机的数字和字母中随机选择一个
        draw.text((30 + i * 30, 0), random_char, get_random_color(), font=font) # 将生成的字符写在图片上
        temp.append(random_char)    # 将生成的随机字符保存下来，校验使用

    # 将随机验证码保存为一个字符串，将该验证码注册到session中用于每个用户各自的验证码校验
    valid_str = "".join(temp)
    request.session["valid_str"] = valid_str    # 设置一个session的值，验证码校验时使用

    # 噪点噪线
    width=170
    height=35
    for i in range(3):
        x1=random.randint(0,width)
        x2=random.randint(0,width)
        y1=random.randint(0,height)
        y2=random.randint(0,height)
        draw.line((x1,y1,x2,y2),fill=get_random_color())

    for i in range(7):
        draw.point([random.randint(0, width), random.randint(0, height)], fill=get_random_color())
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.arc((x, y, x + 4, y + 4), 0, 90, fill=get_random_color())

    # 将生成的图片保存在项目下
    f = open("valid_img.png", "wb")
    image.save(f, "png")
    with open("valid_img.png", "rb")as f:
        data = f.read()
    return HttpResponse(data)


class RegisterView(View):
    """用户注册视图"""
    def get(self, request):
        # 显示注册页面
        return render(request, 'register.html')

    def post(self, request):
        # 注册逻辑处理
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpwd = request.POST.get('cpwd')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        content_dict = {
            'username':username, 'password':password, 'cpwd':cpwd, 'phone':phone, 'email':email
        }

        # 进行数据校验
        # 1、校验数据是否为空，all()函数，当里面的所有值都为真时返回True，否者返回False
        if not all([username, password, cpwd, phone, email, allow]):
            # 数据不完整
            content_dict['error_message'] = '数据不完整'
            return render(request, 'register.html', content_dict)

        # 2、校验数据是否合法
        if len(password)<8:
            content_dict['error_message2'] = '密码长度最低8位'
            return render(request, 'register.html', content_dict)
        if password != cpwd:
            content_dict['error_message2'] = '密码和确认密码不一致'
            return render(request, 'register.html', content_dict)

        if not re.match(r'^0?(13|14|15|17|18|19)[0-9]{9}$', phone):
            content_dict['error_message3'] = '手机号码格式不正确'
            return render(request, 'register.html', content_dict)

        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            content_dict['error_message4'] = '邮箱格式不正确'
            return render(request, 'register.html', content_dict)

        if allow != 'on':
            content_dict['error_message5'] = '请同意协议'
            return render(request, 'register.html', content_dict)

        # 校验用户名是否重复
        try:
            models.User.objects.get(username=username)
        except:
            user = models.User.objects.create_user(username=username, password=password, phone=phone, email=email)
            user.is_active = 0
            user.save()
        else:
            # 用户名已存在（不可用）
            content_dict['error_message1'] = '用户名已存在'
            return render(request, 'register.html', content_dict)

        serialzer = Serializer(settings.SECRET_KEY, 3600)
        info = {'user_id': user.id}  # 加密信息（加密的信息可以是其他的格式，一般使用字典）
        token = serialzer.dumps(info)  # 生成的为bytes类型的密文，得到的即token=b'……'
        token = token.decode('utf-8')  # 解码（为了去掉token的b''）

        from celery_tasks.tasks import send_register_active_email
        send_register_active_email.delay(email, username, token)

        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        # 进行解密，获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)

        # 过期时间过期时，在进行解密时会报错，因此需要捕获错误信息，进行处理
        try:
            # 解密，获得之前加密的用户信息字典info
            info = serializer.loads(token)
            user_id = info['user_id']
            user = models.User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return render(request, 'index.html')
        except SignatureExpired:
            return HttpResponse('该激活链接已过期')


class LoginView(View):
    """用户登录视图"""
    def get(self, request):
        # 显示登录页面
        # 判断是否记住了用户名
        if 'username' and 'password' in request.COOKIES:
            username = request.COOKIES.get('username')
            pwd = request.COOKIES.get('password')
            checked = 'checked'
        else:
            username = ''
            pwd = ''
            checked = ''
        return render(request, "login.html", {'username': username, 'pwd': pwd, 'checked': checked})

    def post(self, request):
        # 登录逻辑处理
        # 接收数据
        username = request.POST.get('username')
        pwd = request.POST.get('pwd')
        code = request.POST.get("code", None)
        if not code:
            return render(request, 'login.html', {'error_message1': '请输入验证码！', 'username': username, 'pwd': pwd})

        valid_str = request.session.get("valid_str")  # 获取session所存入的valid_str的值
        if code.upper() != valid_str.upper():  # 全变成大写后比较
            return render(request, 'login.html', {'error_message1': '验证码错误！', 'username': username, 'pwd': pwd})

        # 校验数据
        if not all([username, pwd]):
            return render(request, 'login.html', {'error_message': '登陆数据不完整'})

        # 业务处理：登陆校验
        user = authenticate(username=username, password=pwd)

        if user is not None:
            # 用户名密码正确
            if user.is_active:
                login(request, user)

                # 获取登录后所要跳转到的地址,默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))
                # 当没有获取到next的值的时候，返回的为反向解析得到的index页面的地址

                # 跳转到next_url
                response = redirect(next_url)  # HttpResponseRedirect

                # 判断是否需要记住用户名
                remember = request.POST.get('remember')

                if remember:
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                    response.set_cookie('password', pwd, max_age=7 * 24 * 3600)
                else:
                    # 登录时没有点击记住用户名，就删除之前保存的cookie
                    response.delete_cookie('username')
                    response.delete_cookie('password')

                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'error_message': '账户未激活', 'username': username, 'pwd': pwd})
        else:
            return render(request, 'login.html', {'error_message': '用户名或密码不正确', 'username': username, 'pwd': pwd})


class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        # 清除用户的session信息（使用auth模块的logout函数）
        logout(request)
        return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-用户信息页面'''
    def get(self, request):
        # 获取用户收货地址信息
        address = models.Address.objects.get_default_address(user=request.user)

        from django_redis import get_redis_connection
        con = get_redis_connection("default")

        history_key = 'history_%s'%request.user.id
        # 获取用户最新浏览的5个商品的id
        ids = con.lrange(history_key, 0, 7)

        if ids:
            # 从数据库中查询用户浏览的商品的具体信息
            # 根据浏览的先后顺序获取5条浏览记录（使用了一层遍历）
            goods_li = []
            for id in ids:
                goods = goods_models.GoodsSKU.objects.get(id=id)
                goods_li.append(goods)

            context = {'page': 'user',
                       'address': address,
                       'goods_li': goods_li,
                       }
        else:
            context = {'page': 'user',
                       'address': address,}

        # 除了你给模板文件传递的模板变量之外，django框架会把request.user也传给模板文件
        return render(request, 'user_center_info.html', context)


class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页面'''
    def get(self, request):
        # 获取当前登录用户对应的user对象
        user = request.user
        # 获取用户的默认收货地址
        try:
            address = models.Address.objects.get(user=user, is_default=True)
        except:
            address = None

        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        '''添加收货地址'''
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        user = request.user
        try:
            address = models.Address.objects.get(user=user, is_default=True)
        except:
            address = None

        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'address': address, 'error_messag': '数据不完整'})
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'address': address, 'errmsg': '手机格式不正确'})

        if address:
            models.Address.objects.create(user=user, receiver=receiver, addr=addr, zip_code=zip_code, phone=phone, is_default=False)
        else:
            models.Address.objects.create(user=user, receiver=receiver, addr=addr, zip_code=zip_code, phone=phone, is_default=True)

        return redirect(reverse('user:address'))


class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页面'''
    def get(self, request, page):
        '''显示'''
        # 获取用户的订单信息
        user = request.user
        orders = order_models.OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = order_models.OrderGoods.objects.filter(order_id=order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.price*order_sku.count
                # 动态给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount = amount

            # 动态给order增加属性，保存订单商品的信息
            order.order_sku = order_skus

        # 使用Django自带分页的后台视图
        paginator = Paginator(orders, 3)

        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page<=0:
            page = 1
        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
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

        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'}

        return render(request, 'user_center_order.html', context)



