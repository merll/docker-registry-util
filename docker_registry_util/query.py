import logging
from itertools import zip_longest, groupby
import re
from distutils.version import LooseVersion
from requests.exceptions import HTTPError
from .digest import ContentDigest
from .cache import ImageDigestCache


def _str_or_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


VERSION_REGEX = re.compile('((?:[<>]=?)|(?:==))(.+)')
REGEX_TYPE = type(VERSION_REGEX)

log = logging.getLogger(__name__)


def _get_tag_func(value):
    if callable(value):
        return value
    elif isinstance(value, str):
        vm = VERSION_REGEX.match(value)
        if vm:
            version_comparison = vm.group(1)
            version = LooseVersion(vm.group(2))
            if version_comparison == '==':
                return version.__eq__
            if version_comparison == '>':
                return version.__lt__
            elif version_comparison == '<':
                return version.__gt__
            elif version_comparison == '>=':
                return version.__le__
            elif version_comparison == '<=':
                return version.__ge__
            # Should be excluded by regular expression.
            raise ValueError("Undefined version comparison.", version_comparison)
    elif isinstance(value, REGEX_TYPE):
        return value.match
    # Fall back to equality comparison.
    return value.__eq__


def _generate_tag_funcs(values):
    if not values:
        return []
    if callable(values) or isinstance(values, (str, int, REGEX_TYPE)):
        return [_get_tag_func(values)]
    return [_get_tag_func(value) for value in values]


def _any_tag_matches(func_list, tag):
    for func in func_list:
        try:
            if func(tag):
                return True
        except TypeError:
            pass
    return False


class IntersectionError(Exception):
    def __init__(self, message, excess_items, digest, *args, **kwargs):
        super(IntersectionError, self).__init__(message, excess_items, digest, *args, **kwargs)

    @property
    def conflicting_items(self):
        return self.args[1]

    @property
    def digest(self):
        return self.args[2]


class SortingVersion(LooseVersion):
    """
    Like LooseVersion, but provides a stable sort order even if different version schemes are used, e.g. numbers and
    strings occur in even positions. This does not mean that the outcome will be semantically correct. Strings are
    considered 'higher' than numbers.
    """
    def _cmp(self, other):
        if self.version == other.version:
            return 0
        try:
            if self.version < other.version:
                return -1
            if self.version > other.version:
                return 1
        except TypeError:
            for a, b in zip_longest(self.version, other.version):
                if a == b:
                    continue
                if type(a) == type(b):
                    if a < b:
                        return -1
                    if a > b:
                        return 1
                else:
                    if isinstance(a, str):
                        return 1
                    if isinstance(b, str):
                        return -1
                    if a is None:
                        return -1
                    if b is None:
                        return 1


