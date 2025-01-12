#!/usr/bin/env python3
'''Reference: https://github.com/doubleplusc/Line-sticker-downloader/blob/master/sticker_dl.py'''

import requests
import json
import os
import io
import zipfile
import string
from urllib import parse
from PIL import Image
from bs4 import BeautifulSoup

from .download_base import DownloadBase
from ..utils.metadata_handler import MetadataHandler
from ..utils.get_line_auth import GetLineAuth

class MetadataLine:
    @staticmethod
    def analyze_url(url):
        region = ''
        is_emoji = False
        if url.startswith('line://shop/detail/'):
            pack_id = url.replace('line://shop/detail/', '')
            if len(url) == 24 and all(c in string.hexdigits for c in url):
                is_emoji = True
        elif url.startswith('https://store.line.me/stickershop/product/'):
            pack_id = url.replace('https://store.line.me/stickershop/product/', '').split('/')[0]
            region = url.replace('https://store.line.me/stickershop/product/', '').split('/')[1]
        elif url.startswith('https://line.me/S/sticker'):
            url_parsed = parse.urlparse(url)
            pack_id = url.replace('https://line.me/S/sticker/', '').split('/')[0]
            region = parse.parse_qs(url_parsed.query)['lang']
        elif url.startswith('https://store.line.me/emojishop/product/'):
            pack_id = url.replace('https://store.line.me/emojishop/product/', '').split('/')[0]
            region = url.replace('https://store.line.me/emojishop/product/', '').split('/')[1]
            is_emoji = True
        elif url.startswith('https://line.me/S/emoji'):
            url_parsed = parse.urlparse(url)
            pack_id = parse.parse_qs(url_parsed.query)['id']
            region = parse.parse_qs(url_parsed.query)['lang']
            is_emoji = True
        elif len(url) == 24 and all(c in string.hexdigits for c in url):
            pack_id = url
            is_emoji = True
        elif url.isnumeric():
            pack_id = url
        else:
            return False

        return pack_id, region, is_emoji
    
    @staticmethod
    def get_metadata_sticon(pack_id, region):
        pack_meta_r = requests.get(f"https://stickershop.line-scdn.net/sticonshop/v1/{pack_id}/sticon/iphone/meta.json")

        if pack_meta_r.status_code == 200:
            pack_meta = json.loads(pack_meta_r.text)
        else:
            return False
        
        if region == '':
            region = 'en'

        pack_store_page = requests.get(f"https://store.line.me/emojishop/product/{pack_id}/{region}")

        if pack_store_page.status_code != 200:
            return False

        pack_store_page_soup = BeautifulSoup(pack_store_page.text, 'html.parser')
        title = pack_store_page_soup.find(class_='mdCMN38Item01Txt').text
        author = pack_store_page_soup.find(class_='mdCMN38Item01Author').text

        files = pack_meta['orders']

        resource_type = pack_meta.get('sticonResourceType')
        has_sound = False

        return title, author, files, resource_type, has_sound
    
    @staticmethod
    def get_metadata_stickers(pack_id, region):
        pack_meta_r = requests.get(f"http://dl.stickershop.line.naver.jp/products/0/0/1/{pack_id}/android/productInfo.meta")

        if pack_meta_r.status_code == 200:
            pack_meta = json.loads(pack_meta_r.text)
        else:
            return False

        if region == '':
            if 'en' in pack_meta['title']:
                # Prefer en release
                region = 'en'
            else:
                # If no en release, use whatever comes first
                region = pack_meta['title'].keys()[0]
        
        if region == 'zh-Hant':
            region = 'zh_TW'

        title = pack_meta['title'].get('en')
        if title == None:
            title = pack_meta['title'][region]

        author = pack_meta['author'].get('en')
        if author == None:
            author = pack_meta['author'][region]

        files = pack_meta['stickers']
        
        resource_type = pack_meta.get('stickerResourceType')
        has_sound = pack_meta.get('hasSound')
        
        return title, author, files, resource_type, has_sound


