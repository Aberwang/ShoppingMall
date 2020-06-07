$('.add_goods').click(function(){
			// 获取商品id和商品数量
            sku_id = $(this).attr('sku_id');
            count = 1;
            csrf = $('input[name="csrfmiddlewaretoken"]').val();
            // 组织参数
            params = {'sku_id':sku_id, 'count':count, 'csrfmiddlewaretoken':csrf};
            // 发起ajax post请求，访问/cart/add, 传递参数:sku_id count
            $.ajax({
                url:'/cart/add',
                type:"POST",
                data:params,
                success:function (data) {
                    if (data.res == 5){
                        // 添加成功
                        alert("加入购物车成功~");
                        oldval = $('.goods_count')
                        count_all = parseInt(oldval.text())+1;
                        $('.goods_count').text(count_all)
                    }else{
                        // 添加失败
                        alert(data.errmsg)
                    }
                }
            });
		});