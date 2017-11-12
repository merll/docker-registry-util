# Docker-Registry-Util

## Search and cleanup on Docker Registry v2.

Project: https://github.com/merll/docker-registry-util

# Overview
This project allows queries on existing repositories and tags of a Docker Registry (v2). It comes with a command line
utility `dregutil`, but can also be used as a lightweight API. Besides gathering information images can also be
deleted from a private Docker Registry, allowing for garbage collection.

# Background
It is a good idea to clean up a private Docker registry every now and then. For example, images that have only been
generated for testing purposes and never been sent to production could be deleted for freeing up storage space.

Since version 2.4.x, the [Docker Registry](https://github.com/docker/distribution/) comes with a
[garbage collector](https://github.com/docker/distribution/blob/master/docs/garbage-collection.md). According to its
documentation, it deletes all blobs not referred to by any image manifest, freeing up space.

The storage of the Docker registry itself is similar to the Docker host image collection: The Docker Registry works on
content-based storage, with the possibility for adding tags. If we take for example an image that has a certain SHA256
digest `sha256:00...` and two tags: `1.0.0` and `latest`. It is possible to address (e.g. fetch) the image using
both the digest and either tag. If we upload an image with digest `sha256:11...` and tags `2.0.0` and `latest`,
the `latest` tag will be removed from the `sha256:00...` image.

Other than the Docker API, which tells all the tags of a certain image id, the Registry API only lists repositories
and tags and shows the associated digest. Technically an identical digest can even be shared by multiple repositories.
If we want to remove an image, we want to make sure that we do not destroy unknown repositories and tags.

This utility presents this relation in both ways. When a tag is selected for deletion, its related digests are
reverse-checked for an association with any other repository and tag.

The entire registry tags and digests are read, and then stored locally in order to speed up further processes.
Therefore, the aforementioned reverse-check may take place on outdated information. It is recommended to update the
cache frequently using the  `--refresh` argument and - like the Docker Registry garbage collection - only perform any
change operations under low or no traffic on the registry.

# Registry configuration
In order for this tool to work, the Docker Registry needs to be configured for allowing deletion. In the configuration
file, add the following:

```yaml
delete:
  enabled: true
```

Besides that, you need to need to set the environment variable `REGISTRY_STORAGE_DELETE_ENABLED` to `true` when
creating the container. This is not documented in the
[Registry Configuration Reference](https://docs.docker.com/registry/configuration/) but was required last time I checked
and subject to some issue reports (e.g. [#989](https://github.com/docker/distribution/issues/989) and
[#1573](https://github.com/docker/distribution/issues/1573)).

# Installation

This library is implemented in Python 3. After [downloading and installing Python](https://www.python.org/downloads/),
installation is simply done via `pip`:

```bash
pip install docker-registry-util
```

for installing the latest release or

```bash
pip install git+https://github.com/merll/docker-registry-util.git
```

for installing the latest development version.

# Getting started

The library first needs to know how to connect to your registry. The following can be set via the command line or
through environment variables:

| Environment variable     | Command line arg. | Description                        |
| ------------------------ | ----------------- | ---------------------------------- |
| REGISTRY                 | -reg              | Registry server to connect to.     |
| REGISTRY_USER            | -u                | User for basic authentication.     |
| REGISTRY_PASSWORD        | -p                | Password for basic authentication. |
| REGISTRY_USE_DIGEST_AUTH | --digest-auth     | Use HTTP Digest Authentication instead of basic auth. |
| REGISTRY_CLIENT_CERT     | -cert             | Client certificate (and optionally key) for the registry. |
| REGISTRY_CLIENT_KEY      | -key              | Key for the client certificate, if not included in the -cert file. |
| REQUESTS_CA_BUNDLE       | -v                | Alternative bundle of certificate authorities for validating the registry. |

The `REGISTRY` / `-reg` specification is required. If `REGISTRY_USER` / `-u` is not specified, the tool attempts to
look up authentication information from the local Docker CLI configuration (`~/.docker/config.json`). 

With this basic configuration, you can query the registry contents via the command line, e.g.

```bash
dregutil list-repo-names
```

lists all the repository names from the registry.

```bash
dregutil list-tag-names
```

lists all available repositories and tags.

On the first start, the tool will query all digests and tags from the registry. In order to speed up operations, this
information is stored in a local cache file named according to the registry name. For example, setting the registry
to `registry.example.com` stores the cache in `registry_example_com_cache.json`. If you have done any upload operations
or deletes outside of this tool, you can force a refresh using the `--refresh` command line argument; you can also
relocate the cache file using the `-c` argument or deactivate the cache entirely setting `-c None`.

# Queries

Queries will list the digests that are used by particular repositories or tags.

Repositories can be queried by exact name:

```bash
dregutil query-repos -r my-repo
```

Tags can be listed using exact names or version selectors.

```bash
dregutil query-tags -r my-repo -t latest
```

Alternatively, you can query versions by prepending an operator `<`, `>`, `<=`, `>=`, or `==` to a version number.
Make sure to escape the `>` and `<` for the shell you are using.

```bash
dregutil query-tags -r my-repo -t \<1.4
```

Queries by regular expressions are also possible.

```bash
dregutil query-tags -r my-repo -re 1\\.*
```

For excluding a tag or version match, use the `-x` argument. For a RegEx-based exclusion, use `-xre`.

# Deletion

Deleting digests from the registry is possible using the same syntax as for queries, but using `remove-repos` or
`remove-tags`.

```bash
dregutil remove-repos -r my-repo
```

removes all digests that belong to the repository `my-repo` from the registry.

```bash
dregutil remove-tags -r my-repo -t \<1.4
```

marks all tags of `my-repo` as deleted that carry a version number lower than `1.4`.

# Partial vs. complete match

As image digests may belong to multiple tags, there is a possibility that you might select tags for deletion that are
shared with other images, but that you had not intended to remove. Therefore the default behavior is to reverse-check
selected digests against your original selection. For example

```bash
dregutil remove-tags -r my-repo -t \<1.4
```

will by erase all digests with a version number lower than `1.4`, unless they belong any other tag or repository. If
one of the images is also tagged as `my-repo/one`, it is not removed, unless 

```bash
dregutil remove-tags -r my-repo -t \<1.4 one
```

is specified.

This behavior can be changed generally using the `--no-match-all-tags` command line option. You can also raise an error
on the event of unexpected intersections using the `--raise-intersecting-tag` argument.

# Additional environment variables

The following settings from the command line can also be set in an environment variable.

| Environment variable     | Command line arg.  | Description                        |
| ------------------------ | ------------------ | ---------------------------------- |
| DOCKER_UTIL_CACHEFILE    | -c                 | Cache file to use. Set to 'None' to deactivate. |
| DOCKER_UTIL_GET_MANIFEST | --use-get-manifest | Uses the HTTP 'GET' method for fetching content digests. The default is using HEAD. |

# Further information

A complete reference to available commands and arguments is available via `dregutil --help`, or
`dregutil [command] --help` for details about single command.
