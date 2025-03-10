import os
import binascii
import base64
import struct
import json
import logging
from Crypto.Cipher import AES

# 默认参数
NCM_HEADER = b'CTENFDAM\x01p'
CORE_KEY = binascii.a2b_hex("687A4852416D736F356B496E62617857")
META_KEY = binascii.a2b_hex("2331346C6A6B5F215C5D2630553C2728")
META_STRING_PREFIX = "music:"
META_DATA_BYTES_PREFIX = b"163 key(Don't modify):"

KEY_PREFIX = "neteasecloudmusic"
DEFAULT_KEY = KEY_PREFIX + "1145141919810E7fT49x7dof9OKCgg9cdvhEuezy3iZCL1nFvBFd1T4uSktAJKmwZXsijPbijliionVUXXg9plTbXEclAE9Lb"


class NCMEncryptor:
    def __init__(self, key_data=None, debug=False):
        """
        初始化NCM加密器

        :param key_data: 自定义的密钥数据（字符串），若为 None 则使用默认密钥
        :param debug: 是否开启调试日志输出
        """
        self.logger = self._init_logger(debug)
        if key_data is None:
            self.key_data_str = DEFAULT_KEY
            self.logger.info("使用默认密钥")
        else:
            self.key_data_str = KEY_PREFIX + key_data
            self.logger.info("使用自定义密钥")

        # 核心密钥和元数据密钥（固定值）
        self.core_key = CORE_KEY
        self.meta_key = META_KEY

        # NCM文件头
        self.ncm_header = NCM_HEADER

    def _init_logger(self, debug):
        """初始化日志记录器"""
        logger = logging.getLogger("NCMEncryptor")
        logger.setLevel(logging.DEBUG if debug else logging.INFO)

        # 避免重复添加处理器
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)

        return logger

    @staticmethod
    def _unpad(s: bytes) -> bytes:
        """去除PKCS#7填充"""
        pad_len = s[-1] if isinstance(s[-1], int) else ord(s[-1])
        return s[:-pad_len]

    @staticmethod
    def _pad(data: bytes) -> bytes:
        """添加PKCS#7填充"""
        block_size = 16
        length = block_size - (len(data) % block_size)
        return data + bytes([length]) * length

    @staticmethod
    def _crc32(data: bytes) -> bytes:
        """计算CRC32校验码并转为字节"""
        crc = binascii.crc32(data)
        return struct.pack('<I', crc)

    def _encrypt_key_data(self) -> tuple:
        """
        加密密钥数据

        :return: 元组(加密后的数据, 加密数据长度的打包表示)
        """
        self.logger.debug("开始处理key_data...")

        # 对密钥进行填充并加密
        key_data_bytes = self._pad(self.key_data_str.encode())
        cryptor = AES.new(self.core_key, AES.MODE_ECB)
        key_data_encrypted = cryptor.encrypt(key_data_bytes)

        # 对加密后的数据进行异或运算
        key_data_encrypted = bytearray(key_data_encrypted)
        for i in range(len(key_data_encrypted)):
            key_data_encrypted[i] ^= 0x64

        key_data_encrypted = bytes(key_data_encrypted)
        key_length = len(key_data_encrypted)
        key_length_packed = struct.pack('<I', key_length)

        self.logger.debug("key_data处理完成")
        return key_data_encrypted, key_length_packed

    def _generate_key_box(self, key_data_encrypted: bytes) -> bytearray:
        """
        生成用于加密音频数据的密钥盒

        :param key_data_encrypted: 加密后的密钥数据
        :return: 生成的密钥盒
        """
        self.logger.debug("开始生成key_box...")

        # 对加密后的密钥数据进行解密
        key_data_array = bytearray(key_data_encrypted)
        for i in range(len(key_data_array)):
            key_data_array[i] ^= 0x64

        key_data_decrypted = AES.new(self.core_key, AES.MODE_ECB).decrypt(bytes(key_data_array))
        key_data_decrypted = self._unpad(key_data_decrypted)[17:]

        # 生成密钥盒
        key_length = len(key_data_decrypted)
        key_data_decrypted = bytearray(key_data_decrypted)
        key_box = bytearray(range(256))

        c = 0
        last_byte = 0
        key_offset = 0

        for i in range(256):
            swap = key_box[i]
            c = (swap + last_byte + key_data_decrypted[key_offset]) & 0xff
            key_offset += 1
            if key_offset >= key_length:
                key_offset = 0
            key_box[i] = key_box[c]
            key_box[c] = swap
            last_byte = c

        self.logger.debug("key_box生成完成")
        return key_box

    def _process_metadata(self, meta_data: dict) -> tuple:
        """
        处理并加密元数据

        :param meta_data: 元数据字典
        :return: 元组(加密后的元数据, 元数据长度的打包表示)
        """
        self.logger.debug("开始处理meta_data...")

        # 将元数据转为字符串并加前缀
        meta_data_str = json.dumps(meta_data, separators=(',', ':'), ensure_ascii=False)
        meta_data_str = META_STRING_PREFIX + meta_data_str

        # 对元数据进行填充并加密
        meta_data_bytes = self._pad(meta_data_str.encode())
        cryptor_meta = AES.new(self.meta_key, AES.MODE_ECB)
        meta_data_bytes_enc = cryptor_meta.encrypt(meta_data_bytes)

        # Base64编码并添加标识
        meta_data_bytes_enc = base64.b64encode(meta_data_bytes_enc)
        meta_data_bytes_enc = META_DATA_BYTES_PREFIX + meta_data_bytes_enc

        # 对编码后的数据进行异或运算
        meta_data_array = bytearray(meta_data_bytes_enc)
        for i in range(len(meta_data_array)):
            meta_data_array[i] ^= 0x63

        meta_data_xor = bytes(meta_data_array)
        meta_length = len(meta_data_xor)
        meta_length_packed = struct.pack('<I', meta_length)

        self.logger.debug("meta_data处理完成")
        return meta_data_xor, meta_length_packed

    def _process_cover_image(self, img_path: str) -> tuple:
        """
        处理封面图片

        :param img_path: 图片文件路径
        :return: 元组(图片数据, 图片大小的打包表示)
        """
        self.logger.debug("开始处理封面图片...")

        with open(img_path, 'rb') as img_file:
            pic_data = img_file.read()

        pic_size = len(pic_data)
        pic_size_packed = struct.pack('<I', pic_size)

        self.logger.debug("封面图片处理完成")
        return pic_data, pic_size_packed

    def _encrypt_audio_data(self, file_path: str, key_box: bytearray, fo) -> None:
        """
        加密音频数据并写入输出文件

        :param file_path: 音频文件路径
        :param key_box: 密钥盒
        :param fo: 输出文件对象
        """
        self.logger.info("开始加密音频文件...")

        with open(file_path, 'rb') as f:
            chunk_size = 0x8000  # 32KB块

            while True:
                chunk = bytearray(f.read(chunk_size))
                chunk_length = len(chunk)

                if not chunk:
                    break

                # 使用密钥盒加密数据块
                for i in range(1, chunk_length + 1):
                    j = i & 0xff
                    chunk[i - 1] ^= key_box[(key_box[j] + key_box[(key_box[j] + j) & 0xff]) & 0xff]

                fo.write(chunk)

        self.logger.info("音频加密成功")

    def encrypt(self, file_path: str, img_path: str, meta_data: dict, output_file: str = 'output.ncm') -> None:
        """
        对音频文件进行加密并生成NCM文件

        :param file_path: 输入音频文件路径
        :param img_path: 封面图片文件路径
        :param meta_data: 元数据字典
        :param output_file: 输出文件路径
        :raises FileNotFoundError: 输入文件不存在时抛出异常
        """
        # 验证输入文件是否存在
        if not os.path.exists(file_path):
            self.logger.error(f"音频文件不存在: {file_path}")
            raise FileNotFoundError(f"音频文件不存在: {file_path}")

        if not os.path.exists(img_path):
            self.logger.error(f"封面图片文件不存在: {img_path}")
            raise FileNotFoundError(f"封面图片文件不存在: {img_path}")

        self.logger.info(f"开始加密: {file_path} -> {output_file}")

        try:
            with open(output_file, "wb") as fo:
                # 写入NCM文件头
                fo.write(self.ncm_header)
                crc_data = self.ncm_header

                # 1. 处理并写入密钥数据
                key_data_encrypted, key_length_packed = self._encrypt_key_data()
                fo.write(key_length_packed)
                fo.write(key_data_encrypted)
                crc_data += key_length_packed + key_data_encrypted

                # 2. 生成密钥盒用于加密音频数据
                key_box = self._generate_key_box(key_data_encrypted)

                # 3. 处理并写入元数据
                meta_data_encrypted, meta_length_packed = self._process_metadata(meta_data)
                fo.write(meta_length_packed)
                fo.write(meta_data_encrypted)
                crc_data += meta_length_packed + meta_data_encrypted

                # 4. 处理封面图片
                pic_data, pic_size_packed = self._process_cover_image(img_path)

                # 5. 写入CRC32校验和其他必要数据
                fo.write(self._crc32(crc_data))
                fo.write(b'\x01')  # 标记位
                fo.write(pic_size_packed)  # 图片大小（写两次）
                fo.write(pic_size_packed)
                fo.write(pic_data)  # 写入图片数据

                # 6. 加密并写入音频数据
                self._encrypt_audio_data(file_path, key_box, fo)

            self.logger.info(f"加密完成: {output_file}")

        except Exception as e:
            self.logger.error(f"加密过程中出现错误: {e}")
            raise
