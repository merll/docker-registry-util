
from copy import deepcopy

from docker_registry_util.digest import ContentDigest
from docker_registry_util.cache import ImageDigestCache


D_A1 = ContentDigest(b'445f4131')
D_A2 = ContentDigest(b'445f4132')
D_BC = ContentDigest(b'445f4243')
D_C = ContentDigest(b'445f4320')
TEST_REGISTRY_TAGS = {
    'a': {
        '1.1.0': D_A1,
        '1.2.0': D_A2,
        'latest': D_A1,
        'testing': D_A2,
        'extra': D_A2,
    },
    'b': {
        '1.0.0': D_BC,
        'latest': D_BC,
    },
    'c': {
        '1.0.0': D_BC,
        '1.1.0': D_C,
        'latest': D_BC,
        'testing': D_C,
    },
}
TEST_REGISTRY_DIGESTS = {
    D_A1: {
        ('a', '1.1.0'),
        ('a', 'latest'),
    },
    D_A2: {
        ('a', '1.2.0'),
        ('a', 'testing'),
        ('a', 'extra'),
    },
    D_BC: {
        ('b', '1.0.0'),
        ('b', 'latest'),
        ('c', '1.0.0'),
        ('c', 'latest'),
    },
    D_C: {
        ('c', '1.1.0'),
        ('c', 'testing'),
    },
}


def get_preset_cache():
    cache = ImageDigestCache()
    cache._digest_tags = deepcopy(TEST_REGISTRY_DIGESTS)
    cache._tag_digests = deepcopy(TEST_REGISTRY_TAGS)
    return cache
