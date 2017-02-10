# @ -*- coding: utf-8 -*-
import cookielib
from urllib import urlencode, quote, unquote
from urllib2 import build_opener, HTTPCookieProcessor, URLError, HTTPError, ProxyHandler
from HTMLParser import HTMLParser
from urlparse import urlparse
import re
import logging
import tempfile
import os


def dict_encode(dict, encoding='cp1251'):
    encoded_dict = { key : dict[key].encode(encoding) for key in dict}
    return encoded_dict


class RutrackerParser(HTMLParser):

    def __init__(self, first_page=True):
        HTMLParser.__init__(self)
        self.download_url = 'http://dl.rutracker.org/forum/'
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
                        self.reset_current()
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


class KinozalParser(HTMLParser):

    def __init__(self, first_page=True):
        HTMLParser.__init__(self)
        self.download_url = 'http://dl.kinozal.tv/download.php?'
        self.first_page = first_page
        self.results = []
        self.other_pages = []
        self.tr_counter = 0
        self.td_counter = 0 # костыль для парсинга размера
        self.desc_re = re.compile(r'/details\.php\?id=\d+')
        self.pages_re = re.compile(r'\?.*?page=(\d+)')
        self.reset_current()

    def reset_current(self):
        self.current_item = { 'name': None,
                              'link': None,
                              'size': None,
                              'seeds': None,
                              'leech': None,
                              'desc_link': None,
                              'comm_cnt': None,
                              'date': None}
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
        """<tr class="bg"> is big container for one torrent, so we store current_item and reset it."""
        params = dict(attr)
        try:
            if 'bg' in params['class']:
                if self.tr_counter != 0:
                    # We only store current_item if torrent is still alive
                    if self.current_item['seeds'] != None:
                        self.results.append(self.current_item)
                        self.reset_current()
                    else:
                        self.tr_counter -= 1
                logging.debug(self.current_item)

                self.tr_counter += 1
        except KeyError:
            pass

    def do_td(self, attr):
        params = dict(attr)
        try:
            if 'nam' in params['class']:
                self.current_item['name'] = True
            elif 'sl_s' in params['class']:
                self.current_item['seeds'] = True
            elif 'sl_p' in params['class']:
                self.current_item['leech'] = True
            elif 's' == params['class']:
                if self.current_item['comm_cnt'] is None:
                    self.current_item['comm_cnt'] = True
                elif self.current_item['size'] is None:
                    self.current_item['size'] = True
                elif self.current_item['date'] is None:
                    self.current_item['date'] = True

        except KeyError:
            pass

    def do_a(self, attr):
        """ <a> tags can specify torrent link in "href" or category or name in inner text. Also used to retrieve further results pages """
        params = dict(attr)
        try:
            link = self.desc_re.search(params['href'])
            if link:
                self.current_item['desc_link'] = "http://kinozal.tv" + link.group(0)
                self.current_item['link'] = self.download_url + urlparse("http://kinozal.tv" + link.group(0)).query
                logging.debug((self.tr_counter, 'link', link.group(0)))
            elif self.first_page:
                pages = self.pages_re.search(params['href'])
                if pages:
                    if pages.group(1) != u'0' and pages.group(1) not in self.other_pages:
                        self.other_pages.append(pages.group(1))
        except KeyError:
            pass


