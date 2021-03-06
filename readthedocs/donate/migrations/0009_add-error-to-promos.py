# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-03-24 16:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('donate', '0008_add-programming-language-filter'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='supporterpromo',
            options={'ordering': ('analytics_id', '-live')},
        ),
        migrations.AlterField(
            model_name='geofilter',
            name='countries',
            field=models.ManyToManyField(related_name='filters', to='donate.Country'),
        ),
        migrations.AlterField(
            model_name='supporterpromo',
            name='display_type',
            field=models.CharField(choices=[(b'doc', b'Documentation Pages'), (b'site-footer', b'Site Footer'), (b'search', b'Search Pages'), (b'error', b'Error Pages')], default=b'doc', max_length=200, verbose_name='Display Type'),
        ),
        migrations.AlterField(
            model_name='supporterpromo',
            name='programming_language',
            field=models.CharField(blank=True, choices=[(b'words', b'Only Words'), (b'py', b'Python'), (b'js', b'JavaScript'), (b'php', b'PHP'), (b'ruby', b'Ruby'), (b'perl', b'Perl'), (b'java', b'Java'), (b'go', b'Go'), (b'julia', b'Julia'), (b'c', b'C'), (b'csharp', b'C#'), (b'cpp', b'C++'), (b'objc', b'Objective-C'), (b'other', b'Other')], default=None, max_length=20, null=True, verbose_name='Programming Language'),
        ),
    ]
