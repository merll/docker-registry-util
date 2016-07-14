import re
import unittest

from docker_registry_util.query import DockerRegistryQuery, IntersectionError

from test.data import *

_ALL_TAGS = re.compile('.*')


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.query = DockerRegistryQuery('localhost')
        self.query._cache = get_preset_cache()
        self.query._initialized = True

    def assertItemsEqual(self, list1, list2, msg=None):
        return self.assertListEqual(sorted(list1), sorted(list2), msg=msg)

    def test_independent_repo_selection(self):
        q = self.query.select_repositories
        self.assertItemsEqual(q('a'), [('a', D_A1), ('a', D_A2)])
        self.assertItemsEqual(q(['a']), [('a', D_A1), ('a', D_A2)])

    def test_intersecting_repo_selection(self):
        q = self.query.select_repositories
        self.assertItemsEqual(q(['b', 'c']), [('b', D_BC), ('c', D_C)])
        self.assertItemsEqual(q('b', raise_intersecting_repo=False), [])
        self.assertItemsEqual(q('c', raise_intersecting_repo=False), [('c', D_C)])
        with self.assertRaises(IntersectionError) as ie1:
            q('b')
        ce1 = ie1.exception
        self.assertSetEqual(ce1.conflicting_items, {'c'})
        self.assertEqual(ce1.digest, D_BC)
        with self.assertRaises(IntersectionError) as ie2:
            q('c')
        ce2 = ie2.exception
        self.assertSetEqual(ce2.conflicting_items, {'b'})
        self.assertEqual(ce2.digest, D_BC)

    def test_independent_tag_selection(self):
        q = self.query.select_tags
        self.assertItemsEqual(q('a', ('<1.2.0', 'latest')), [('a', D_A1)])
        self.assertItemsEqual(q('a', (_ALL_TAGS, )), [('a', D_A1), ('a', D_A2)])
        self.assertItemsEqual(q('c', ('>=1.1.0', 'testing')), [('c', D_C)])

    def test_intersecting_tag_selection(self):
        q = self.query.select_tags
        self.assertItemsEqual(q('a', ('<=1.2.0', 'latest')), [('a', D_A1)])
        self.assertItemsEqual(q(['b', 'c'], _ALL_TAGS), [('b', D_BC), ('c', D_C)])
        self.assertItemsEqual(q(['b', 'c'], ('1.0.0', 'latest')), [('b', D_BC)])
        self.assertItemsEqual(q('c', _ALL_TAGS, raise_intersecting_repo=False), [('c', D_C)])
        with self.assertRaises(IntersectionError) as ie1:
            q('b', _ALL_TAGS)
        ce1 = ie1.exception
        self.assertEqual(ce1.conflicting_items, 'c')
        self.assertEqual(ce1.digest, D_BC)
        with self.assertRaises(IntersectionError) as ie2:
            q('c', _ALL_TAGS)
        ce2 = ie2.exception
        self.assertEqual(ce2.conflicting_items, 'b')
        self.assertEqual(ce2.digest, D_BC)
        with self.assertRaises(IntersectionError) as ie3:
            q(['b', 'c'], '==1.0.0', raise_intersecting_tag=True)
        ce3 = ie3.exception
        self.assertSetEqual(ce3.conflicting_items, {'latest'})
        self.assertEqual(ce3.digest, D_BC)

    def test_tag_selection_with_exclusion(self):
        q = self.query.select_tags
        self.assertItemsEqual(q('a', _ALL_TAGS, 'latest'), [('a', D_A2)])
        self.assertItemsEqual(q(['b', 'c'], _ALL_TAGS, ['testing']), [('b', D_BC)])
