#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


if __name__ == '__main__':
    from vsdelkaru_site_ad_parser import VSdelkaRu_SiteAdParser

    # Создаем парсер и устанавливаем настройки
    parser = VSdelkaRu_SiteAdParser()
    parser.process_config('config.yaml')
    parser.run()
    parser.save()
