## WIP

## v4.2.2

- fix bug in overriders, which caused overriden message to be removed, even if it was in a different file

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
