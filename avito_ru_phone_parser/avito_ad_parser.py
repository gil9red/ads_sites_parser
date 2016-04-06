#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from PySide.QtCore import QObject, Signal, QEventLoop
from PySide.QtWebKit import QWebPage, QWebSettings
from PySide.QtNetwork import QNetworkProxyFactory
from PySide.QtGui import QApplication

from avito_im_phone_parser import AvitoPhoneImgParser
import time
import base64

import sys


from abstract_site_ad_parser import get_logger
logger = get_logger('avitoru_ad_parser')


class AvitoAdParser(QObject):
    """Парсер страницы объявления сайта avito.ru"""

    def __init__(self):
        super().__init__()

        self.app = QApplication(sys.argv)

        QNetworkProxyFactory.setUseSystemConfiguration(True)

        self.web_page = QWebPage(self)
        self.web_page.settings().setAttribute(QWebSettings.AutoLoadImages, False)
        self.web_page.loadFinished.connect(self.load_finished)

        # Адрес страницы объявления
        self.url = None

        # Переменная нужна для замера времени выполнения
        self.t = None

        self.phone_img_parser = AvitoPhoneImgParser()

        # Строка с номером телефона
        self.phone = None

        self.proxy_url = None
        self.proxy_type = None
        self.proxy_enabled = None

    # Сигнал вызывается, когда закончен парсинг сотового из объявления
    parse_phone_finished = Signal(str)

    def run(self, url):
        """Функция выполняет парсинг страницы объявления"""

        self.url = url
        self.phone = None

        self.t = time.clock()

        # Загружаем страницу объявления
        self.web_page.mainFrame().load(url)

        logger.debug('Начало выполнения загрузки "{}" {:.3f} секунд'.format(url, time.clock() - self.t))

        # Ждем тут, пока закончится парсинг объявления -- все из-за ассинхронности webpage и моей лени -- хочется
        # просто в цикле запустить обработку и url, но из-за асинхронности с сигналами это не сработает -- какая-то
        # лажа происходит -- падает приложение с ошибкой где-то в QtCore.dll
        loop = QEventLoop()
        self.parse_phone_finished.connect(loop.quit)
        loop.exec_()

        logger.debug('Время выполнения парсера {:.3f} секунд'.format(time.clock() - self.t))
        self.t = None

    def get_phone(self):
        """Функция выполняет поиск картинки с номером телефона, получает его адрес, скачивает, а после
        парсит картинку с номером и записывает в self.phone номер телефона. После парсинга вызывает сигнал
        parse_phone_finished, в котором передается номер телефона.

        """

        # Ищем элемент с картинкой телефона
        el = self.web_page.mainFrame().findFirstElement("img[class='description__phone-img']")

        logger.debug('Поиск изображения телефона {:.3f} секунд'.format(time.clock() - self.t))

        ok = not el.isNull()
        if ok:
            src = el.attribute('src')
            logger.debug('Атрибут src картинки с телефоном: "%s".', src)
            src = src.replace('data:image/png;base64,', '')
            logger.debug('Данные картинки с телефоном: "%s".', src)
            data = base64.b64decode(src)

            # TODO: вызывать исключение, если номер не найден
            # TODO: вызывать исключение, если номер не 11 символов (нормальный номер: 89615750404)
            phone_number = self.phone_img_parser.parse_from_data(data)
            logger.debug('Телефон получен: %s', phone_number)
            logger.debug('Парсинг номера телефона из картинки {:.3f} секунд'.format(time.clock() - self.t))

            self.phone = phone_number
            self.parse_phone_finished.emit(phone_number)

    def find_and_click_element(self):
        """Функция ищет на странице объявления элемент 'Показать телефон' и кликает его, чтобы
        выполнились страшные скрипты и загрузилась картинка с номером телефона

        """

        code = """
        span_phone = $("span[class='description__phone-insert js-phone-show__insert'] span[class='btn__text']")
        span_phone.click()
        """

        logger.debug('Выполняю программный клик по кнопке "Получить телефон"')
        ok = self.web_page.mainFrame().evaluateJavaScript(code)
        if ok is None:
            logger.warn('Выполнение js скрипта неудачно. Code:\n%s', code)
            return

        logger.debug('Время выполнения js скрипта {:.3f} секунд'.format(time.clock() - self.t))
        self.get_phone()

    def load_finished(self, x):
        """Функция вызывается, когда QWebView отсылает сигнал loadFinished"""

        if x and self.phone is None:
            logger.info('Загрузка завершена {:.3f} секунд'.format(time.clock() - self.t))
            self.find_and_click_element()
