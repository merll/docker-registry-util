import requests


class DockerRegistryClient(object):
    """
    A lighweight, minimalistic (and likely feature-incomplete) API client to the Docker registry. Likely to be
    extended but only for Registry v2+.

    All functions return the unparsed responses, as in some cases (e.g. images) header information may be useful.
    For more detailed information on the client functions and response contents, refer to the
    [Docker Registry API docs](https://docs.docker.com/registry/spec/api/).

    :param base_url: Base URL to the Docker Registry, excluding the ``v2`` path. E.g. if your registry is
      ``registry.example.com``, the base URL should be ``https://registry.example.com``.
    :type base_url: str
    :param kwargs: Additional keyword arguments (e.g. for authentication), which are set as attributes on to
      the :class:`requests.Session` instance.
    """
    def __init__(self, base_url, **kwargs):
        self._base_url = base_url
        self._session = requests.Session()
        self._session.headers = {
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json',
        }
        for k, v in kwargs.items():
            setattr(self._session, k, v)

    def _request(self, method, *args, **kwargs):
        request_url = '{0}/v2/{1}'.format(self._base_url, '/'.join(args))
        res = self._session.request(method, request_url, **kwargs)
        res.raise_for_status()
        return res

    @property
    def base_url(self):
        """
        Base URL to the Docker Registry, excluding the ``v2`` path.

        :return: Registry base URL.
        :rtype: str
        """
        return self._base_url

    @base_url.setter
    def base_url(self, value):
        self.base_url = value

    @property
    def session(self):
        """
        The client's :class:`requests.Session` instance for modifying settings, headers etc.

        :return: Session object.
        :rtype: requests.Session
        """
        return self._session

    def ping(self):
        return self._request('GET', '')

    def get_catalog(self):
        return self._request('GET', '_catalog')

    def get_tags(self, name):
        return self._request('GET', name, 'tags', 'list')

    def get_manifest(self, name, reference):
        return self._request('GET', name, 'manifests', reference)

    def head_manifest(self, name, reference):
        return self._request('HEAD', name, 'manifests', reference)

    def put_manifest(self, name, reference):
        return self._request('PUT', name, 'manifests', reference)

    def delete_manifest(self, name, reference):
        return self._request('DELETE', name, 'manifests', reference)

    def get_blob(self, name, digest):
        return self._request('GET', name, 'blobs', digest)

    def delete_blob(self, name, digest):
        return self._request('DELETE', name, 'blobs', digest)
