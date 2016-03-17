#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


if __name__ == '__main__':
    from olxua_site_ad_parser import OlxUa_SiteAdParser

    # Создаем парсер и устанавливаем настройки
    parser = OlxUa_SiteAdParser()
    parser.process_config('config.yaml')
    parser.run()
    parser.save()
