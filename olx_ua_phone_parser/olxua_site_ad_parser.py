#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from grab import Grab
from grab.error import GrabNetworkError
from urllib.parse import urljoin
import re
from abstract_site_ad_parser import AbstractSiteAdParser, get_logger
import json
import os.path


logger = get_logger('olxua_parser')


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


class OlxUa_SiteAdParser(AbstractSiteAdParser):
    """Парсер сайта olx.ua"""

    def __init__(self):
        super().__init__()

        self.proxy_url = None
        self.proxy_type = None
        self.proxy_enabled = None

    def process_config(self, file_name):
        super().process_config(file_name)

        proxy = self.config['proxy']
        self.proxy_url = proxy['url']
        self.proxy_type = proxy['type']
        self.proxy_enabled = proxy['enabled']

    def get_url_page_category(self, url, page):
        # Примеры страниц категорий сайта olx.ua:
        # Первая страница (корень) может быть так представлена:
        #   http://olx.ua/rabota/ohrana-bezopasnost/
        # или: http://olx.ua/rabota/ohrana-bezopasnost/?page=1
        # Последующие:
        #   http://olx.ua/rabota/ohrana-bezopasnost/?page=2
        #   http://olx.ua/rabota/ohrana-bezopasnost/?page=3
        # И так до конца...

        if page <= 0:
            raise Exception('Неправильный номер страницы {} -- может быть только положительные.'.format(page))

        return url if page == 1 else url + '?page{}'.format(page)

    def get_list_ad_from_category(self, category_page_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, category_page_url)

        # На странице тематики, среди обычных объявлений ищем ссылки из картинок объявлений
        xpath = '//table[@id="offers_table"]//td[contains(@class, "offer")]//a[contains(@class, "thumb")]'
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
        # Запрос, который получает список ссылок с вариантами перехода на страницы
        # и возвращает последную -- она и будет адресом последней страницы
        xpath = '(//div[@class="pager rel clr"]/span[contains(@class, "item")]/a)[last()]'
        a = g.doc.select(xpath)
        if a.count() == 0:
            raise Exception('Не удается получить адрес последней страницы в данной категории ({})'.format(xpath))

        # Адрес последней страницы категории объявлений
        last_page_url = urljoin(g.response.url, a.attr('href'))

        page = os.path.split(last_page_url)[-1]
        page = page.replace('?page=', '')
        return int(page)


    def get_phones_ad(self, ad_url):
        g = Grab()
        if self.proxy_enabled:
            g.setup(proxy=self.proxy_url, proxy_type=self.proxy_type)

        grab_go(g, ad_url)

        # Проверим наличие тега, сообщающего о том, что объявление не активно
        select = g.doc.select('//div[@id="offer_removed_by_user"]')
        if select.count():
            logger.warn('Объявление не активно\n')
            return []

        # В классе хранится информация, нужная для ajax запроса
        # И нас интересует кусок json-текста из класса link-phone
        # Пример: "{'path':'phone', 'id':'b6q05', 'id_raw': '164069613'}
        xpath = '//ul[@id="contact_methods"]/li[contains(@class, "link-phone")]'
        select = g.doc.select(xpath)
        if select.count():
            # Вытаскиваем json текст из атрибута тега
            m = re.search(r'(\{.+\})', select.attr('class'))
            if m is None:
                logger.warn('Не найденные данные о объявлении в ' + xpath)
                return []

            # json не хочет парсить строки с одинарными кавычками
            ad_data = m.group(1).replace("'", '"')
            ad_data = json.loads(ad_data)

            # Создаем url GET запроса, возвращающего json с настоящим номером телефона
            # Пример: http://krivoyrog.dnp.olx.ua/ajax/misc/contact/phone/eWGfv/white
            split_url = g.response.url_details()
            host = '{}://{}'.format(split_url.scheme, split_url.netloc)
            url_phone = host + '/ajax/misc/contact/{path}/{id}/white'.format(**ad_data)

            grab_go(g, url_phone)
            phones_value = json.loads(g.response.body)['value']

            # Если пришел html тег, телефонов несколько
            if '<span' in phones_value:
                from io import StringIO
                from lxml import etree

                # TODO: можно попробовать ругуляркой выковыривать телефоны
                # Чтобы распарсилось нормально:
                phones_xml = '<phones>' + phones_value + '</phones>'

                f = StringIO(phones_xml)
                tree = etree.parse(f)
                xpath = '//span[@class="block"]/text()'

                return [phone.strip() for phone in tree.xpath(xpath)]

            return [phones_value.strip()]

        else:
            logger.warn('Не найден телефон ({})\n'.format(xpath))
            return []

    def processing_phones(self, phone):
        # Не будем вызывать processing_phones предка -- наша функция лучше

        # Приводим номера телефонов к международному формату.
        # Примеры:
        #   050 352 3204 -> +380503523204
        #   (0612)246448 -> +380612246448
        #   066-55-4-000-4 -> +380665540004
        #   097-171-80-66 -> +380971718066
        #   (0612)246448 -> +380612246448

        # Регулярка для удаления любых символов, кроме цифр от 0-9 и +
        new_phone = re.sub(r'[^\d+]', '', phone)

        # Если первым символом номера является 0,
        # удаляем его и добавляем +380
        if new_phone[0] == '0':
            new_phone = '+380' + new_phone[1:]

        # Если телефон уже с телефонным кодом Украины (380), но без + в начале
        elif len(new_phone) == 12 and new_phone[:3] == '380':
            new_phone = '+' + new_phone

        if len(new_phone) != 13:
            # raise Exception('Номер "{}" -> "{}" невалидный: длина должна быть 13 символов.'.format(phone, new_phone))
            logger.warn('Номер "{}" -> "{}" невалидный: длина должна быть 13 символов.'.format(phone, new_phone))
            logger.warn('Возвращаю оригинальный номер телефона: ' + phone)
            return phone

        logger.debug('Выполняю обработку номера телефона "%s" -> "%s".', phone, new_phone)
        return new_phone
