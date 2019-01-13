#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Created on 2019-01-10 14:05:42
# Project: novel_qidian
import os
import re

import requests
from fontTools.ttLib import TTFont
from pyspider.libs.base_handler import *
from io import BytesIO
import header_selector


class Handler(BaseHandler):
    crawl_config = {
        "user_agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36",
        "timeout": 20,
        "connect_timeout": 10,
        "retries": 3,
        "fetch_type": 'None',
        "auto_recrawl": False,
    }
    headers = header_selector.HeadersSelector()

    @every(minutes=24 * 60)
    def on_start(self):
        self.crawl('https://www.qidian.com/all?orderId=11', callback=self.index_page,
                   headers=self.headers.select_header())

    @config(age=24 * 60 * 60)
    def index_page(self, response):
        for each in response.doc('a[href^="http"]').items():
            if re.match("https://book.qidian.com/info/\d+$", each.attr.href):
                self.crawl(each.attr.href, callback=self.detail_page, headers=self.headers.select_header())
        for each in response.doc('.lbf-pagination-next').items():
            self.crawl(each.attr.href, callback=self.index_page, headers=self.headers.select_header())
        # 爬取每本书的收藏数
        pattern = re.compile('<div.*?book-mid-info.*?>.*?<h4>.*?href="(.*?)(?#书本链接地址)'
                             '".*?</h4>.*?</style><span.*?>((?:\&#\d+;){1,})(?#收藏数字)</span>([万]总收藏)', re.S)
        tuple_list = re.findall(pattern, response.text)
        encode_number_list = [num for (url, num, decs) in tuple_list]
        anti_spider_font = AntiSpiderFont()
        num_list = anti_spider_font.get_nums(response.text, encode_number_list)
        favor_list = []
        for i in range(len(tuple_list)):
            favor = float(num_list[i])
            if tuple_list[i][2][0] == "万":
                favor *= 10000
            favor_list.append({
                "url": "https:" + tuple_list[i][0],
                "favor": int(favor)
            })
        return favor_list

    @config(priority=2)
    def detail_page(self, response):
        anti_spider_font = AntiSpiderFont()
        #  获取当前页面所有被字符数字及单位（字数，阅文总点击， 会员周点击， 总推荐， 周推荐）
        pattern = re.compile('</style><span.*?>((?:\&#\d+;){1,})(?#编码的数字)'
                             '</span>.*?<cite>(.*?)</cite>', re.S)
        tuple_list = re.findall(pattern, response.text)
        encode_number_list = [num for (num, decs) in tuple_list]
        num_list = anti_spider_font.get_nums(response.text, encode_number_list)
        hits = float(num_list[1])
        if tuple_list[1][1][0] == "万":
            hits *= 10000
        recommended_votes = int(response.doc('.rec-ticket .num #recCount').text())
        monthly_ticket = int(response.doc('.month-ticket .num #monthCount').text())
        return {
            # 书籍的链接
            "url": response.url,
            # 书名
            "title": response.doc('h1 > em').text(),
            # 作者
            "author": response.doc('h1 a').text(),
            # 点击数
            "hits": int(hits),
            # 订阅数
            "subscription": 0,
            # 推荐票
            "recommendedVotes": recommended_votes,
            # 月票
            "monthlyTicket": monthly_ticket
        }


class AntiSpiderFont(object):
    def __init__(self):
        self.headers = {
            'Connection': "keep-alive",
            'Pragma': "no-cache",
            'Cache-Control': "no-cache",
            'Upgrade-Insecure-Requests': "1",
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36",
            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            'Accept-Encoding': "gzip, deflate, br",
            'Accept-Language': "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.WORD_MAP = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7',
                         'eight': '8', 'nine': '9', 'period': '.'}

    def _get_font(self, url):
        response = requests.get(url, headers=self.headers)
        font = TTFont(BytesIO(response.content))
        cmap = font.getBestCmap()
        font.close()
        return cmap

    def _get_encode(self, cmap, values):
        word_count = ''
        value_list = values.split(';')
        value_list.pop(-1)
        for value in value_list:
            value = value[2:]
            key = cmap[int(value)]
            word_count += self.WORD_MAP[key]
        return word_count

    def get_nums(self, response, encode_number_list):
        """
        :param response: str类型，页面数据
        :param encode_number_list: 编码的数字
        :return: 解码收的数字
        """
        # pattern = re.compile('</style><span.*?>(.*?)</span>', re.S)
        # pattern = re.compile('</style><span.*?>(.*?)</span>.*?<cite>(.*?)</cite>', re.S)
        # pattern = re.compile('</style><span.*?>((?:\&#\d+;){1,})</span>.*?<cite>(.*?)</cite>', re.S)
        # #  获取当前页面所有被字符数字及单位（字数，阅文总点击， 会员周点击， 总推荐， 周推荐）
        # tuple_list = re.findall(pattern, response)
        # number_list = [num for (num, decs) in tuple_list]
        # 获取当前包含字体文件链接的文本
        reg = re.compile('<style>(.*?)\s*</style>', re.S)
        font_url = re.findall(reg, response)[0]
        # 通过正则获取当前页面字体文件链接
        url = re.search('woff.*?url.*?\'(.+?)\'.*?truetype', font_url).group(1)
        cmap = self._get_font(url)
        # print('cmap:', cmap)
        num_list = []
        for num in encode_number_list:
            num_list.append(self._get_encode(cmap, num))
        return num_list
