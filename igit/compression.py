import zlib
from os import stat

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
