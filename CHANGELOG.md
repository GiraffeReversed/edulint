## WIP

## v4.3.0

### Features

- new Package API (see [docs](https://edulint.readthedocs.io/en/latest/package_api.html) for more info)
- new checker: detect overcomplicated conditions and infinite loops using Z3 (optional dependency) by @danielczinege in #12 and #14 
- new checker: detect inefficient ifs which use `range(..)` and could be simplified @danielczinege in #13
- new checker: detect multiple ifs which could be combined by `if x in [...]` or `if x in {...}`
- improved data dependency analysis
- added packaged configurations `full` and `cs1`
- search for implicit edulint configuration (`edulint.toml` or `.edulint.toml`) in parent folders

### Changes

- generalized `similar-if-to-untwisted` to cover more cases
- improved `similar-block-to-call`
- run flake8 through its (undocumented) API instead of as subprocess
- generate parts of docs based on docstrings
- add pipx and docker installation guides to readme and docs
- work on performance (significant speed up in some checks to partially ofset the slowdown from new checks)
- add support for Python 3.14
- use Python 3.14 as default for Docker image
- build ARM64 Docker image
- build Docker image including optional dependencies
- update CICD actions
- relax tomli and tqdm dependency version requirements
- refactor: removed 'print' from PURE_FUNCTIONS #17 by @danielczinege

## v4.2.2

- fix bug in overriders, which caused overriden message to be removed, even if it was in a different file

## v4.2.1

- require pylint < 3.3 to hotfix error msgs which would be confusing for users

## v4.2.0

- update support for Python 3.13
- remove `no-self-use` from the `enhancement` group
- allow "command line" or "configuration file" in Pylint path
- fail gracefully when checked file not found

## v4.1.5

- add support for installing through `pipx`

## v4.1.4

- remove false-positive undefined group log

## v4.1.3

- skip missing examples/explanations in `edulint explain`

## v4.1.1

- update docs, document language translations
- added `edulint explain all` to get all available explanations
- fix `use-for-loop`: missing check whether the variable is incremented towards the limit
- separated `similar-block-to-loop` to `similar-block-to-loop-range` and `similar-block-to-loop-collection`
- update support for Python 3.12
- resolve config files and language files relative to the parent config/checked file

## v4.0.0

### breaking changes
- upgrade dependencies to newest versions (most notably Pylint to >= 3, backwards incompatible)
    - for breaking changes in Pylint, see [its documentation](https://pylint.readthedocs.io/en/stable/whatsnew/3/3.0/index.html)
- change CLI -- add check, explain and version subcommands
    - to lint a file: edulint -> edulint check
- the no-duplicate-code checker has been renamed to old-no-duplicate-code and replaced by a new no-duplicate-code checker (old name -> new name)
    - duplicate-if-branches -> identical-if-branches-part
    - duplicate-seq-ifs -> identical-seq-ifs
- the short-problems checker has been renamed to local-issues
- the improper-loop checker has been renamed to unsuited-loop

### other changes
- run Pylint through API instead of as a subprocess (tests now run in 20s with 10 workers instead of 60)
- added some checkers for duplicate code
- update unsuited-loop and no-global-variables to use the new data dependency analysis
