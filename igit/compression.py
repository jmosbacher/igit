
from os import stat
import zlib

COMPRESSORS = {}

class NoOpCompressor:
    @staticmethod
    def compress(data):
        return data

    @staticmethod
    def decompress(data):
        return data

COMPRESSORS["noop"] = NoOpCompressor
COMPRESSORS["zlib"] = zlib