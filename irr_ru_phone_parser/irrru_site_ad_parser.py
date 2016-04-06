#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from grab import Grab
from grab.error import GrabNetworkError
import re
from abstract_site_ad_parser import AbstractSiteAdParser, get_logger
from urllib.parse import urljoin
import base64


logger = get_logger('mgnbarnet_parser')


# По-моему, костыль, нужно какой-то метод из коробки использовать
def grab_go(g, url, **kwargs):
    """Функция повторяет запросы, если во время выполнения случаются ошибки grab"""

    logger.info('Отправляю запрос к %s, kwargs=%s.', url, kwargs)

    count = 5

    while count:
        try:
            g.go(url, **kwargs)
            break
        except GrabNetworkError as e:
            count -= 1
            logger.warn('Произошла ошибка "%s" (количество оставшихся попыток %s).', e, count)


class IrrRu_SiteAdParser(AbstractSiteAdParser):
    """Парсер сайта "Из рук в руки" irr.ru"""

    def __init__(self):
        super().__init__()

        self.proxy_url = None
        self.proxy_type = None
        self.proxy_enabled = None

        # Регулярка для получения номера последней страницы из url
        self.re_page = re.compile('/page(\d+)/?')

    def process_config(self, file_name):
        super().process_config(file_name)

        proxy = self.config['proxy']
        self.proxy_url = proxy['url']
        self.proxy_type = proxy['type']
        self.proxy_enabled = proxy['enabled']

    def get_url_page_category(self, url, page):
        # Примеры страниц категорий сайта irr.ru:
        # Первая страница (корень) может быть так представлена:
        #   http://saint-petersburg.irr.ru/computers-devices/notebooks/notebooks/
        # или: http://saint-petersburg.irr.ru/computers-devices/notebooks/notebooks/page1/
        # Последующие:
        #   http://saint-petersburg.irr.ru/computers-devices/notebooks/notebooks/page2/
        #   http://saint-petersburg.irr.ru/computers-devices/notebooks/notebooks/page3/
        # И так до конца...

        if page <= 0:
            raise Exception('Неправильный номер страницы {} -- может быть только положительные.'.format(page))

        return url if page == 1 else url + 'page{}/'.format(page)

    def get_list_ad_from_category(self, category_page_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, category_page_url)

        # Запрос для получения адресов объявлений
        xpath = '//a[@class="add_title"]'
        xpath = '//div[contains(@class, "adds_cont")]/a'

        select = g.doc.select(xpath)
        if select.count() == 0:
            raise Exception('Не нашлось объявлений! (xpath="{}").'.format(xpath))

        ad_urls = []

        for a in select:
            ad_url = urljoin(category_page_url, a.attr('href'))
            ad_urls.append(ad_url)

        return ad_urls

    def get_last_page_category(self, url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, url)

        # Запрос для получения последней страницы данной категории
        xpath = '(//li[starts-with(@id, "page")]/a)[last()]'
        a = g.doc.select(xpath)
        if a.count() == 0:
            raise Exception('Не удалось получить url последней страницы данной категории! (xpath="{}").'.format(xpath))

        last_page_url = urljoin(g.response.url, a.attr('href'))
        logger.debug('Href последней страницы: %s', a.attr('href'))
        logger.debug('Url последней страницы: %s', last_page_url)

        match = self.re_page.search(last_page_url)
        if match is None:
            raise Exception('Не получилось получить номер последней страницы категории. Регулярка: '
                            '{}.'.format(self.re_page.pattern))

        page = match.group(1)
        return int(page)

    def get_phones_ad(self, ad_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, ad_url)

        xpath = '//div[@class="noactual_adv"]'
        select = g.doc.select(xpath)
        if select.count() == 1:
            logger.info('Объявление удалено.')
            return []

        xpath = '//div[@class="productPage__phoneText js-productPagePhoneLabel"]'
        select = g.doc.select(xpath)
        if select.count() == 0:
            logger.warn('Не нашел кнопки "Показать". xpath="%s".', xpath)
            return []

        data_phone = select.attr('data-phone', None)
        if data_phone is None:
            logger.warn('Телефон не указан.')
            return []

        logger.info('Закодированный в base64 телефон получен: "%s".', data_phone)

        # Декодирование из base64, а после приведение к типу str
        phone = base64.b64decode(data_phone)
        phone = phone.decode()

        logger.info('Декодированный телефон: "%s".', phone)
        return [phone]
