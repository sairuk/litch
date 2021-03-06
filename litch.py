#!/usr/bin/env python3
#
# litch - sairuk
#
# A fairly barebone leecher for itch.io 
# - login  
# - download purchases
# - auto claim bundles
#
# Code is jank af, covers the two f's, fkd and functional
#

import requests
import pickle
import os
import json
import argparse
import getpass
from time import sleep
from bs4 import BeautifulSoup

APP_NAME="litch"
APP_VER="0.1alpha"

GAME_STORAGE_DIR = r'.'
COOKIES_FILENAME = r'itchio-cookies.dat'

CONFIG_STORAGE_DIR = os.path.expanduser('~/.litch')
COOKIES_ABSPATH = os.path.join(CONFIG_STORAGE_DIR,COOKIES_FILENAME)

# ITCH URLs
ITCH_HOST = r'itch.io'
ITCH_HOME_URL = r'https://itch.io'
ITCH_ACCOUNT_URL = r'https://itch.io/dashboard'
ITCH_LOGIN_URL = r'https://itch.io/login'
ITCH_LIBRARY = r'https://itch.io/my-collections'
ITCH_CLAIMED = r'https://itch.io/my-purchases'
ITCH_BUNDLES = r'https://itch.io/my-purchases/bundles'

DEBUG=False

PAGE_DELAY=5
ITEM_DELAY=2

USER_AGENT="%s/%s" % ( APP_NAME, APP_VER)


def _log(s, level=1):

    levels = {
        1 : "INFO",
        2 : "WARN",
        3 : "DEBUG",
    }

    if level == 3 and not DEBUG:
        return

    print("[%s] %s" % (levels[level], s))

### from here coz its late 
# https://github.com/eddie3/gogrepo/blob/6685e761f779809c90607af445b632211604f25c/gogrepo.py
def auto_size(b):

    if b > 1024**3:
        return '%.2fGB' % (b / float(1024**3))
    elif b > 1024**2:
        return '%.1fMB' % (b / float(1024**2))
    elif b > 1024:
        return '%.1fKB' % (b / float(1024))
    else:
        return '%dB' % (b)
        

def doconn(client, url, conn_type="GET", headers={}, payload={}, stream=False, retry=1, retries=3):

    exception = False
    try:
        r = None
        if conn_type == "GET":
            r = client.get(url, data=payload, headers=headers, stream=stream)
        elif conn_type == "POST":
            r = client.post(url, data=payload, headers=headers, stream=stream)
        elif conn_type == "HEAD":
            r = client.head(url, data=payload, headers=headers, stream=stream)
        if r.status_code == 200:
            return r
        else:
            exception = True
    except:
        _log("Connection failed, going to retry")
        exception = True

    if exception:
        if retry <= retries:
            retry += 1
            doconn(client, url, conn_type, headers, payload, stream, retry)
            sleep(PAGE_DELAY)

    return None



def login():

    client = requests.session()
    r = doconn(client, ITCH_LOGIN_URL, conn_type="GET")

    soup = BeautifulSoup(r.text, 'lxml')
    target = soup.find('input', attrs={'type':'hidden','name':'csrf_token'})
    csrftoken = target.attrs['value']

    print("\n%s %s\n\nLogin process starting, prepare to login\n" % (APP_NAME, APP_VER))

    EMAIL = input("Email Address: ")
    PASSWORD = getpass.getpass()

    login_data = dict(username=EMAIL, password=PASSWORD, csrf_token=csrftoken)

    ### Login
    headers =   {   
                    'User-Agent' : USER_AGENT,
                    'Referer' : ITCH_LOGIN_URL
                }    
    r = doconn(client, ITCH_LOGIN_URL, conn_type="POST", headers=headers, payload=login_data)
    if r.status_code == 200:
        _log("Login successful")
        if "totp" in r.url:
            # handle MFA
            _log("Handling MFA")
            target = soup.find('input', attrs={'type':'hidden','name':'csrf_token'})
            csrftoken = target.attrs['value']

            value = input("Enter MFA code: ")
            login_data = dict(code=value, csrf_token=csrftoken)
            headers =   {   
                            'User-Agent' : USER_AGENT,
                            'Referer' : ITCH_LOGIN_URL
                        }
            m = client.post(r.url, data=login_data, headers=headers)

            if m.status_code == 200:
                # MFA successul, we should write out the cookies
                _log("MFA was successful")
                _log("Dumping cookies file", 3)
                with open(COOKIES_ABSPATH, 'wb') as cj:
                    pickle.dump(client.cookies, cj)

            else:
                _log("MFA failed, waiting %ds and trying again" % 5)
                _log("Retry isn't really setup yet")
    else:
        _log("Login failed")

