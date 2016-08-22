#!/usr/bin/env python

import argparse
import json
import logging
import os
import re

from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth

from .client import DockerRegistryClient
from .query import DockerRegistryQuery
from .remover import DockerRegistryRemover

RE_REPLACE_PATTERN = re.compile('(?:.+//)(.*)')
DOCKER_CONFIG_FILE = os.path.expanduser('~/.docker/config.json')


def value_or_false(value):
    if not value or str(value).lower() in ('false', '0', 'no', 'none'):
        return False
    return value


def _get_cache_name(registry):
    if args.cache is None:
        return '{0}_cache.json'.format(RE_REPLACE_PATTERN.sub(r'\1', registry).replace('/', '_').replace('.', '_'))
    return value_or_false(args.cache)


def _get_auth_config(registry):
    try:
        with open(DOCKER_CONFIG_FILE) as config_file:
            config_data = json.load(config_file)
    except (IOError, json.JSONDecodeError):
        return None
    auth_data = config_data.get('auths')
    if not auth_data:
        return None
    registry_data = auth_data.get(registry)
    if not registry_data:
        return None
    return registry_data.get('auth')


def _get_query():
    registry = args.registry
    if not registry:
        parser.error("No registry provided, neither as a command argument nor through the environment variable "
                     "REGISTRY.")
    if registry.startswith('http'):
        base_url = registry
    else:
        base_url = 'https://{0}'.format(registry)
    kwargs = {}
    if args.user:
        if args.digest_auth:
            kwargs['auth'] = HTTPDigestAuth(args.user, args.password)
        else:
            kwargs['auth'] = HTTPBasicAuth(args.user, args.password)
    elif os.path.isfile(DOCKER_CONFIG_FILE):
        config_auth = _get_auth_config(registry)
        if config_auth:
            kwargs['auth'] = HTTPBase64Auth(config_auth)
    if args.verify is not None:
        kwargs['verify'] = value_or_false(args.verify)
    if args.client_cert:
        if args.client_key:
            kwargs['cert'] = (args.client_cert, args.client_key)
        else:
            kwargs['cert'] = args.client_cert

    client = DockerRegistryClient(base_url, **kwargs)
    query = DockerRegistryQuery(client)
    cache_fn = _get_cache_name(registry)
    if cache_fn and os.path.isfile(cache_fn) and not args.refresh:
        with open(cache_fn) as f:
            query.load(f)
    return query


def _save_query(query):
    cache_fn = _get_cache_name(args.registry)
    if cache_fn:
        with open(cache_fn, 'w') as f:
            query.dump(f)


def _get_tag_args():
    if not (args.tags or args.regex):
        parser.error("No tags specified.")
    if args.tags:
        tag_list = args.tags[:]
    else:
        tag_list = []
    if args.regex:
        tag_list.extend([re.compile(exp) for exp in args.regex])
    if args.exclude:
        exclude_list = args.exclude[:]
    else:
        exclude_list = []
    if args.exclude_regex:
        exclude_list.extend([re.compile(exp) for exp in args.exclude_regex])
    return {
        'tags': tag_list,
        'exclude_tags': exclude_list,
        'raise_intersecting_repo': args.raise_intersecting_repo,
        'raise_intersecting_tag': args.raise_intersecting_tag,
        'match_all_tags': args.match_all_tags
    }


def _show_count(item_type, res):
    if not args.count:
        return
    status_str = "Number of {0}: {1}".format(item_type, len(res))
    sep_str = '-' * len(status_str)
    print(sep_str)
    print(status_str)


class HTTPBase64Auth(AuthBase):
    """
    Similar to HTTPBasicAuth, but handles the base64 encoded string directly instead of dividing it into user name
    and password.
    """
    def __init__(self, auth):
        self.auth = auth

    def __eq__(self, other):
        return self.auth == getattr(other, 'auth', None)

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        r.headers['Authorization'] = 'Basic {0}'.format(self.auth)
        return r


def list_repo_names(query):
    result = query.get_repo_names()
    for repo in result:
        print(repo)
    _show_count('repositories', result)


def list_tag_names(query):
    result = query.get_tag_names(args.repo)
    repo_len = max([len(r[0]) for r in result])
    for repo, tag_name in result:
        print('{0:{1}}  {2}'.format(repo, repo_len, tag_name))
    _show_count('tags', result)


def query_repos(query):
    repo_len = max(map(len, args.repo))
    result = query.select_repositories(args.repo, raise_intersecting_repo=args.raise_intersecting_repo)
    for repo, digest in result:
        print('{0:{1}}  {2}'.format(repo, repo_len, digest))
    _show_count('selected digests', result)


def query_tags(query):
    repo_len = max(map(len, args.repo))
    result = query.select_tags(args.repo, **_get_tag_args())
    for repo, digest in result:
        print('{0:{1}}  {2}'.format(repo, repo_len, digest))
    _show_count('selected digests', result)


def remove_repos(query):
    remover = DockerRegistryRemover(query)
    result = remover.remove_repositories(args.repo, raise_intersecting_repo=args.raise_intersecting_repo)
    _show_count('removed digests', result)


def remove_tags(query):
    if not (args.tags or args.regex):
        parser.error("No tags specified.")
    remover = DockerRegistryRemover(query)
    result = remover.remove_tags(args.repo, **_get_tag_args())
    _show_count('removed digests', result)