class DownloadLine(DownloadBase):
    def __init__(self, *args, **kwargs):
        super(DownloadLine, self).__init__(*args, **kwargs)
        self.headers = {
                'referer': 'https://store.line.me',
                'user-agent': 'Android',
                'x-requested-with': 'XMLHttpRequest',
            }
        self.cookies = self.load_cookies()
        self.sticker_text_dict = {}

    def load_cookies(self):
        cookies = {}
        if self.opt_cred.get('line', {}).get('cookies'):
            try:
                for i in self.opt_cred['line']['cookies'].split(';'):
                    c_key, c_value = i.split('=')
                    cookies[c_key] = c_value
                if not GetLineAuth.validate_cookies(cookies):
                    self.cb_msg('Warning: Line cookies invalid, you will not be able to add text to "Custom stickers"')
                    cookies = {}
            except ValueError:
                self.cb_msg('Warning: Line cookies invalid, you will not be able to add text to "Custom stickers"')
        
        return cookies

    def get_pack_url(self):
        # Reference: https://sora.vercel.app/line-sticker-download
        if self.is_emoji:
            if self.resource_type == 'ANIMATION':
                pack_url = f'https://stickershop.line-scdn.net/sticonshop/v1/{self.pack_id}/sticon/iphone/package_animation.zip'
            else:
                pack_url = f'https://stickershop.line-scdn.net/sticonshop/v1/{self.pack_id}/sticon/iphone/package.zip'
        else:
            if self.resource_type in ('ANIMATION', 'ANIMATION_SOUND', 'POPUP') or self.has_sound == True:
                pack_url = f'https://stickershop.line-scdn.net/stickershop/v1/product/{self.pack_id}/iphone/stickerpack@2x.zip'
            elif self.resource_type == 'PER_STICKER_TEXT':
                pack_url = f'https://stickershop.line-scdn.net/stickershop/v1/product/{self.pack_id}/iphone/sticker_custom_plus_base@2x.zip'
            elif self.resource_type == 'NAME_TEXT':
                pack_url = f'https://stickershop.line-scdn.net/stickershop/v1/product/{self.pack_id}/iphone/sticker_name_base@2x.zip'
            else:
                pack_url = f'https://stickershop.line-scdn.net/stickershop/v1/product/{self.pack_id}/iphone/stickers@2x.zip'
        
        return pack_url
    
    def decompress_emoticon(self, zip_file):
        num = 0
        with zipfile.ZipFile(io.BytesIO(zip_file)) as zf:
            self.cb_msg(f'Unzipping...')

            self.cb_bar(set_progress_mode='determinate', steps=len(self.pack_files))
            for sticker in self.pack_files:
                if self.resource_type == 'ANIMATION':
                    f_path = str(sticker) + '_animation.png'
                else:
                    f_path = str(sticker) + '.png'
                data = zf.read(f_path)
                self.cb_msg(f'Read {f_path}')
                
                out_path = os.path.join(self.out_dir, str(num).zfill(3) + '.png')
                with open(out_path, 'wb') as f:
                    f.write(data)
                
                if self.cb_bar:
                    self.cb_bar(update_bar=True)

                num += 1

    def decompress_stickers(self, zip_file):
        num = 0
        with zipfile.ZipFile(io.BytesIO(zip_file)) as zf:
            self.cb_msg(f'Unzipping...')

            self.cb_bar(set_progress_mode='determinate', steps=len(self.pack_files))
            for sticker in self.pack_files:
                if self.resource_type in ('ANIMATION', 'ANIMATION_SOUND'):
                    f_path = 'animation@2x/' + str(sticker['id']) + '@2x.png'
                elif self.resource_type == 'POPUP':
                    f_path = 'popup/' + str(sticker['id']) + '.png'
                else:
                    f_path = str(sticker['id']) + '@2x.png'
                data = zf.read(f_path)
                self.cb_msg(f'Read {f_path}')
                
                out_path = os.path.join(self.out_dir, str(num).zfill(3) + '.png')
                with open(out_path, 'wb') as f:
                    f.write(data)
                
                if self.resource_type == 'PER_STICKER_TEXT':
                    self.sticker_text_dict[num] = {
                        'sticker_id': sticker['id'],
                        'sticker_text': sticker['customPlus']['defaultText']
                        }
                
                elif self.resource_type == 'NAME_TEXT':
                    self.sticker_text_dict[num] = {
                        'sticker_id': sticker['id'],
                        'sticker_text': ''
                        }
                
                if self.has_sound:
                    f_path = 'sound/' + str(sticker['id']) + '.m4a'
                    data = zf.read(f_path)
                    self.cb_msg(f'Read {f_path}')
                    
                    out_path = os.path.join(self.out_dir, str(num).zfill(3) + '.m4a')
                    with open(out_path, 'wb') as f:
                        f.write(data)
                
                if self.cb_bar:
                    self.cb_bar(update_bar=True)

                num += 1
            
    def edit_custom_sticker_text(self):
        line_sticker_text_path = os.path.join(self.out_dir, 'line-sticker-text.txt')

        if not os.path.isfile(line_sticker_text_path):
            with open(line_sticker_text_path, 'w+', encoding='utf-8') as f:
                json.dump(self.sticker_text_dict, f, indent=4, ensure_ascii=False)

            msg_block = 'The Line sticker pack you are downloading can have customized text.\n'
            msg_block += 'line-sticker-text.txt has been created in input directory.\n'
            msg_block += 'Please edit line-sticker-text.txt, then continue.'
            self.cb_msg_block(msg_block)

        with open(line_sticker_text_path , "r", encoding='utf-8') as f:
            self.sticker_text_dict = json.load(f)
    
    def get_custom_sticker_text_urls(self):
        custom_sticker_text_urls = []
        name_text_key_cache = {}

        for num, data in self.sticker_text_dict.items():
            out_path = os.path.join(self.out_dir, str(num).zfill(3))
            sticker_id = data['sticker_id']
            sticker_text = data['sticker_text']

            if self.resource_type == 'PER_STICKER_TEXT':
                custom_sticker_text_urls.append((f'https://store.line.me/overlay/sticker/{self.pack_id}/{sticker_id}/iPhone/sticker.png?text={parse.quote(sticker_text)}', out_path + '-text.png'))

            elif self.resource_type == 'NAME_TEXT' and sticker_text:
                name_text_key = name_text_key_cache.get(sticker_text, None)
                if not name_text_key:
                    name_text_key = self.get_name_text_key(sticker_text)
                if name_text_key:
                    name_text_key_cache[sticker_text] = name_text_key
                else:
                    continue

                custom_sticker_text_urls.append((f'https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/iPhone/overlay/name/{name_text_key}/sticker@2x.png', out_path + '-text.png'))
        
        return custom_sticker_text_urls

    def get_name_text_key(self, sticker_text):
        params = {
            'text': sticker_text
        }

        response = requests.get(
            f'https://store.line.me/api/custom-sticker/preview/{self.pack_id}/{self.region}',
            params=params,
            cookies=self.cookies,
            headers=self.headers,
        )

        response_dict = json.loads(response.text)

        if response_dict['errorMessage']:
            self.cb_msg(f"Failed to generate customized text {sticker_text} due to: {response_dict['errorMessage']}")
            return False

        name_text_key = response_dict['productPayload']['customOverlayUrl'].split('name/')[-1].split('/main.png')[0]

        return name_text_key

    def combine_custom_text(self):
        for i in sorted(os.listdir(self.out_dir)):
            if i.endswith('-text.png'):
                base_path = os.path.join(self.out_dir, i.replace('-text.png', '.png'))
                text_path = os.path.join(self.out_dir, i)

                base_img = Image.open(base_path).convert('RGBA')
                text_img = Image.open(text_path).convert('RGBA')

                Image.alpha_composite(base_img, text_img).save(base_path)

                os.remove(text_path)

                self.cb_msg(f"Combined {i.replace('-text.png', '.png')}")
        
    def download_stickers_line(self):
        url_data = MetadataLine.analyze_url(self.url)
        if url_data:
            self.pack_id, self.region, self.is_emoji = url_data
        else:
            self.cb_msg('Download failed: Unsupported URL format')
            return False

        if self.is_emoji:
            metadata = MetadataLine.get_metadata_sticon(self.pack_id, self.region)
        else:
            metadata = MetadataLine.get_metadata_stickers(self.pack_id, self.region)
        
        if metadata:
            self.title, self.author, self.pack_files, self.resource_type, self.has_sound = metadata
        else:
            self.cb_msg('Download failed: Failed to get metadata')
            return False

        MetadataHandler.set_metadata(self.out_dir, title=self.title, author=self.author)

        pack_url = self.get_pack_url()
        zip_file = self.download_file(pack_url)

        if zip_file:
            self.cb_msg(f'Downloaded {pack_url}')
        else:
            self.cb_msg(f'Cannot download {pack_url}')
            return False

        if self.is_emoji:
            self.decompress_emoticon(zip_file)
        else:
            self.decompress_stickers(zip_file)
                
        custom_sticker_text_urls = []
        if self.sticker_text_dict != {} and (self.resource_type == 'PER_STICKER_TEXT' or (self.resource_type == 'NAME_TEXT' and self.cookies != {})):
            self.edit_custom_sticker_text()
            custom_sticker_text_urls = self.get_custom_sticker_text_urls()
        elif self.resource_type == 'NAME_TEXT' and self.cookies == {}:
            self.cb_msg('Warning: Line "Custom stickers" is supplied as input')
            self.cb_msg('However, adding custom message requires Line cookies, and it is not supplied')
            self.cb_msg('Continuing without adding custom text to stickers')
        
        self.download_multiple_files(custom_sticker_text_urls, headers=self.headers)
        self.combine_custom_text()
        
        return True

    @staticmethod
    def start(url, out_dir, opt_cred=None, cb_msg=print, cb_msg_block=input, cb_bar=None):
        downloader = DownloadLine(url, out_dir, opt_cred, cb_msg, cb_msg_block, cb_bar)
        return downloader.download_stickers_line()