def bundles():
    _log("Loading Bundles")
    if os.path.exists(COOKIES_ABSPATH):
        client = requests.session()

        _log("Reading Cookies", 3)
        with open(COOKIES_ABSPATH, 'rb') as cj:
            client.cookies.update(pickle.load(cj))

        _log("Starting to read bundles pages", 3)
        url = "%s" % ITCH_BUNDLES
        _log("Reading page %s" % url)
        r = doconn(client, url=url, conn_type="GET")

        soup = BeautifulSoup(r.text, 'lxml')
        bundle_section = soup.find('section', attrs={'class':'bundle_keys'})
        bundle_links = bundle_section.findAll('a')
        _log("Found %d bundles" % len(bundle_links))

        for link in bundle_links:
            _log("Switching bundles: %s" % link.string)
            burl = "%s%s" % (ITCH_HOME_URL,link.attrs['href']) 
            _log(burl, 3)
            b = doconn(client, burl, conn_type="GET")

            if b.status_code == 200:
                _log("Success", 3)
                ### paginate
                next_page = ""
                next_href = 1
                
                _log("Starting to read bundles page(s)", 3)
                while next_page is not None:
                    purl = "%s?page=%s" % (burl, next_href)
                    p = doconn(client, purl, conn_type="GET")
                    _log("Reading %s" % purl, 3)
                    _log("Switching to page %s" % next_href)

                    target = soup.find('input', attrs={'type':'hidden','name':'csrf_token'})
                    csrftoken = target.attrs['value']

                    psoup = BeautifulSoup(p.text, 'lxml')
                    #targets = soup.findAll('button', attrs={'name':'action','value':'claim'})
                    targets = psoup.findAll('form', attrs={'class':'form','method':'post'})
                    _log("Found %d unclaimed items" % len(targets))

                    targets_title = psoup.findAll('div', attrs={'class':'game_row_data'})
                    
                    if len(targets_title) > 0:
                        _log("Starting claim process")
                        for target in targets_title:
                            game_id_target = target.find('input', attrs={'type':'hidden','name':'game_id'})
                            if str(game_id_target) == "None":
                                continue
                                
                            game_id = game_id_target['value']
                            game_title = target.find('h2', attrs={'class':'game_title'}).find('a').string

                            payload = dict(game_id=game_id, action='claim', csrf_token=csrftoken)
                            headers =   {   
                                            'User-Agent': USER_AGENT,
                                            'Referer': burl,
                                            'Origin': ITCH_HOME_URL,
                                            'Host': ITCH_HOST
                                        }
                            
                            game_title = ''.join(char for char in game_title if ord(char) < 128)
                            _log("Claiming game: %s (ID %s)" % (game_title, game_id))
                            doconn(client, burl, conn_type="POST", payload=payload, headers=headers)
                        
                            sleep(ITEM_DELAY)

                    next_page = psoup.find('a', attrs={'class':'next_page'})
                    next_href += 1
                    sleep(PAGE_DELAY)
            else:
                _log("Failed to get %s %s %s" % (burl, b.status_code, b.reason))
    else:
        login()
        bundles()

