# Change History

## 1.0.3

* Added option to use ``GET`` method instead of ``HEAD`` for content digest requests. Fixes #3.
* Added sorting to the tag output from ``list-tag-names``.
* Added output mode to ``list-tag-names`` that matches the format of Docker images (i.e. prefixed with registry and
  repositiory/tag separated by colon).

## 1.0.2

* Added registry authentication from Docker config (suggested in #1).

## 1.0.1

* Added HTTP digest authentication, client certificates, and server certificate validation settings.
* Renamed `log_level` argument to `log-level`.

## 1.0.0

Initial release.
