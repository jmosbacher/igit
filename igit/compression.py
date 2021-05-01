
import zlib

COMPRESSORS = {}

class NoOpCompressor:

    def compress(self, data):
        return data

    def decompress(self, data):
        return data

COMPRESSORS["noop"] = NoOpCompressor
COMPRESSORS["zlib"] = zlib 