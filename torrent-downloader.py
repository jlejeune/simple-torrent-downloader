#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# TODO: use logging module to log everything
# TODO: show all downlable tv shows in a beautiful tab and select each one you want to download
# TODO: use classes to define providers
# TODO: move utils functions in an external module
# TODO: define filters outside

import requests
import argparse
import configparser
import re
import numbers
from urllib.parse import urlsplit
import os
from distutils.util import strtobool

from bs4 import BeautifulSoup
import putiopy


# Variables
ROOT_PAGE = 'http://www.torrent9.ec'
SERIES_URL = ROOT_PAGE + '/torrents_series.html'
FILTER_TITLE = "walking dead (.*) vostfr|mr. robot (.*) vostfr||homeland (.*)|big bang theory (.*) vostfr||new girl (.*) vostfr|game of (.*) vostfr"
FILTER_MIN_SIZE = 283115520  # 270 Mo
FILTER_MAX_SIZE = 943718400   # 900 Mo
TEMP_DIR = '/tmp/'
# Common disk size units, used for formatting and parsing.
DISK_SIZE_UNITS = (dict(prefix='b', divider=1, singular='octet', plural='octets'),
                   dict(prefix='k', divider=1024 ** 1, singular='Ko', plural='Ko'),
                   dict(prefix='m', divider=1024 ** 2, singular='Mo', plural='Mo'),
                   dict(prefix='g', divider=1024 ** 3, singular='Go', plural='Go'),
                   dict(prefix='t', divider=1024 ** 4, singular='To', plural='To'),
                   dict(prefix='p', divider=1024 ** 5, singular='Po', plural='Po'))


################################ Tools ########################################
def user_yes_no_query(question):
    print('%s [y/n]: ' % question)
    while True:
        try:
            return strtobool(input().lower())
        except ValueError:
            print('Please respond with \'y\' or \'n\':')


def tokenize(text):
    """
    Tokenize a text into numbers and strings.
    >>> tokenize('42')
    [42]
    >>> tokenize('42Mo')
    [42, 'Mo']
    """

    tokenized_input = []
    for token in re.split(r'(\d+(?:\.\d+)?)', text):
        token = token.strip()
        if re.match(r'\d+\.\d+', token):
            tokenized_input.append(float(token))
        elif token.isdigit():
            tokenized_input.append(int(token))
        elif token:
            tokenized_input.append(token)
    return tokenized_input


def parse_size(size):
    """
    Parse a human readable data size and return the number of bytes.
    >>> parse_size('42')
    42
    >>> parse_size('1 Ko')
    1024
    >>> parse_size('5 kilooctet')
    5120
    >>> parse_size('1.5 Go')
    1610612736
    """
    tokens = tokenize(size)
    if tokens and isinstance(tokens[0], numbers.Number):
        # If the input contains only a number, it's assumed to be the number of bytes.
        if len(tokens) == 1:
            return int(tokens[0])
        # Otherwise we expect to find two tokens: A number and a unit.
        if len(tokens) == 2 and isinstance(tokens[1], basestring):
            normalized_unit = tokens[1].lower()
            # Try to match the first letter of the unit.
            for unit in DISK_SIZE_UNITS:
                if normalized_unit.startswith(unit['prefix']):
                    return int(tokens[0] * unit['divider'])


def filter_links(links):
    filtered_links = links.copy()
    for link, value in links.items():
        #print(link, value['title'], value['size'])
        m = re.search(FILTER_TITLE, value['title'], flags=re.IGNORECASE)
        size = parse_size(value['size'])
        if not m or size < FILTER_MIN_SIZE or size > FILTER_MAX_SIZE:
        #if not m:
            del filtered_links[link]
    return filtered_links


def download_file(url):
    filename = os.path.basename(urlsplit(url)[2])
    r = requests.get(url)
    if r.status_code == 200:
        with open(TEMP_DIR + filename, 'wb') as f:
            f.write(r.content)
        return TEMP_DIR + filename


def upload_torrent_to_putio(token, filename, parent_id):
    client = putiopy.Client(token)
    client.Transfer.add_torrent(filename, parent_id)
    os.remove(filename)


def define_options():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', help='no filter', action='store_true')
    parser.add_argument('--quizz', help='interactive mode', action='store_true')
    parser.add_argument('--dry-run', help='test filters', action='store_true')
    parser.add_argument('--parent-id',
                        dest='parent_id',
                        help='destination putio folder parent id',
                        default=424351456)
    parser.add_argument('--config-file',
                        dest='config_file',
                        help="configuration file",
                        default='~/.putio-cli/config.ini',
                        metavar='FILE')
    return vars(parser.parse_args())
###############################################################################


############################## Torrent9 #######################################
def extract_links_from_torrent9():
    r = requests.get(SERIES_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find('div', {'class': ['table-responsive']})
    table_body = table.find('tbody')
    rows = table_body.find_all('tr')
    divs = dict()
    for row in rows:
        a = row.find('a')
        divs[a.attrs['href']] = dict()
        #divs[a.attrs['href']]['size'] = size.text.strip()
        divs[a.attrs['href']]['title'] = a.text
    return divs


def extract_torrent_links_from_torrent9(links):
    for link in links:
        r = requests.get(ROOT_PAGE + link)
        soup = BeautifulSoup(r.text, "html.parser")
        torrent_link = soup.find('div', {'class': ['download-btn']}).find('a')
        links[link]['torrent_link'] = ROOT_PAGE + torrent_link.attrs['href']
###############################################################################


def main():
    options = define_options()

    # load settings from external config file
    config = configparser.RawConfigParser()
    config.read(os.path.expanduser(options['config_file']))
    for section in config.sections():
        for key, value in config.items(section):
            key = section + '.' + key
            options[key] = value

    links = extract_links_from_torrent9()

    if not options['all']:
        filtered_links = filter_links(links)
    else:
        filtered_links = links
    extract_torrent_links_from_torrent9(filtered_links)
    for values in filtered_links.values():
        if not options['dry_run']:
            if options['quizz']:
                if not user_yes_no_query('Do you want to download %s?' % values['title']):
                    continue
            filename = download_file(values['torrent_link'])
            if filename:
                upload_torrent_to_putio(options['Settings.oauth-token'], filename, options['parent_id'])
                print("%s (%s) sent to put.io" % (values['title'], values['size']))
        else:
            print("%s (%s) will be downloaded" % (values['title'], values['size']))

if __name__ == '__main__':
    main()
