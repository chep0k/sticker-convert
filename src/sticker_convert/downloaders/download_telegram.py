#!/usr/bin/env python3
import os

from .download_base import DownloadBase
from ..utils.metadata_handler import MetadataHandler

import anyio
from telegram import Bot

class DownloadTelegram(DownloadBase):
    def __init__(self, *args, **kwargs):
        super(DownloadTelegram, self).__init__(*args, **kwargs)
    
    def download_stickers_telegram(self):
        self.token = self.opt_cred.get('telegram', {}).get('token')
        if self.token == None:
            self.cb_msg('Download failed: Token required for downloading from telegram')
            return False
    
        if not ('telegram.me' in self.url or 't.me' in self.url):
            self.cb_msg('Download failed: Unrecognized URL format')
            return False

        self.title = ""
        try:
            self.title = self.url.split("/addstickers/")[1]
        except IndexError:
            self.title = self.url.split("eu/stickers/")[1]
        
        anyio.run(self.save_stickers)
        return True

    async def save_stickers(self):
        bot = Bot(self.token)
        async with bot:
            sticker_set = await bot.get_sticker_set(self.title, read_timeout=30, write_timeout=30, connect_timeout=30, pool_timeout=30)

            if self.cb_bar:
                self.cb_bar(set_progress_mode='determinate', steps=len(sticker_set.stickers))

            emoji_dict = {}
            num = 0
            for i in sticker_set.stickers:
                sticker = await i.get_file(read_timeout=30, write_timeout=30, connect_timeout=30, pool_timeout=30)
                ext = os.path.splitext(sticker.file_path)[-1]
                f_id = str(num).zfill(3)
                f_name = f_id + ext
                f_path = os.path.join(self.out_dir, f_name)
                await sticker.download_to_drive(custom_path=f_path, read_timeout=30, write_timeout=30, connect_timeout=30, pool_timeout=30)
                emoji_dict[f_id] = i.emoji
                self.cb_msg(f'Downloaded {f_name}')
                if self.cb_bar:
                    self.cb_bar(update_bar=True)
                num += 1
            
            if sticker_set.thumbnail:
                cover = await sticker_set.thumbnail.get_file(read_timeout=30, write_timeout=30, connect_timeout=30, pool_timeout=30)
                cover_ext = os.path.splitext(cover.file_path)[-1]
                cover_name = 'cover' + cover_ext
                cover_path = os.path.join(self.out_dir, cover_name)
                await cover.download_to_drive(custom_path=cover_path, read_timeout=30, write_timeout=30, connect_timeout=30, pool_timeout=30)
                self.cb_msg(f'Downloaded {cover_name}')

        MetadataHandler.set_metadata(self.out_dir, title=self.title, emoji_dict=emoji_dict)

    @staticmethod
    def start(url, out_dir, opt_cred=None, cb_msg=print, cb_msg_block=input, cb_bar=None):
        downloader = DownloadTelegram(url, out_dir, opt_cred, cb_msg, cb_msg_block, cb_bar)
        return downloader.download_stickers_telegram()