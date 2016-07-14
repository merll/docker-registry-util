import json
from collections import defaultdict
import itertools
from operator import itemgetter

from .digest import ContentDigest

DUMP_KWARGS = {'ensure_ascii': False, 'check_circular': False}

_get_first = itemgetter(0)


class ImageDigestCache(object):
    """
    Cache for image data, speeding up lookups on the registry and storing a two-way relation between repository tags
    and image digests.
    """
    def __init__(self):
        super(ImageDigestCache, self).__init__()
        self._tag_digests = defaultdict(dict)
        self._digest_tags = defaultdict(set)

    def __contains__(self, item):
        return item in self._tag_digests

    def _discard_digest_tag(self, digest, repo, tag):
        tags = self._digest_tags.get(digest)
        if tags is not None:
            tags.discard((repo, tag))
            if not tags:
                del self._digest_tags[digest]

    def add_image(self, repo, tag, digest):
        """
        Adds an image to the cache associated with the given digest. This does not check whether there are already any
        images that need re-assignment; for updating an existing cache with new data, use ``update_image``.

        :param repo: Repository name.
        :type repo: str
        :param tag: Image tag.
        :type tag: str
        :param digest: Image digest.
        :type digest: bytes
        """
        self._tag_digests[repo][tag] = digest
        self._digest_tags[digest].add((repo, tag))

    def update_image(self, repo, tag, digest):
        """
        Adds an image to the cache associated with the given digest. If the digest is already associated with different
        repositories/tags, these relations are removed first.

        :param repo: Repository name.
        :type repo: str
        :param tag: Image tag.
        :type tag: str
        :param digest: Image digest.
        :type digest: bytes
        """
        existing_tags = self._tag_digests.get(repo)
        if not existing_tags:
            self.add_image(repo, tag, digest)
        existing_digest = existing_tags.get(tag)
        if existing_digest:
            if existing_digest == digest:
                return False
            self._discard_digest_tag(existing_digest, repo, tag)
            self._digest_tags[digest].add((repo, tag))
            existing_tags[tag] = digest

    def remove_repository(self, name):
        """
        Removes a repository with all of its tags from the cache. Also cleans up the digests that are associated with
        these unless there are still other tags associated with them.

        :param name: Repository name.
        :type name: str
        :return: ``True`` if there was anything to remove, ``False`` otherwise.
        :rtype: bool
        """
        existing_rd = self._tag_digests.get(name)
        if not existing_rd:
            return False
        existing_digests = set(existing_rd.values())
        for digest in existing_digests:
            existing_tags = self._digest_tags.get(digest)
            repo_tags = {i for i in existing_tags if i[0] == name}
            existing_tags.difference_update(repo_tags)
            if not existing_tags:
                del self._digest_tags[digest]
        del self._tag_digests[name]
        return True

    def remove_tag(self, repo, tag):
        """
        Removes a particular tag of a repository from the cache. Also cleans up the digest that are associated with
        it unless there are still other tags using the same.

        :param repo: Repository name.
        :type repo: str
        :param tag: Image tag.
        :type tag: str
        :return: ``True`` if there was anything to remove, ``False`` otherwise.
        :rtype: bool
        """
        existing_rd = self._tag_digests.get(repo)
        if not existing_rd:
            return False
        existing_digest = existing_rd.get(tag)
        if not existing_digest:
            return False
        self._discard_digest_tag(existing_digest, repo, tag)
        del existing_rd[tag]
        if not existing_rd:
            del self._tag_digests[repo]
        return True

    def remove_digests(self, digests):
        """
        Removes digests from the cache. Also removes any repository tags that were using them.

        :param digests: List of digests.
        :type digests: list[bytes]
        """
        all_tags = itertools.chain.from_iterable((self._digest_tags.get(digest) for digest in digests))
        for repo, repo_tags in itertools.groupby(sorted(all_tags, key=_get_first), _get_first):
            repo_digests = self._tag_digests[repo]
            for rt in repo_tags:
                del repo_digests[rt[1]]
            if not repo_digests:
                del self._tag_digests[repo]
        for digest in digests:
            del self._digest_tags[digest]

    def reset(self):
        """
        Clears all contents from the cache.
        """
        self._tag_digests.clear()
        self._digest_tags.clear()

    def get_digests(self, repo, tags=None):
        """
        Returns a set of digests that match the given repository. Also filters by matches of the given tag if provided.

        :param repo: Repository name.
        :type repo: str
        :param tags: Image tags of the repository.
        :rtype tags: list[str]
        :return: Set of content digests.
        :rtype: set[docker_registry_query.digest.ContentDigest]
        """
        if tags is not None:
            return set(filter(None, (self._tag_digests.get(repo, {}).get(tag)
                                     for tag in tags)))
        return set(self._tag_digests.get(repo, {}).values())

    def get_tag_digests(self, repo):
        """
        Returns a dictionary of tags and digests on the given repo.

        Note that changes to this will affect the cache contents.

        :param repo: Repository name.
        :type repo: str
        :return: Dictionary of tags and their digest.
        :rtype: dict[str, docker_registry_util.digest.ContentDigest]
        """
        return self._tag_digests.get(repo)

    def get_digest_repos(self, digest):
        """
        Returns a set of all repositories that contain any tag with the given digest.

        :param digest: Image digest.
        :type digest: bytes
        :return: Repository names.
        :rtype: set[str]
        """
        return set(rt[0] for rt in self._digest_tags.get(digest, []))

    def get_digest_tags(self, digest):
        """
        Returns all repo-tag-tuples that are associated with the given digest.

        Note that changes to this will affect the cache contents.

        :param digest: Image digest.
        :type digest: bytes
        :return: Set of tuples, each with repository name and image tag.
        :rtype: set[(str, str)]
        """
        return self._digest_tags.get(digest)

    def get_grouped_tags(self, digest):
        """
        Same as ``get_digest_tags``, but returns a group iterator by repository name.

        :param digest: Image digest.
        :type digest: bytes
        :return: A groupby object for iterating over repositories and tags.
        :rtype: itertools.groupby
        """
        tags = self._digest_tags.get(digest, ())
        return itertools.groupby(sorted(tags, key=_get_first), _get_first)

    def get_repo_names(self):
        """
        Returns a sorted list of available repository names.

        :return: Repository name list.
        :rtype: list[str]
        """
        return sorted(self._tag_digests.keys())

    def get_tag_names(self, repos=None):
        """
        Returns a sorted list of available tags, optionally filtered by a set of repository names.

        :param repos: Optional list or other iterable of repository names to limit the output.
        :type repos: list[str] | tuple[str] | set[str] | NoneType
        :return: List with tuples of repositories and tags.
        :rtype: list[(str, str)]
        """
        if repos:
            return [(repo, tag)
                    for repo in repos
                    for tag in sorted(self._tag_digests[repo].keys())]
        return [(repo, tag)
                for repo, tag_repos in sorted(self._tag_digests.items(), key=_get_first)
                for tag in sorted(tag_repos.keys())]

    @classmethod
    def _load(cls, tag_digests):
        if not isinstance(tag_digests, dict):
            raise ValueError("Unexpected object type.", type(tag_digests).__name__)
        new_instance = cls()
        new_instance._tag_digests.update({repo: {tag: ContentDigest.from_sha256(digest)
                                                 for tag, digest in tags.items()}
                                          for repo, tags in tag_digests.items()})
        digest_tags = new_instance._digest_tags
        for repo, tags in tag_digests.items():
            for tag, digest in tags.items():
                digest_tags[ContentDigest.from_sha256(digest)].add((repo, tag))
        return new_instance

    def _serialize(self):
        return {repo: {tag: digest.as_sha256()
                       for tag, digest in tags.items()}
                for repo, tags in self._tag_digests.items()}

    @classmethod
    def load(cls, file):
        """
        Creates a new cache instance from the given file-like object, containing the JSON-encoded contents of the
        registry information.

        :param file: File object.
        :return: New ImageCache instance.
        :rtype: ImageDigestCache
        """
        tag_digests = json.load(file)
        return cls._load(tag_digests)

    @classmethod
    def loads(cls, s):
        """
        Creates a new cache instance from the given string, containing the JSON-encoded contents of the registry
        information.

        :param s: JSON-encoded string.
        :return: New ImageCache instance.
        :rtype: ImageDigestCache
        """
        tag_digests = json.loads(s)
        return cls._load(tag_digests)

    def dump(self, file):
        """
        Stores the current state of the cache in the given file-like stream as a JSON object.

        :param file: File object.
        """
        json.dump(self._serialize(), file,  **DUMP_KWARGS)

    def dumps(self):
        """
        Returns a JSON-encoded object representation of the current cache state.

        :return: JSON string.
        :rtype: str
        """
        return json.dumps(self._serialize(), **DUMP_KWARGS)
