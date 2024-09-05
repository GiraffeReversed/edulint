# WIP

- separated `similar-block-to-loop` to `similar-block-to-loop-range` and `similar-block-to-loop-collection`
- added `edulint explain all` to get all available explanations
- resolve config files and language files relative to the parent config/checked file
- fix `use-for-loop`: missing check whether the variable is incremented towards the limit

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
