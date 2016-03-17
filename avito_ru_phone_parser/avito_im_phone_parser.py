#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from PIL import Image
from io import BytesIO
import glob
import time


BLACK_PXL = 0


def get_margins(im):
    """Функция для определения границ номера сотового"""

    w, h = im.size
    left, right, top, bottom = w, -1, h, -1

    for y in range(h):
        for x in range(w):
            pxl = im.getpixel((x, y))

            if pxl == BLACK_PXL:
                if left > x:
                    left = x

                if right < x:
                    right = x

                if top > y:
                    top = y

                if bottom < y:
                    bottom = y

    return left, right, top, bottom


def crop_im_phone(im):
    """Функция вырезает из изображения номер сотового и возвращает его копию"""

    left, right, top, bottom = get_margins(im)
    return im.crop((left, top, right+1, bottom+1))


from abstract_site_ad_parser import get_logger
logger = get_logger('avitoru_image_phone_parser')


NUMBERS_DIR = 'numbers'


class AvitoPhoneImgParser:
    """Класс для разбора изображения номера телефона, который дает авито"""

    def __init__(self):
        self.num_img_list = dict()

        logger.debug('Получаю список картинок цифр из папки "%s"', NUMBERS_DIR)
        num_file_list = glob.glob("{}/*.png".format(NUMBERS_DIR))
        num_file_list = sorted(num_file_list)

        # От 0 до 9 может быть
        if len(num_file_list) != 10:
            raise Exception('Файлов изображений в папке "{}" может быть только 10 -- для '
                            'каждой цифры свой файл. Найдено же {}.'.format(NUMBERS_DIR, len(num_file_list)))

        logger.debug('Выполняю загрузку файлов изображений и заполнение словаря изображений цифр')

        for i, path in enumerate(num_file_list):
            num_im = Image.open(path).convert('L')
            self.num_img_list[i] = num_im

        logger.debug('Закончена загрузка файлов изображений и заполнение словаря изображений цифр')

    def parse_from_data(self, byte_data):
        """Функция принимает байтовый массив, представляющий собой изображение с телефоном,
        парсит и возвращает строку с номером телефона

        """

        logger.debug('Открываю изображение телефона от байтового массива')

        ph_im = Image.open(BytesIO(byte_data)).convert('L')
        ph_im = crop_im_phone(ph_im)

        logger.debug('Закончена подготовка изображения')

        ph_w, ph_h = ph_im.size

        phone_number = ""

        logger.debug('Начинаю разбор изображения телефона')

        t = time.clock()

        # Перебираем каждый x картинки с телефоном
        for offset in range(ph_w + 1):
            # На каждом шагу x проверяем на совпадение с изображением цифры
            for num, im_num in self.num_img_list.items():
                num_w, num_h = im_num.size

                # Проверяем границы -- в какой-то момент картинки цифр будут выходить из за границы
                if offset + num_w > ph_w:
                    continue

                find = True

                # По пиксельно проверяем текущую область картинки сотового на совпадение с цифрой
                for x in range(num_w):
                    for y in range(num_h):
                        ph_pxl = ph_im.getpixel((x + offset, y))
                        num_pxl = im_num.getpixel((x, y))
                        if ph_pxl != num_pxl:
                            find = False
                            break

                # Если нашли, добавляем цифру в строку с телефоном
                if find:
                    phone_number += str(num)

        logger.debug('Разбор изображения телефона закончено за {:.3f} секунд'.format(time.clock() - t))

        logger.debug('Закончил разбор, телефон: "%s", длина %s символов', phone_number, len(phone_number))
        return phone_number
