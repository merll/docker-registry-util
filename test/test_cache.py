import os
import unittest
from tempfile import mktemp

from test.data import *


class TestCache(unittest.TestCase):
    def test_refresh(self):
        cache = ImageDigestCache()
        for repo, tag_digests in TEST_REGISTRY_TAGS.items():
            for tag, digest in tag_digests.items():
                cache.add_image(repo, tag, digest)
        self.assertDictEqual(cache._digest_tags, TEST_REGISTRY_DIGESTS)

    def test_update_tag(self):
        cache = get_preset_cache()
        cache.update_image('a', 'latest', D_A2)
        self.assertSetEqual(cache.get_digests('a', ['latest']), {D_A2})
        self.assertIn(('a', 'latest'), cache.get_digest_tags(D_A2))
        self.assertNotIn(('a', 'latest'), cache.get_digest_tags(D_A1))

    def test_remove_independent_repo(self):
        cache = get_preset_cache()
        self.assertTrue(cache.remove_repository('a'))
        self.assertNotIn('a', cache)
        self.assertIsNone(cache.get_digest_tags(D_A1))
        self.assertIsNone(cache.get_digest_tags(D_A2))
        self.assertFalse(cache.remove_repository('a'))

    def test_remove_intersecting_repo(self):
        cache1 = get_preset_cache()
        self.assertTrue(cache1.remove_repository('b'))
        self.assertSetEqual(cache1.get_digest_tags(D_BC), {('c', '1.0.0'), ('c', 'latest')})
        self.assertSetEqual(cache1.get_digest_tags(D_C), TEST_REGISTRY_DIGESTS[D_C])
        self.assertFalse(cache1.remove_repository('b'))
        cache2 = get_preset_cache()
        self.assertTrue(cache2.remove_repository('c'))
        self.assertSetEqual(cache2.get_digest_tags(D_BC), {('b', '1.0.0'), ('b', 'latest')})
        self.assertIsNone(cache2.get_digest_tags(D_C))
        self.assertFalse(cache2.remove_repository('c'))

    def test_remove_independent_tag(self):
        cache = get_preset_cache()
        self.assertTrue(cache.remove_tag('a', 'latest'))
        self.assertIn('a', cache)
        self.assertFalse(cache.remove_tag('a', 'latest'))
        self.assertSetEqual(set(cache.get_tag_digests('a')), {'1.1.0', '1.2.0', 'extra', 'testing'})
        self.assertSetEqual(cache.get_digest_tags(D_A1), {('a', '1.1.0')})
        self.assertTrue(cache.remove_tag('a', '1.1.0'))
        self.assertIsNone(cache.get_digest_tags(D_A1))
        self.assertSetEqual(cache.get_digest_tags(D_A2), TEST_REGISTRY_DIGESTS[D_A2])
        self.assertTrue(cache.remove_tag('a', '1.2.0'))
        self.assertTrue(cache.remove_tag('a', 'extra'))
        self.assertTrue(cache.remove_tag('a', 'testing'))
        self.assertIsNone(cache.get_digest_tags(D_A2))

    def test_remove_intersecting_tag(self):
        cache = get_preset_cache()
        self.assertTrue(cache.remove_tag('b', '1.0.0'))
        self.assertSetEqual(cache.get_digest_tags(D_BC), {('b', 'latest'), ('c', '1.0.0'), ('c', 'latest')})
        self.assertTrue(cache.remove_tag('b', 'latest'))
        self.assertSetEqual(cache.get_digest_tags(D_BC), {('c', '1.0.0'), ('c', 'latest')})
        self.assertTrue(cache.remove_tag('c', '1.0.0'))
        self.assertSetEqual(cache.get_digest_tags(D_BC), {('c', 'latest')})
        self.assertTrue(cache.remove_tag('c', 'latest'))
        self.assertIsNone(cache.get_digest_tags(D_BC))
        self.assertSetEqual(cache.get_digests('c'), {D_C})

    def test_remove_digest(self):
        cache = get_preset_cache()
        cache.remove_digests([D_BC])
        self.assertNotIn('b', cache)
        self.assertDictEqual(cache.get_tag_digests('c'), {'1.1.0': D_C, 'testing': D_C})

    def test_dumps_loads(self):
        cache = get_preset_cache()
        reloaded = cache.loads(cache.dumps())
        self.assertDictEqual(cache._tag_digests, reloaded._tag_digests)

    def test_dump_load(self):
        filename = mktemp()
        cache = get_preset_cache()
        with open(filename, 'w') as f:
            cache.dump(f)
        try:
            with open(filename, 'r') as f:
                reloaded = cache.load(f)
        finally:
            os.unlink(filename)
        self.assertDictEqual(cache._tag_digests, reloaded._tag_digests)
