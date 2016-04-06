#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from grab import Grab
from grab.error import GrabNetworkError
import re
from abstract_site_ad_parser import AbstractSiteAdParser, get_logger
from urllib.parse import urljoin
from random import random
import time
import os.path


logger = get_logger('mgnbarnet_parser')


# По-моему, костыль, нужно какой-то метод из коробки использовать
def grab_go(g, url, **kwargs):
    """Функция повторяет запросы, если во время выполнения случаются ошибки grab"""

    logger.info('Отправляю запрос к %s, kwargs=%s', url, kwargs)

    count = 5

    while count:
        try:
            g.go(url, **kwargs)
            break
        except GrabNetworkError as e:
            count -= 1
            logger.warn('Произошла ошибка "%s" (количество оставшихся попыток %s).', e, count)


class MgnBarNet_SiteAdParser(AbstractSiteAdParser):
    """Парсер сайта magnitogorsk.barahla.net"""

    def __init__(self):
        super().__init__()

        self.proxy_url = None
        self.proxy_type = None
        self.proxy_enabled = None
        self.attempts = None

        # Регулярка для получения номера последней страницы из url
        self.re_page = re.compile('\?page=(\d+)')

        # Регулярка для получения данных для post-запрос
        self.re_post_phone = re.compile("post\(.+({key: '.+?', br: '.+?'}),")

        # Регулярка для получения телефона из тега nobr
        self.re_response_phone = re.compile('<nobr>(.+)</nobr>')

        # Регулярка для получения телефона из тега error
        self.re_response_error = re.compile('<error>(.+)</error>')

    def process_config(self, file_name):
        super().process_config(file_name)

        proxy = self.config['proxy']
        self.proxy_url = proxy['url']
        self.proxy_type = proxy['type']
        self.proxy_enabled = proxy['enabled']

        self.attempts = self.config['attempts']

    def get_url_page_category(self, url, page):
        # Примеры страниц категорий сайта magnitogorsk.barahla.net:
        # Первая страница (корень) может быть так представлена:
        #   http://magnitogorsk.barahla.net/services/220/
        # или: http://magnitogorsk.barahla.net/services/220/?page=1
        # Последующие:
        #   http://magnitogorsk.barahla.net/services/220/?page=2
        #   http://magnitogorsk.barahla.net/services/220/?page=3
        # И так до конца...

        if page <= 0:
            raise Exception('Неправильный номер страницы {} -- может быть только положительные.'.format(page))

        return url if page == 1 else url + '?page={}'.format(page)

    def get_list_ad_from_category(self, category_page_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, category_page_url)

        # Запрос для получения адресов объявлений
        xpath = '//table[@class="ob"]//a[@class=" ads-title-link"]'

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
        xpath = '//div[@class="page_nav"]//a[last()]'
        a = g.doc.select(xpath)
        if a.count() == 0:
            raise Exception('Не удалось получить url последней страницы данной категории! (xpath="{}").'.format(xpath))

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

        xpath = '//table[@class="author_ob"]//a[contains(@onclick, "viewphone")]'
        select = g.doc.select(xpath)
        if select.count() == 0:
            logger.warn('Телефон не указан, адрес объявления: %s, xpath="%s".', ad_url, xpath)
            return []

        # В атрибуте описан js-скрипт, в котором есть 2 значения, нужных нам: key и br
        onclick = select.attr('onclick').strip()

        logger.info('onclick js-код: "%s".', onclick)

        # Сгенерируем url для получения номера телефона, значение rand не важно, можно любое число
        # но для правдоподобности url все-таки сгенерируем
        post_phone_url = urljoin(g.response.url, '/ajax/getPhones.php?rand=' + str(random()))
        logger.info('Сгенерированный POST адрес для получения телефона: ' + post_phone_url)

        match = self.re_post_phone.search(onclick)
        if match is None:
            raise Exception('Не получилось вытащить данные для POST запроса получения '
                            'телефона. Регулярка: "%s"', self.re_post_phone.pattern)

        data_json = match.group(1)
        logger.info('Регулярка вытащила строку: "%s".', data_json)

        # TODO: использовать yaml для подобного как пушкой по воробьям стрелять
        # TODO: вытащить текст из скобок, и вручную распарсить
        import yaml
        post = yaml.load(data_json)

        # Количество попыток получения номера телефона
        count = self.attempts

        logger.debug('Попытаемся получить телефон, количество попыток: %s', count)

        # Не всегда приходит телефон от сервера, в целом, в половину случаев
        while True:
            logger.info('POST запрос для получения телефона: %s, %s.', post_phone_url, post)
            g.go(post_phone_url, post=post)

            # Варианты ответа:
            # <error>oh, shit</error>
            # <nobr>+7 921 956-23-24</nobr>
            # 84951111111
            response = g.response.body
            logger.info('Ответ на запрос: "%s".', response)

            if '<error>' in response:
                match = self.re_response_error.search(response)
                if match is None:
                    logger.info('Не получилось вытащить текст ошибки регуляркой: "%s".', self.re_response_error.pattern)
                else:
                    text_err = match.group(1)
                    logger.info('Получена ошибка: "%s".', text_err)
            else:
                phone = None

                # Если телефон пришел в теге nobr, вытаскиваем его регуляркой
                if '<nobr>' in response:
                    logger.debug('Вытаскиваю телефон из тега nobr.')
                    match = self.re_response_phone.search(response)

                    if match:
                        phone = match.group(1)
                    else:
                        logger.info('Не получилось вытащить телефон регуляркой: "%s".',
                                    self.re_response_phone.pattern)
                else:
                    phone = response

                if phone is None:
                    logger.warn('Телефон не найден.')
                    return []

                logger.info('Телефон: "%s".', phone)
                return [phone]

            count -= 1
            logger.info('Телефон не получен, осталось попыток: %s.', count)

            # Перед отправкой следующего запроса подождем секунду
            time.sleep(1)

            # Если закончилось количество попыток
            if count == 0:
                logger.warn('Закончилось количество попыток, заканчиваю попытки получить телефон.')
                break

        return []