def purchases(GAME_STORAGE_DIR, cleanup=False, start_page=1):
    _log("Loading Purchases")
    _log("Will download to %s" % GAME_STORAGE_DIR)

    if os.path.exists(COOKIES_ABSPATH):
        client = requests.session()

        _log("Reading Cookies", 3)
        with open(COOKIES_ABSPATH, 'rb') as cj:
            client.cookies.update(pickle.load(cj))
        
        next_page = ""
        next_href = start_page

        _log("Starting to read purchase page(s)", 3)
        while next_page is not None:
            url = "%s?page=%s" % (ITCH_CLAIMED, next_href)
            _log("Reading page %s" % url)
            r =doconn(client, url, conn_type="GET")

            soup = BeautifulSoup(r.text, 'lxml')
            targets = soup.findAll('div', attrs={'class':'game_cell'})
            #targets = soup.findAll('a', attrs={'class':'button'})
            _log("Found %d potential targets" % len(targets))

            count = 1
            if len(targets) > 0:
                for ctarget in targets:

                    target = ctarget.find('a', attrs={'class':'button'}, text="Download")

                    target_href = target.attrs['href']
                    target_parts = target_href.split('/')
                    proto = target_parts[0]
                    developer = target_parts[2]
                    game = target_parts[3]
                    key = target_parts[-1]
                    _log("Trying game %s from %s" % (game, developer))
                    ITCH_DEV_URL = "%s//%s" % (proto, developer)

                    _log("===[ can resume from this page --start-page %s ]===" % next_href)

                    game_id = ctarget.attrs['data-game_id']
                    # game thumb
                    try:
                        game_thumb_div = ctarget.find('div', attrs={'class':'game_thumb'})
                        # vomit
                        game_thumb_url = game_thumb_div['style'].split('url(')[-1].replace("'","").replace(")","")
                        # game thumb extension
                        game_thumb_ext = os.path.splitext(game_thumb_url)[-1]
                        game_thumb = "%s%s" % ( game, game_thumb_ext )
                    except:
                        game_thumb = None
                        game_thumb_url = None
                        game_thumb_ext = None
                        game_thumb_div = None

                    # game nfo
                    try:
                        game_title = ctarget.find('a', attrs={'class':'title'}).text
                    except:
                        game_title = ""
                    try:
                        game_author = ctarget.find('a', attrs={'class':'game_link'}).text
                    except:
                        game_author = ""
                    try:
                        game_desc = ctarget.find('div', attrs={'class':'game_text'}).text
                    except:
                        game_desc = ""
                    gamenfo = "%s.nfo" % game

                    # load download page
                    _log("Load the download page for %s" % game, 3)
                    i = doconn(client, target_href, conn_type="GET")
                    dl_soup = BeautifulSoup(i.text, 'lxml')

                    # find all the downloads
                    _log("Look for download ids for %s" % game, 3)
                    download_ids = dl_soup.findAll('a', attrs={'class':'download_btn'})
                    _log("Found %d potential downloads" % len(download_ids))

                    # csrf_token
                    csrf_elem = dl_soup.find('input', attrs={'type':'hidden','name':'csrf_token'})
                    csrftoken = csrf_elem.attrs['value']
                                
                    old_outpath = os.path.join(GAME_STORAGE_DIR, game)
                    outpath = os.path.join(GAME_STORAGE_DIR, "%s_(%s)" % ( game, game_id ) )

                    # check if data path exists and move and append game_id
                    if os.path.exists(old_outpath):
                        os.rename(old_outpath, outpath)

                    _log("Output path is now %s" % outpath)

                    if not os.path.exists(outpath):
                        os.mkdir(outpath)

                    # download thumb
                    if 'http' in game_thumb_url:
                        _log("Attempted to download thumb: %s" % game_thumb_url)
                        out_game_thumb = os.path.join(outpath, "%s_%s" % ( APP_NAME, game_thumb))
                        if not os.path.exists(out_game_thumb):
                            _log("Creating thumb: %s" % out_game_thumb)
                            dl = doconn(client, game_thumb_url, conn_type="GET", stream=True)
                            with open(out_game_thumb, 'wb') as gt:
                                gt.write(dl.content)
                        else:
                            _log("Thumb already downloaded")
                    else:
                        _log("No thumb available for %s" % game)

                    # create nfo
                    out_game_nfo = os.path.join(outpath, "%s_%s" % ( APP_NAME, gamenfo))
                    if not os.path.exists(out_game_nfo):
                        _log("Creating nfo: %s" % out_game_nfo)                    
                        with open(out_game_nfo, 'w') as gn:
                            gn.write("title: %s\n" % game_title)
                            gn.write("description: %s\n" % game_desc)
                            gn.write("game_id: %s\n" % game_id)
                            gn.write("author: %s\n" % game_author)
                    else:
                        _log(".nfo already created")

                    cntr = 0
                    for download_id in download_ids:
                        
                        download_idn = download_id.attrs['data-upload_id']
                        _log("Found DOWNLOAD_ID: %s" % download_idn, 3)

                        dlurl = "%s/%s/file/%s?source=game_download&key=%s" % (ITCH_DEV_URL, game, download_idn, key)

                        payload = dict(csrf_token=csrftoken)
                        headers =   {   
                                        'User-Agent': USER_AGENT,
                                        'Referer': target_href,
                                        'Origin': ITCH_DEV_URL,
                                        'Host': developer
                                    }
                        _log("Attempting to initiate authorised download", 3)
                        dlf = doconn(client, dlurl, payload=payload, headers=headers, conn_type="POST")
                        
                        if dlf.status_code == 200:
                            _log("Success", 3)

                            _log("Attempting to get CDN link from JSON data", 3)
                            jd = json.loads(dlf.content.decode('utf-8'))

                            jdlurl = jd['url']
                            jdlext = jd['external']
                            jdlurl_pieces = jdlurl.split('/')
                            

                            filename = "tempfile"
                            if jdlext == True:
                                filename = jdlurl_pieces[-1]
                                referer = jdlurl_pieces[2]
                                _log("This is an externally hosted file: %s" % filename, 3)
                                headers =   {   
                                                'User-Agent': USER_AGENT,
                                                'Referer': referer,
                                                'Origin': ITCH_DEV_URL,
                                                'Host': referer
                                            }
                            else:
                                _log("Found CDN link on %s" % jdlurl_pieces[2], 3)
                                _log("Attempting to start download", 3)
                                headers =   {   
                                                'User-Agent': USER_AGENT,
                                                'Referer': target_href,
                                                'Origin': ITCH_DEV_URL,
                                                'Host': jdlurl_pieces[2]
                                            }
                                dl = doconn(client, jdlurl, headers=headers, conn_type="HEAD")
                                if dl is not None:
                                    if 'content-disposition' in dl.headers.keys():
                                        content_disposition = dl.headers['Content-Disposition']
                                        filename = content_disposition.split("=")[-1].replace('"','')
                                    elif'GoogleAccessId' in jdlurl:
                                        ## old google?
                                        filename = jdlurl.split('?')[0].split('/')[-1]
                                    size = int(dl.headers['Content-Length'])
                                    _log("Found %s (%s)" % (filename, auto_size(size)))
                                else:
                                    _log("Failed to get headers for %s, dumping" % (jdlurl))
                                    _log(dl.headers)
                                    next


                            if not os.path.exists(outpath):
                                os.mkdir(outpath)

                            outfile = os.path.join(outpath, filename)

                            if os.path.exists(outfile):
                                _log("Looking for existing file")
                                if jdlext == False:
                                    # check the size, we dont have a hash to check against :(
                                    # but at least google cdn gives us the content-length
                                    ondisk_size = os.path.getsize(outfile)
                                    if ondisk_size != size:
                                        _log("Filename: %s\n\tFilesize BAD\n\tExpected: %s\n\tFound: %s" % (filename, auto_size(size), auto_size(ondisk_size)))
                                        if cleanup:
                                            _log("User asked to cleanup, removing to redownload")
                                            try:
                                                os.remove(outfile)
                                            except:
                                                _log("Removal failed for %s" % filename)
                                        else:
                                            _log("Filesize is wrong but user did not as for automated cleanup %s" % filename)
                                    else:
                                        _log("Filename: %s\n\tFilesize GOOD\n\tExpected: %s\n\tFound: %s" % (filename, auto_size(size), auto_size(ondisk_size)))
                                else:
                                    _log("Existing file not found")


                            if not os.path.exists(outfile):
                                _log("Attempting Download of %s (%s)" % (filename, auto_size(size)))
                                dl = doconn(client, jdlurl, headers=headers, stream=True, conn_type="GET")
                                if dl is not None:
                                    if dl.status_code == 200:
                                        _log("Downloading %s (%s)" % (filename, auto_size(size)))
                                        with open(outfile, 'wb') as f:
                                            f.write(dl.content)
                                    else:
                                        _log("Download failed with %s %s" % (dl.status_code, dl.reason))
                                        _log(jdlurl)
                            else:
                                _log("File exists, skipping: %s (%s)" % (filename, auto_size(size)))

                    sleep(ITEM_DELAY)

            next_page = soup.find('a', text="Next page")
            next_href += 1
            sleep(PAGE_DELAY)

    else:
        login()
        purchases(GAME_STORAGE_DIR, cleanup)