class TorrentSearch(object):

    def __init__(self, **kwargs):#tracker_name):
        self.cj = cookielib.CookieJar()
        self.tracker_name = kwargs.get("tracker_name")
        self.credentials = kwargs.get("credentials")

        if self.tracker_name == 'rutracker':
            self.url = 'http://rutracker.org'
            self.name = 'rutracker.org'
            self.login_url = 'http://login.rutracker.org/forum/login.php'
            self.download_url = 'http://dl.rutracker.org/forum/'
            self.search_url = 'http://rutracker.org/forum/tracker.php'
            self.need_proxy = False
            self.cookie_value = 'bb_data'
            self.format_string = '{}?nm={}&start={}'

        elif self.tracker_name == 'kinozal':
            self.url = 'http://kinozal.tv'
            self.name = 'kinozal.tv'
            self.login_url = 'http://kinozal.tv/takelogin.php'
            self.download_url = 'http://dl.kinozal.tv/'
            self.search_url = 'http://kinozal.tv/browse.php'
            self.need_proxy = True
            self.cookie_value = 'pass'
            self.format_string = '{}?s={}&page={}'
        else:
            raise Exception('Wrong tracker name!!!')

        if self.need_proxy:
            self.opener = build_opener(ProxyHandler({'http': '158.69.218.198'}), HTTPCookieProcessor(self.cj))
        else:
            self.opener = build_opener(HTTPCookieProcessor(self.cj))

        try:
            logging.info("Trying to connect using given credentials")
            response = self.opener.open(self.login_url, urlencode(dict_encode(self.credentials)).encode())
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
            if not self.cookie_value in [cookie.name for cookie in self.cj]:
                raise ValueError("Unable to connect using given credentials")
            else:
                logging.info("Login succesful.")
        except (URLError, HTTPError, ValueError) as e:
            logging.error(e)


    def logging_to_tracker(self):
        if self.need_proxy:
            self.opener = build_opener(ProxyHandler({'http': '158.69.218.198'}), HTTPCookieProcessor(self.cj))
        else:
            self.opener = build_opener(HTTPCookieProcessor(self.cj))

        try:
            logging.info("Trying to connect using given credentials")
            response = self.opener.open(self.login_url, urlencode(dict_encode(self.credentials)).encode())
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
            if not self.cookie_value in [cookie.name for cookie in self.cj]:
                raise ValueError("Unable to connect using given credentials")
            else:
                logging.info("Login succesful.")
                return 0

        except (URLError, HTTPError, ValueError) as e:
            logging.error(e)
            return -1

    def parse_search(self, what, start=0, first_page=True):
        """Search for what starting on specified page. Defaults to first page of results"""
        logging.debug("parse_search({}, {}, {}".format(what, start, first_page))
        # Search
        if self.tracker_name == "rutracker":
            parser = RutrackerParser()
        elif self.tracker_name == "kinozal":
            parser = KinozalParser()
        else:
            raise Exception("Unknown Torrent Tracker!!!!")

        try:
            response = self.opener.open(self.format_string.format(self.search_url, quote(what), start))
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info, None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            return

        data = response.read().decode('cp1251')
        parser.feed(data)
        parser.close()

        if parser.tr_counter == 0:
            return

        return (parser.tr_counter, parser.results, parser.other_pages)

    def search(self, what, cat='all'):
        what = unquote(what)
        logging.info("Searching for {} ... ".format(what))
        logging.info("Parsing page 1.")
        results = self.parse_search(what)

        if results == None:
            return

        (total, torrents, pages) = results
        result_torrents = [torrent for torrent in torrents]
        logging.info("{} pages of results found.".format(len(pages)+1))

        for start in pages:
            if self.tracker_name == "rutracker":
                logging.info("Parsing page {}.".format(int(start)/50+1))
            else:
                logging.info("Parsing page {}.".format(int(start)+1))

            results = self.parse_search(what, start, False)
            if results != None:
                (counter, torrents, _) = results
                for torrent in torrents:
                    result_torrents.append(torrent)
                total += counter

        logging.info("{} torrents found.".format(total))
        return result_torrents

    def download_torrent(self, url):
        f, path = tempfile.mkstemp()
        f = os.fdopen(f, "wb")

        #set up fake POST params, needed to trick server into sending the file
        if self.tracker_name == "rutracker":
            id = re.search(r'dl\.php\?t=(\d+)', url).group(1)
        elif self.tracker_name == "kinozal":
            id = re.search(r'download\.php\?id=(\d+)', url).group(1)
        else:
            id = 0
        post_params = {'t': id,}

        try:
            response = self.opener.open(url, urlencode(dict_encode(post_params)).encode())
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            return

        data = response.read()
        f.write(data)
        f.close()
        return path
