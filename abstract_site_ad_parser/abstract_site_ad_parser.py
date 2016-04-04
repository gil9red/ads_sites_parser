#!/usr/bin/env python
# -*- coding: utf-8 -*-


# The MIT License (MIT)
#
# Copyright (c) 2015 Ilya Petrash (aka gil9red) <ilya.petrash@inbox.ru>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


__author__ = 'ipetrash'


from abc import ABCMeta, abstractmethod
import re
import yaml
import time
import logging
import sys


# Отправляется, когда нужное количество телефонов набрано
class NeedPhonesComplete(Exception):
    pass


# TODO: предусмотреть настройку логера для вывода в консоль и в файл
# TODO: сделать на примере dict из http://docs.python-guide.org/en/latest/writing/logging/


def get_logger(name, file='log.txt', encoding='utf8'):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')

    fh = logging.FileHandler(file, encoding=encoding)
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(stream=sys.stdout)
    # ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    log.addHandler(fh)
    log.addHandler(ch)

    return log


logger = get_logger('asaparser')


class AbstractSiteAdParser(metaclass=ABCMeta):
    """Абстрактный парсер сайтов-объявлений

    Пример использования:

    # Создание парсера FooBar_SiteAdParser на основе AbstractSiteAdParser
    # После:

    from foobar_site_ad_parser import FooBar_SiteAdParser

    # Создаем парсер и устанавливаем настройки
    parser = FooBar_SiteAdParser()
    parser.process_config('config.yaml')
    parser.run()
    parser.save()

    """

    def __init__(self):
        # Список найденных парсером телефонов
        self.list_phones = set()

        # Список посещенных страниц объявлений
        self.visited_ad_urls = []

        # Адреса отдельных объявлений
        self.ad_urls = []

        # Адреса категорий
        self.categories_urls = []

        # Настройка парсинга страниц категории объявления
        # start_page: указание с какой страницы начинать парсинг
        # end_page: указание до какой страниц (включительно) парсить. Если указано end, то max игнорируется.
        # max_page: количество страниц, которые будут распарсены
        self.start_page = None
        self.end_page = None
        self.max_page = None

        # Ссылка на конфиг yaml, инициализация в функции process_config
        self.config = None

        # Файл, в который будут добавлены найденные номера
        self.out = None

        # Режим открытия файла (w -- перезапись, a -- добавление в конец)
        self.out_mode = None

        # Количество телефонов, которые нужно набрать
        self.need_phones = None

    def process_config(self, file_name):
        """Функция обрабатывает конфиг, инициализирует поля парсера от параметров конфига"""

        stream = open(file_name, encoding='utf8')
        self.config = yaml.load(stream)

        # Из файла конфига добавляем в парсер список адресов объявлений
        ad_urls = self.config['ad_urls']
        if ad_urls:
            self.ad_urls += ad_urls

        # Настройка категорий объявлений
        categories = self.config['categories']

        page = categories['page']
        self.start_page = page['start']
        self.end_page = page['end']
        self.max_page = page['max']

        # Из файла конфига добавляем в парсер список адресов категорий объявлений
        cat_urls = categories['urls']
        if cat_urls:
            self.categories_urls += cat_urls

        self.need_phones = self.config['need_phones']

        # Настройка файла, в котором сохраняются результаты парсинга
        out = self.config['out']
        self.out = out['file_name']
        self.out_mode = out['mode']

        # # Настройка логирования
        # log = self.config['log']
        # # Файл, в котором логируются события скрипта
        # log['out']
        # # Формат логированных сообщений
        # log['format']
        #
        # logger.disable(logging.NOTSET if log['enabled'] else logging.CRITICAL)

    def run(self):
        """Функция запускает парсинг сайта"""

        t = time.clock()

        try:
            if self.ad_urls:
                logger.debug('Начинаю парсить, указанные в конфиге, адреса объявлений (%s).', len(self.ad_urls))
                self.parse_ad_urls(self.ad_urls, self.need_phones)
                logger.debug('Закончен парсинг, найдено %s телефонов.', len(self.list_phones))

            logger.debug('Начинаю парсить категории объявлений (%s).', len(self.categories_urls))

            for url in self.categories_urls:
                logger.info('Адрес категории: %s.', url)

                # Если последняя страница указана и она меньше или равна стартовой
                if self.end_page is not None and self.end_page >= self.start_page:
                    end_page = self.end_page

                # Если указано максимальное количество страниц и оно больше или равно 1
                elif self.max_page is not None and self.max_page >= 1:
                    end_page = self.start_page + self.max_page - 1
                else:
                    end_page = self.start_page

                # Номер последней страницы в категории объявлений
                last_page_category = self.get_last_page_category(url)
                logger.debug('Номер последней страницы в категории объявлений: {}.'.format(last_page_category))

                # Проходим по страницам данной категории
                for page in range(self.start_page, end_page + 1):
                    if page > last_page_category:
                        logger.debug('Превышение максимального количества страниц (текущая страница %s, максимальная '
                                     'страница %s).', page, last_page_category)
                        break

                    try:
                        url_page_cat = self.get_url_page_category(url, page)

                        logger.debug('Начинаю парсинг %s страницы категории: %s.', page, url_page_cat)

                        # Получаем список адресов объявлений данной страницы категории объявлений
                        # и парсим этот список
                        urls_ad = self.get_list_ad_from_category(url_page_cat)
                        logger.info('Найдено адресов объявлений: %s.', len(urls_ad))

                        self.parse_ad_urls(urls_ad, self.need_phones)

                        logger.debug('Закончен парсинг страницы категории.')

                    except NeedPhonesComplete:
                        # Пробрасываем выше -- там ожидается это исключение
                        raise

                    except Exception as e:
                        logger.error(e, exc_info=True)

            logger.debug('Закончен парсинг категорий объявлений. Найдено %s телефонов.', len(self.list_phones))

        except NeedPhonesComplete:
            pass

        # TODO: больше статистики: сколько была найдено объявлений
        logger.debug('Время выполнения парсера {0:.3f} секунд.'.format(time.clock() - t))
        logger.info('Найдено %s телефонов.', len(self.list_phones))
        logger.info('Телефоны: %s.', self.list_phones if len(self.list_phones) else 'нет')

    def parse_ad_urls(self, ad_urls, need_phones):
        """Функция принимает список адресов объявлений, парсит его и
        заполняет список номеров телефонов self.list_phones

        :param ad_urls: список адресов объявлений
        :param need_phones: количество нужных телефонов

        """

        for url in ad_urls:
            try:
                if url in self.visited_ad_urls:
                    logger.info('Объявление {} уже было распарсено.'.format(url))
                    continue

                logger.debug('Выполняю разбор объявления %s.', url)
                self.visited_ad_urls.append(url)

                ad_phones = self.get_phones_ad(url)
                logger.info('Найдено %s телефонов.', len(ad_phones))

                for phone in ad_phones:
                    try:
                        if phone in self.list_phones:
                            logger.info('Телефон "%s" уже есть в списке.', phone)
                        else:
                            phone = self.processing_phones(phone)
                            self.list_phones.add(phone)

                            logger.info('Номер телефона: %s.', phone)

                            # Если need_phones указано и набрано нужное количество телефонов
                            if isinstance(need_phones, int) and need_phones == len(self.list_phones):
                                logger.info('Найдено нужное количество телефонов.')
                                raise NeedPhonesComplete()

                    except NeedPhonesComplete:
                        # Пробрасываем выше -- там ожидается это исключение
                        raise

                    except Exception as e:
                        logger.error(str(e) + '\n', exc_info=True)

            except NeedPhonesComplete:
                # Пробрасываем выше -- там ожидается это исключение
                raise

            except Exception as e:
                logger.error(e, exc_info=True)

    def save(self, out=None, mode=None):
        """Функция сохранения найденных номеров в файл out.
        Если вызывать функцию без параметров, то файл будет браться из
        параметра конфига out

        :param out: путь к файлу конфига

        """

        file_name = self.out
        if out is not None:
            file_name = out

        if file_name:
            logger.debug('Сохраняю номера телефонов в файл: %s.', file_name)

            out_mode = self.out_mode
            if mode is not None:
                out_mode = mode

            # TODO: настройка сохранения файла: создать новый / переписать или добавлять в конец
            with open(file_name, mode=out_mode) as f:
                for phone in self.list_phones:
                    f.write(phone + '\n')

        else:
            raise Exception('Не указано имя файла (out и self.out).')

    @abstractmethod
    def get_url_page_category(self, url, page):
        """Функция возвращает адрес страницы категории объявления.

        :param url: корень категории (первая страница)
        :param page: номер страницы категории

        """

    @abstractmethod
    def get_list_ad_from_category(self, category_page_url):
        """Функция возвращает список адресов объявлений со страницы категории.

        :param category_page_url: адрес страницы категорий

        """

    @abstractmethod
    def get_last_page_category(self, url):
        """Функция возвращает последний номер страницы категории объявлений.

        :param url: Адрес страницы категорий

        """

    @abstractmethod
    def get_phones_ad(self, ad_url):
        """Функция возвращает список телефонов объявления."""

    def processing_phones(self, phone):
        """Функция для обработки номеров, которая вызывается перед
        добавлением их в список телефонов

        Функция по умолчанию удаляет из номера любые символы, кроме цифр от 0-9 и +

        """

        # Регулярка для удаления любых символов, кроме цифр от 0-9 и +
        new_phone = re.sub(r'[^\d+]', '', phone)
        logger.debug('Выполняю обработку номера телефона "%s" -> "%s".', phone, new_phone)
        return new_phone
