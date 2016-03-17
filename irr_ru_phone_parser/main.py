#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


if __name__ == '__main__':
    from irrru_site_ad_parser import IrrRu_SiteAdParser

    # Создаем парсер и устанавливаем настройки
    parser = IrrRu_SiteAdParser()
    parser.process_config('config.yaml')
    parser.run()
    parser.save()
