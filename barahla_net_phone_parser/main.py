#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


if __name__ == '__main__':
    from mgnbarnet_site_ad_parser import MgnBarNet_SiteAdParser

    # Создаем парсер и устанавливаем настройки
    parser = MgnBarNet_SiteAdParser()
    parser.process_config('config.yaml')
    parser.run()
    parser.save()