parser = argparse.ArgumentParser(description="Lists or removes tags by selection from a Docker Registry.")
parser.add_argument('--registry', '-reg', default=os.getenv('REGISTRY'),
                    help="Registry name. Can also be set using the environment variable REGISTRY.")
parser.add_argument('--user', '-u', default=os.getenv('REGISTRY_USER'),
                    help="Registry user. Can also be set using the environment variable REGISTRY_USER. If neither is "
                         "provided, attempts to read authentication from the Docker CLI config in "
                         "'{0}'".format(DOCKER_CONFIG_FILE))
parser.add_argument('--password', '-p', default=os.getenv('REGISTRY_PASSWORD'),
                    help="Registry password. Can also be set using the environment variable REGISTRY_PASSWORD.")
parser.add_argument('--digest-auth', default=os.getenv('REGISTRY_USE_DIGEST_AUTH'),
                    help="Use HTTP Digest Authentication instead of plain basic auth.")
parser.add_argument('--client-cert', '-cert', default=os.getenv('REGISTRY_CLIENT_CERT'),
                    help="Path to a file that contains a client-side certificate. It also needs to include the key, "
                         "or the key needs to be passed separately using '-key'.")
parser.add_argument('--client-key', '-key', default=os.getenv('REGISTRY_CLIENT_KEY'),
                    help="Path to a file that contains the key to the client certificate used in '-cert'.")
parser.add_argument('--verify', '-v',
                    help="Bundle of trusted certificate authorities for verifying a SSL certificate. If set to 'None', "
                         "verification is disabled (not recommended).")
parser.add_argument('--cache', '-c', default=os.getenv('DOCKER_UTIL_CACHEFILE'),
                    help="Cache file to use for speeding up multiple calls. Can be set to 'None' to deactivate.")
parser.add_argument('--refresh', action='store_true', default=False,
                    help="Forces a complete reload from the registry, but unlike setting -c to 'None' creates a "
                         "new cache file.")
parser.add_argument('--count', action='store_true', default=False,
                    help="Show the number of selected items, e.g. tags, digests etc.")
parser.add_argument('--no-raise-intersecting-repo', action='store_false', default=True,
                    dest='raise_intersecting_repo',
                    help="Do not raise errors when repositories share digests, if the former are not part of the same "
                         "query. If set, digests shared by multiple, partially non-listed repositories are ignored.")
parser.add_argument('--log-level', '-l', default='info',
                    help="Output log level.")
subparsers = parser.add_subparsers(title='command', description="Type of operation to perform.")
parser_list_repos = subparsers.add_parser('list-repo-names',
                                          help="Lists the names of all available repositories in the registry. Empty "
                                               "repositories (i.e. not containing any tags) are ignored.")
parser_list_repos.set_defaults(func=list_repo_names)
parser_list_tags = subparsers.add_parser('list-tag-names',
                                         help="Lists the names of available tags in each repository, optionally "
                                              "filtered on a certain set of repository names.")
parser_list_tags.set_defaults(func=list_tag_names)
parser_query_repos = subparsers.add_parser('query-repos',
                                           help="Checks the registry for all digests of one or multiple repositories.")
parser_query_repos.set_defaults(func=query_repos)
parser_query_tags = subparsers.add_parser('query-tags',
                                          help="Runs a query against the registry on repositories and tags.")
parser_query_tags.set_defaults(func=query_tags)
parser_remove_repos = subparsers.add_parser('remove-repos',
                                            help="Deletes all digests of certain repositories from the registry.")
parser_remove_repos.set_defaults(func=remove_repos)
parser_remove_tags = subparsers.add_parser('remove-tags',
                                           help="Deletes all digests that match the given repositories and tags.")
parser_remove_tags.set_defaults(func=remove_tags)
for subparser in [parser_query_repos, parser_query_tags, parser_remove_repos, parser_remove_tags]:
    subparser.add_argument('--repo', '-r', nargs='+', required=True,
                           help="Repository names.")
parser_list_tags.add_argument('repo', nargs='*',
                              help="Optional repository names to filter on.")
for subparser in [parser_query_tags, parser_remove_tags]:
    subparser.add_argument('--tags', '-t', nargs='*',
                           help="Tag names or version selectors. Versions can be specified as comparisons, e.g. "
                                ">=1.0.0. The following operators are supported: == <= >= < >.")
    subparser.add_argument('--regex', '-re', nargs='*',
                           help="Regular expressions for tag selection.")
    subparser.add_argument('--exclude', '-x', nargs='*',
                           help="Tag names or version selectors to exclude.")
    subparser.add_argument('--exclude-regex', '-xre', nargs='*', dest='exclude_regex',
                           help="Regular expression for excluding tags from the selection.")
    subparser.add_argument('--no-match-all-tags', dest='match_all_tags', action='store_false', default=True,
                           help="By default all selected digests are reverse-checked if they only match selected repos "
                                "and tags. Digests with any other dependents are not removed, unless this option is "
                                "used. WARNING: This can destroy other tags and repositories that you are not aware "
                                "of. Always check the query output first!")
    subparser.add_argument('--raise-intersecting-tag', action='store_true', default=False,
                           dest='raise_intersecting_tag',
                           help="Raise errors when tags share digests, if the former are not part of the same query.")
args = parser.parse_args()


def main():
    if 'func' not in args:
        parser.error("No command was set.")
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(name)s - %(message)s', level=args.log_level.upper())
    logging.getLogger('requests').setLevel(logging.WARNING)

    q = _get_query()
    args.func(q)
    _save_query(q)
