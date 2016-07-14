import logging


log = logging.getLogger(__name__)


class DockerRegistryRemover(object):
    """
    Utility for removing manifests from the Docker Registry by dynamic selections (e.g. repositories, tags).

    :param query: DockerRegistryQuery instance.
    :type query: docker_registry_util.query.DockerRegistryQuery
    """
    def __init__(self, query):
        self._query = query

    def remove_repositories(self, names, **kwargs):
        """
        Removes all digests used by the given repositories, i.e. any of its tags.

        :param names: Repository name or a list of multiple repository names.
        :type names: str | list[str]
        :param kwargs: Additional kwargs for :meth:`docker_registry_util.query.DockerRegistryQuery.select_repositories`.
        :return: A list of tuples, each with repository name and digest. If a digest is referred to by multiple
         repositories, only the first one (in the order of ``names``) is listed.
        :rtype: list[(str, docker_registry_util.digest.ContentDigest)]
        """
        client = self._query.client
        cache = self._query.cache
        repo_digests = self._query.select_repositories(names, **kwargs)
        for name, digest in repo_digests:
            log.info("Removing digest %s.", digest)
            client.delete_manifest(name, digest.as_sha256())
        digests_only = [i[1] for i in repo_digests]
        cache.remove_digests(digests_only)
        log.info("Deleted %s digests.", len(repo_digests))
        return repo_digests

    def remove_tags(self, repos, tags, **kwargs):
        """
        Removes all digests used by the given repositories and their tags matching the given selectors.

        :param repos: Repository name or a list of multiple repository names.
        :type repos: str | list[str]
        :param tags: Single tag name or list of tag names for exact match. Or version selectors, e.g. ``>=1.0.0`` for
         selecting versioned tags. Or compiled regular expressions for performing RegEx matches.
        :param kwargs: Additional kwargs for :meth:`docker_registry_util.query.DockerRegistryQuery.select_tags`.
        :return: A list of tuples, each with repository name and digest. If a digest is referred to by multiple
         repositories, only the first one (in the order of ``repos``) is listed.
        :rtype: list[(str, docker_registry_util.digest.ContentDigest)]
        """
        client = self._query.client
        cache = self._query.cache
        tag_digests = self._query.select_tags(repos, tags, **kwargs)
        for name, digest in tag_digests:
            log.info("Removing digest %s.", digest)
            client.delete_manifest(name, digest.as_sha256())
        digests_only = [i[1] for i in tag_digests]
        cache.remove_digests(digests_only)
        log.info("Deleted %s digests.", len(tag_digests))
        return tag_digests
