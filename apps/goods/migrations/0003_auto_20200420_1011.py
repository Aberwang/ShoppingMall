# Generated by Django 2.2.12 on 2020-04-20 02:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goods', '0002_auto_20200420_1005'),
    ]

    operations = [
        migrations.AlterField(
            model_name='indexpromotionbanner',
            name='image',
            field=models.ImageField(upload_to='banner', verbose_name='活动图片'),
        ),
    ]