def main(args):

    GAME_STORAGE_DIR = args.content_path

    # make directories
    if not os.path.exists(CONFIG_STORAGE_DIR):
        os.mkdir(CONFIG_STORAGE_DIR)

    if not os.path.exists(GAME_STORAGE_DIR):
        os.mkdir(GAME_STORAGE_DIR)

    if args.login:
        login()

    if args.claim_bundles:
        bundles()

    if args.download_purchases:
        if args.cleanup_incorrect_files:
            purchases(GAME_STORAGE_DIR, True, args.start_page)
        else:
            purchases(GAME_STORAGE_DIR)

    return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='%s, leech itch.io purchases' % APP_NAME)

    parser.add_argument('--login', const=True, default=False, type=bool, nargs="?",
                        help='login and refresh cookiejar')

    parser.add_argument('--claim-bundles', const=True, default=False, type=bool, nargs="?",
                        help='automatically claim bundles')

    parser.add_argument('--download-purchases', const=True, default=False, type=bool, nargs="?",
                        help='download all your purchases')

    parser.add_argument('--content-path', required=False, default='.', type=str,
                        help='Where to save downloads (default: current)')

    parser.add_argument('--cleanup-incorrect-files', const=True, default=False, type=bool, nargs="?",
                        help='remove incorrect files when found (filesize check on, itch internal hosting only)')

    parser.add_argument('--start-page', default=1, type=int,
                        help='override starting page')

    args = parser.parse_args()
    main(args)
