#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


# TODO: увеличить время между запросами, чтобы бан по ip позже наступал
# TODO: использовать прокси
# TODO: отслеживать, когда наступает бан


if __name__ == '__main__':
    from avitoru_site_ad_parser import AvitoRu_SiteAdParser

    # Создаем парсер и устанавливаем настройки
    parser = AvitoRu_SiteAdParser()
    parser.process_config('config.yaml')
    parser.run()
    parser.save()
