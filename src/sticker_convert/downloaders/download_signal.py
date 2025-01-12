#!/usr/bin/env python3
import os
import anyio
from signalstickers_client import StickersClient

from .download_base import DownloadBase
from ..utils.metadata_handler import MetadataHandler
from ..utils.codec_info import CodecInfo

class DownloadSignal(DownloadBase):
    def __init__(self, *args, **kwargs):
        super(DownloadSignal, self).__init__(*args, **kwargs)
        
    @staticmethod
    async def get_pack(pack_id, pack_key):
        async with StickersClient() as client:
            pack = await client.get_pack(pack_id, pack_key)
        
        return pack

    def save_stickers(self, pack):
        if self.cb_bar:
            self.cb_bar(set_progress_mode='determinate', steps=len(pack.stickers))

        emoji_dict = {}
        for sticker in pack.stickers:
            f_id = str(sticker.id).zfill(3)
            f_path = os.path.join(self.out_dir, f'{f_id}')
            with open(f_path, "wb",) as f:
                f.write(sticker.image_data)

            emoji_dict[f_id] = sticker.emoji

            codec = CodecInfo.get_file_codec(f_path)
            if 'apng' in codec:
                f_path_new = f_path + '.apng'
            elif 'png' in codec:
                f_path_new = f_path + '.png'
            elif 'webp' in codec:
                f_path_new = f_path + '.webp'
            else:
                self.cb_msg(f'Unknown codec {codec}, defaulting to webp')
                codec = 'webp'
                f_path_new = f_path + '.webp'
            
            os.rename(f_path, f_path_new)
            
            self.cb_msg(f'Downloaded {f_id}.{codec}')
            if self.cb_bar:
                self.cb_bar(update_bar=True)
        
        MetadataHandler.set_metadata(self.out_dir, title=pack.title, author=pack.author, emoji_dict=emoji_dict)

    def download_stickers_signal(self):
        if 'signal.art' not in self.url:
            self.cb_msg('Download failed: Unrecognized URL format')
            return False

        pack_id = self.url.split('#pack_id=')[1].split('&pack_key=')[0]
        pack_key = self.url.split('&pack_key=')[1]

        pack = anyio.run(DownloadSignal.get_pack, pack_id, pack_key)
        self.save_stickers(pack)

        return True
    
    @staticmethod
    def start(url, out_dir, opt_cred=None, cb_msg=print, cb_msg_block=input, cb_bar=None):
        downloader = DownloadSignal(url, out_dir, opt_cred, cb_msg, cb_msg_block, cb_bar)
        return downloader.download_stickers_signal()