import codecs

codec_info = codecs.lookup('hex')
_encode_hex = codec_info.encode
_decode_hex = codec_info.decode


def _encode_hex_str(value):
    return _encode_hex(value)[0].decode()


class ContentDigest(bytes):
    @classmethod
    def from_sha256(cls, value):
        if value[:7] != 'sha256:':
            raise ValueError("Found unsupported digest type.", value)
        return cls(_decode_hex(value[7:])[0])

    def as_sha256(self):
        return 'sha256:{0}'.format(_encode_hex_str(self))

    __str__ = as_sha256

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self)
