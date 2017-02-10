#@ -*- coding: utf-8 -*-
credentials = {
    'login_username': u'gran12',
    'login_password': u'ox0Ip'
}

import cookielib
from urllib import urlencode, quote, unquote
from urllib2 import build_opener, HTTPCookieProcessor, URLError, HTTPError
from HTMLParser import HTMLParser
import tempfile
import os
import re
import logging

def dict_encode(dict, encoding='cp1251'):
    encoded_dict = { key : dict[key].encode(encoding) for key in dict}
    return encoded_dict

class rutracker(object):
    url = 'http://rutracker.org'
    name = 'rutracker.org'
    login_url = 'http://login.rutracker.org/forum/login.php'
    download_url = 'http://dl.rutracker.org/forum/'
    search_url = 'http://rutracker.org/forum/tracker.php'

    def __init__(self):
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.credentials = credentials
        self.credentials['login'] = u'Вход'

        try:
            logging.info("Trying to connect using given credentials")
            response = self.opener.open(self.login_url, urlencode(dict_encode(self.credentials)).encode())
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
            if not 'bb_data' in [cookie.name for cookie in self.cj]:
                raise ValueError("Unable to connect using given credentials")
            else:
                logging.info("Login succesful.")
        except (URLError, HTTPError, ValueError) as e:
            logging.error(e)

    class Parser(HTMLParser):

        def __init__(self, download_url, first_page=True):
            HTMLParser.__init__(self)
            self.download_url = download_url
            self.first_page = first_page
            self.results = []
            self.other_pages = []
            self.tr_counter = 0
            self.cat_re = re.compile(r'tracker\.php\?f=\d+')
            self.name_re = re.compile(r'viewtopic\.php\?t=\d+')
            self.link_re = re.compile(r'('+self.download_url+'dl\.php\?t=\d+)')
            self.pages_re = re.compile(r'tracker\.php\?.*?start=(\d+)')
            self.reset_current()

        def reset_current(self):
            self.current_item = { 'cat': None,
                                  'name': None,
                                  'link': None,
                                  'size': None,
                                  'seeds': None,
                                  'leech': None,
                                  'desc_link': None}
        def close(self):
            self.results.append(self.current_item)
            HTMLParser.close(self)

        def handle_data(self, data):
            """Retrieve inner text information based on rules defined in do_tag()."""
            for key in self.current_item:
                if self.current_item[key] == True:
                    self.current_item[key] = data
                    logging.debug((self.tr_counter, key, data))

        def handle_starttag(self, tag, attrs):
            """Pass along tag and attributes to dedicated handlers. Discard any tag without handler."""
            try:
                getattr(self, 'do_{}'.format(tag))(attrs)
            except:
                pass

        def do_tr(self, attr):
            """<tr class="tCenter"> is big container for one torrent, so we store current_item and reset it."""
            params = dict(attr)
            try:
                if 'tCenter' in params['class']:
                    if self.tr_counter != 0:
                        # We only store current_item if torrent is still alive
                        if self.current_item['seeds'] != None:
                            self.results.append(self.current_item)
                        else:
                            self.tr_counter -= 1
                    logging.debug(self.current_item)

                    self.tr_counter += 1
            except KeyError:
                pass

        def do_a(self, attr):
            """ <a> tags can specify torrent link in "href" or category or name in inner text. Also used to retrieve further results pages """
            params = dict(attr)
            try:
                link = self.link_re.search(params['href'])
                if link:
                    self.current_item['link'] = link.group(0)
                    logging.debug((self.tr_counter, 'link', link.group(0)))
                elif self.cat_re.search(params['href']):
                    self.current_item['cat'] = True
                elif 'data-topic_id' in params and self.name_re.search(params['href']):
                    self.current_item['desc_link'] = 'http://rutracker.org/forum/' + params['href']
                    self.current_item['name'] = True
                elif self.first_page:
                    pages = self.pages_re.search(params['href'])
                    if pages:
                        if pages.group(1) not in self.other_pages:
                            self.other_pages.append(pages.group(1))
            except KeyError:
                pass

        def do_td(self, attr):
            """ <td> tags give us number of leechers in inner text and can signal torrent size in next <u> tag.  """
            params = dict(attr)

            try:
                if 'tor-size' in params['class']:
                    self.current_item['size'] = False
                elif 'leechmed' in params['class']:
                    self.current_item['leech'] = True
            except KeyError:
                pass

        def do_u(self, attr):
            """ <u> tags give us torrent size in inner text. """
            if self.current_item['size'] == False:
                self.current_item['size'] = True

        def do_b(self, attr):
            params = dict(attr)
            try:
                if 'seedmed' in params['class']:
                    self.current_item['seeds'] = True
            except KeyError:
                pass

    def parse_search(self, what, start=0, first_page=True):
        """Search for what starting on specified page. Defaults to first page of results"""
        logging.debug("parse_search({}, {}, {}".format(what, start, first_page))
        # Search

        parser = self.Parser(self.download_url, first_page)

        try:
            response = self.opener.open('{}?nm={}&start={}'.format(self.search_url, quote(what), start))
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info, None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            return

        data = response.read().decode('cp1251')
        parser.feed(data)
        parser.close()

        for torrent in parser.results:
            torrent['engine_url'] = self.url

        if parser.tr_counter == 0:
            return

        return (parser.tr_counter, parser.other_pages)

    def search(self, what, cat='all'):
        what = unquote(what)
        logging.info("Searching for {} ... ".format(what))
        logging.info("Parsing page 1.")
        results = self.parse_search(what)

        if results == None:
            return

        (total, pages) = results
        logging.info("{} pages of results found.".format(len(pages)+1))

        for start in pages:
            logging.info("Parsing page {}.".format(int(start)/50+1))
            results = self.parse_search(what, start, False)
            if results != None:
                (counter, _) = results
                total += counter

        logging.info("{} torrents found.".format(total))

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    engine = rutracker()
    engine.search('Muse')