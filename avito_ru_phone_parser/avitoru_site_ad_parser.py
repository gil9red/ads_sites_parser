#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from grab import Grab
from grab.error import GrabNetworkError
from abstract_site_ad_parser import AbstractSiteAdParser, get_logger
from urllib.parse import urljoin
from avito_ad_parser import AvitoAdParser
import os.path
import re


logger = get_logger('avitoru_site_parser')


# По-моему, костыль, нужно какой-то метод из коробки использовать
def grab_go(g, url, **kwargs):
    """Функция повторяет запросы, если во время выполнения случаются ошибки grab"""

    logger.info('Отправляю запрос к ' + url + ', kwargs=%s', kwargs)

    count = 5

    while count:
        try:
            g.go(url, **kwargs)
            break
        except GrabNetworkError as e:
            count -= 1
            logger.warn('Произошла ошибка "%s" (количество оставшихся попыток %s)', e, count)


class AvitoRu_SiteAdParser(AbstractSiteAdParser):
    """Парсер сайта avito.ru"""

    def __init__(self):
        super().__init__()

        self.proxy_url = None
        self.proxy_type = None
        self.proxy_enabled = None

        # Парсер объявлений
        self.ad_parser = AvitoAdParser()

        # Регулярка для получения номера последней страницы из url
        self.re_page = re.compile('.+\?p=(\d+)')

    def process_config(self, file_name):
        super().process_config(file_name)

        proxy = self.config['proxy']

        self.proxy_url = proxy['url']
        self.proxy_type = proxy['type']
        self.proxy_enabled = proxy['enabled']

        self.ad_parser.proxy_url = self.proxy_url
        self.ad_parser.proxy_type = self.proxy_type
        self.ad_parser.proxy_enabled = self.proxy_enabled

    def get_url_page_category(self, url, page):
        # Примеры страниц категорий сайта avito.ru:
        # Первая страница (корень) может быть так представлена:
        #   https://www.avito.ru/magnitogorsk/vakansii
        # или: https://www.avito.ru/magnitogorsk/vakansii?p=1
        # Последующие:
        #   https://www.avito.ru/magnitogorsk/vakansii?p=2
        #   https://www.avito.ru/magnitogorsk/vakansii?p=3
        # И так до конца...

        if page <= 0:
            raise Exception('Неправильный номер страницы {} -- может быть только положительные.'.format(page))

        return url if page == 1 else url + '?p={}'.format(page)

    def get_list_ad_from_category(self, category_page_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, category_page_url)

        # Список адресов объявлений
        ad_urls = []

        xpath = '//div[contains(@class, "catalog")]//div[contains(@class, "item_table")]'
        select = g.doc.select(xpath)
        if select.count() == 0:
            raise Exception('Не нашлось объявлений! (xpath="{}")'.format(xpath))

        for sel in select:
            a = sel.select('div[@class="description"]/h3/a')
            ad_url = urljoin(g.response.url, a.attr('href'))
            ad_urls.append(ad_url)

        return ad_urls

    def get_last_page_category(self, url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, url)

        # Запрос для получения последней страницы данной категории
        xpath = '(//div[@class="pagination js-pages"]//a[@class="pagination__page"])[last()]'
        a = g.doc.select(xpath)
        if a.count() == 0:
            raise Exception('Не удалось получить url последней страницы данной категории! (xpath="{}")'.format(xpath))

        last_page_url = urljoin(g.response.url, a.attr('href'))

        page = os.path.split(last_page_url)[-1]
        match = self.re_page.search(page)
        if match is None:
            raise Exception('Не получилось получить номер последней страницы категории. Регулярка: '
                            '{}.'.format(self.re_page.pattern))

        page = match.group(1)
        return int(page)

    def get_phones_ad(self, ad_url):
        logger.debug('Выполняю разбор объявления ' + ad_url)
        self.ad_parser.run(ad_url)

        phone = self.ad_parser.phone

        if phone is None:
            logger.warn('Телефон не найден')
            return []

        return [phone]

    def processing_phones(self, phone):
        # Не вызываю родительскую функцию и без изменений передаю номер, т.к. обработка
        # для телефонов авито не нужна -- все-равно она вытаскиваются путем парсинга их
        # изображения и вытаскиваются только цифры
        return phone
