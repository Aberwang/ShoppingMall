# Generated by Django 2.2.12 on 2020-04-10 12:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(default=None, max_length=11, verbose_name='手机号码'),
            preserve_default=False,
        ),
    ]