class DockerRegistryQuery(object):
    def __init__(self, client):
        self._client = client
        self._cache = ImageDigestCache()
        self._initialized = False

    @property
    def client(self):
        return self._client

    def refresh(self):
        log.info("Initializing cache.")
        if self._initialized:
            log.info("Clearing.")
            self._cache.reset()
        repos = self._client.get_catalog().json()['repositories']
        log.info("Found %s repositories.", len(repos))
        for repo in repos:
            log.info("Checking repository '%s'.", repo)
            tags = self._client.get_tags(repo).json()['tags']
            if not tags:
                log.info("No tags found for '%s', skipping.", repo)
                continue
            for tag in tags:
                try:
                    manifest = self._client.head_manifest(repo, tag)
                except HTTPError:
                    log.warning("Getting http error during request manifest: (repo=%s, tag=%s), skipping.", repo, tag)
                    continue
                digest = manifest.headers['Docker-Content-Digest']
                log.debug("Registering digest for %s:%s - %s.", repo, tag, digest)
                self._cache.add_image(repo, tag, ContentDigest.from_sha256(digest))
        log.info("Cache init completed.")
        self._initialized = True

    def update(self, repos, tags):
        log.info("Updating cache.")
        tag_funcs = _generate_tag_funcs(tags)
        for repo in _str_or_list(repos):
            log.info("Checking repository '%s'.", repo)
            available_tags = self._client.get_tags(repo).json()['tags']
            if not available_tags:
                log.info("No tags found for '%s', skipping.", repo)
                continue
            for tag in available_tags:
                log.info("Checking filter match for %s:%s.", repo, tag)
                if _any_tag_matches(tag_funcs, tag):
                    try:
                        manifest = self._client.head_manifest(repo, tag)
                    except HTTPError:
                        log.warning("Getting http error during request manifest: (repo=%s, tag=%s), skipping.", repo, tag)
                        continue
                    digest = manifest.headers['Docker-Content-Digest']
                    log.debug("Registering digest for %s:%s - %s.", repo, tag, digest)
                    self._cache.update_image(repo, tag, ContentDigest.from_sha256(digest))

    def select_repositories(self, names, raise_intersecting_repo=True):
        """
        Selects all digests used by the given repositories, i.e. any of its tags.

        :param names: Repository name or a list of multiple repository names.
        :type names: str | list[str]
        :param raise_intersecting_repo: Raises an exception if any of the selected digests is used by a repository that
         is not specified in ``names``. Default is ``True``. If set to ``False``, items with such intersecting
         references are simply ignored.
        :type raise_intersecting_repo: bool
        :return: A list of tuples, each with repository name and digest. If a digest is referred to by multiple
         repositories, only the first one (in the order of ``names``) is listed.
        :rtype: list[(str, docker_registry_util.digest.ContentDigest)]
        """
        if not self._initialized:
            self.refresh()

        def _complete_match(d):
            repos = self._cache.get_digest_repos(d)
            log.debug("Found repositories %s for digest %s.", repos, d)
            external_names = repos.difference(name_list)
            log.debug("Outside of query: %s", external_names)
            if not external_names:
                return True
            elif raise_intersecting_repo:
                raise IntersectionError("Selected names intersect with at least one other repository that is not "
                                        "included in the selection.", external_names, d)
            return False

        name_list = _str_or_list(names)
        tested_digests = set()
        return [(name, digest)
                for name in name_list
                for digest in self._cache.get_digests(name)
                if not (digest in tested_digests or tested_digests.add(digest)) and _complete_match(digest)]

    def select_tags(self, repos, tags, exclude_tags=None, match_all_tags=True,
                    raise_intersecting_repo=True, raise_intersecting_tag=False):
        """
        Selects all digests used by the given repositories and their tags matching the given selectors.

        :param repos: Repository name or a list of multiple repository names.
        :type repos: str | list[str]
        :param tags: Single tag name or list of tag names for exact match. Or version selectors, e.g. ``>=1.0.0`` for
         selecting versioned tags. Or compiled regular expressions for performing RegEx matches.
        :param exclude_tags: Optionally a tag or multiple tags to exclude. Supports the same variations as ``tags``.
         This means that if any of the digests selected from ``tags`` also has any other tag matching an item
         in ``exclude_tags``, it is ignored.
        :param match_all_tags: If set (which is the default), each found digests is reverse-matched against the
         original selection of tags. If there are any tags outside of the selection, the digest is ignored. This can
         be deactivated setting this to ``False``. When used during tag deletion, this may however lead to affecting
         other tags being deleted unexpectedly. Note that repositories are still checked against the original selection.
        :param raise_intersecting_repo: Raises an exception if any of the selected digests is used by a repository that
         is not specified in ``names``. Default is ``True``. If set to ``False``, items with such intersecting
         references are simply ignored.
        :type raise_intersecting_repo: bool
        :param raise_intersecting_tag: Raises an exception if any of the selected digests is used by a tag that is not
         specified in ``tags``. When left at the default, which is ``False``, items with such intersecting
         references are simply ignored. Items excluded with ``exclude_tags`` do not trigger exceptions either way.
        :type raise_intersecting_tag: bool
        :return: A list of tuples, each with repository name and digest. If a digest is referred to by multiple
         repositories, only the first one (in the order of ``repos``) is listed.
        :rtype: list[(str, docker_registry_util.digest.ContentDigest)]
        """
        def _complete_match(d):
            for repo_name, repo_tags in self._cache.get_grouped_tags(d):
                tag_set = tag_sets.get(repo_name)
                if tag_set:
                    current_tags = {i[1] for i in repo_tags}
                    if match_all_tags:
                        external_tags = current_tags - tag_set
                        if not external_tags:
                            if any((_any_tag_matches(excluded_filter, t) for t in current_tags)):
                                return False
                        elif raise_intersecting_tag:
                            raise IntersectionError(
                                "Selected tags intersect with other tags of the repositories, which were not "
                                "included in the selection.", external_tags, d)
                        else:
                            return False
                    else:
                        return not any((_any_tag_matches(excluded_filter, t) for t in current_tags))
                elif raise_intersecting_repo:
                    raise IntersectionError(
                        "Selected repositories and tags intersect with at least one other repository "
                        "or tags within, that is not included.", repo_name, d)
                else:
                    return False
            return True

        def _group_digest(iterable):
            result = []
            key = lambda x: (x[0], x[2])
            sorted_iterable = sorted(iterable, key=key)
            for k, g in groupby(sorted_iterable, key=key):
                # (repo, digest, [tags])
                r_item = (k[0], k[1], [t for _, t, _ in list(g)])
                result.append(r_item)
            return result

        if not self._initialized:
            self.refresh()
        included_filter = _generate_tag_funcs(tags)
        excluded_filter = _generate_tag_funcs(exclude_tags)
        tag_sets = dict()
        test_digests = []
        for repo in _str_or_list(repos):
            tag_digests = self._cache.get_tag_digests(repo)
            if not tag_digests:
                continue
            partial_matches = [(tag, digest)
                               for tag, digest in tag_digests.items()
                               if _any_tag_matches(included_filter, tag)]
            if partial_matches:
                p_tags, p_digests = zip(*partial_matches)
                tag_sets[repo] = set(p_tags)
                test_digests.extend([(repo, tag, digest) for tag, digest in partial_matches])

        grouped_digest = _group_digest(test_digests)

        tested_digests = set()
        return [(name, digest, tags)
                for name, digest, tags in grouped_digest
                if not (digest in tested_digests or tested_digests.add(digest)) and _complete_match(digest)]

    def get_repo_names(self):
        """
        Returns a sorted list of available repository names.

        :return: Repository name list.
        :rtype: list[str]
        """
        if not self._initialized:
            self.refresh()
        return self._cache.get_repo_names()

    def get_tag_names(self, repos=None, reverse_sort=False):
        """
        Returns a sorted list of available tags, optionally filtered by a set of repository names.

        :param repos: Optional repository name or list names to limit the output.
        :type repos: str | list[str] | tuple[str] | NoneType
        :param reverse_sort: Revert the sort order.
        :type reverse_sort: bool
        :return: List with tuples of repositories and tags.
        :rtype: list[(str, str)]
        """
        if not self._initialized:
            self.refresh()
        if repos:
            repo_list = _str_or_list(repos)
        else:
            repo_list = None
        return self._cache.get_tag_names(repo_list, SortingVersion, reverse_sort)

    @property
    def cache(self):
        """
        Returns the cache instance for queries.

        :rtype: Lookup cache for repositories, tags, and digests.
        :rtype: docker_registry_util.cache.ImageDigestCache
        """
        return self._cache

    @property
    def client(self):
        """
        Returns the client instance used for cache updates.

        :return: Docker Registry API client.
        :rtype: docker_registry_util.client.DockerRegistryClient
        """
        return self._client

    def load(self, file):
        """
        Loads a previous state of a cache from a JSON file or file-like object.

        :param file: JSON file.
        """
        self._cache = ImageDigestCache.load(file)
        self._initialized = True

    def loads(self, s):
        """
        Loads a previous state of a cache from a JSON string.

        :param s: JSON-formatted string.
        :type s: str
        """
        self._cache = ImageDigestCache.loads(s)
        self._initialized = True

    def dump(self, file):
        """
        Saves the current state of the image cache to a file (or file-like object) in JSON format.

        :param file: Output file.
        """
        self._cache.dump(file)

    def dumps(self):
        """
        Returns the current state of the image cache as a string in JSON format.

        :return: str
        """
        return self._cache.dumps()
