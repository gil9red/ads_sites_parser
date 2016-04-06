#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from grab import Grab
from grab.error import GrabNetworkError
from urllib.parse import unquote, urljoin
import re
from abstract_site_ad_parser import AbstractSiteAdParser, get_logger
import os.path


logger = get_logger('vsdelkaruparser')


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


class VSdelkaRu_SiteAdParser(AbstractSiteAdParser):
    """Парсер сайта v-sdelka.ru"""

    def __init__(self):
        super().__init__()

        self.proxy_url = None
        self.proxy_type = None
        self.proxy_enabled = None

        # Регулярка для получения номера последней страницы из url
        self.re_page = re.compile('num(\d+?).html')

    def process_config(self, file_name):
        super().process_config(file_name)

        proxy = self.config['proxy']
        self.proxy_url = proxy['url']
        self.proxy_type = proxy['type']
        self.proxy_enabled = proxy['enabled']

    def get_url_page_category(self, url, page):
        # Примеры страниц категорий сайта v-sdelka.ru:
        # Первая страница (корень) может быть так представлена:
        #   http://v-sdelka.ru/alladv/nedv/
        # или: http://v-sdelka.ru/alladv/nedv/num1.html
        # Последующие:
        #   http://v-sdelka.ru/alladv/nedv/num2.html
        #   http://v-sdelka.ru/alladv/nedv/num3.html
        # И так до конца...

        if page <= 0:
            raise Exception('Неправильный номер страницы {} -- может быть только положительные.'.format(page))

        return url if page == 1 else url + 'num{}.html'.format(page)

    def get_list_ad_from_category(self, category_page_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, category_page_url)

        # Запрос для получения адресов объявлений
        xpath = '//div[@class="synopsis_advert"]//a[@class="title_synopsis_adv"]'

        select = g.doc.select(xpath)
        if select.count() == 0:
            raise Exception('Не нашлось объявлений! (xpath="{}")'.format(xpath))

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
        xpath = '//div[@class="navigator_page_podcategory"]//a[last()]'
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
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, ad_url)

        pattern_text = r'view_mask_phone_advert.action_view\((.+?)\)'
        pattern = re.compile(pattern_text)

        match = pattern.search(g.response.body)
        if match is None:
            logger.warn('Телефон не указан, адрес объявления: ' + ad_url)
            return []

        # id объявления
        id_ad = match.group(1)

        post_phone_url = 'http://v-sdelka.ru/moduls/doska/include/get_type_data_elm_doska.php'
        post = {'id_advert': id_ad, 'type_data': 'phone'}
        logger.info('POST запрос для получения телефона: %s, %s', post_phone_url, post)

        # Отправляем post-запрос с данными объявления
        grab_go(g, post_phone_url, post=post)

        # Варианты возврата:
        # { error:{code:1,text:'ошибка с параметрами!'}  }
        # { error:{code:0,text:'no'}  ,  on_data : 1, data : {'phone':'%2B89049425772%20'} }
        body = g.response.body

        logger.info('Ответ на запрос: %s', body)
        logger.debug('Попытка найти в ответе ошибку, и если ее нет, получить телефон')

        match = re.search("text:'(.+?)'", body)
        if match is not None:
            error = match.group(1)
            if error != 'no':
                raise Exception('Ошибка "{}", тело ответа: {}'.format(error, body))

        match = re.search("{'phone':'(.+?)'}", body)
        if match is None:
            raise Exception('Не найден в ответе на post-запрос телефон')

        # Вытаскиваем телефон
        phone = match.group(1)

        logger.info('Телефон: "%s"', phone)

        # Декодируем в номере телефона ascii %xx последовательности и убираем лишние пробелы
        phone = unquote(phone).strip()

        logger.info('Телефон после обработки: "%s"', phone)

        return [phone]
