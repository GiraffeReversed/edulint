# EduLint

EduLint is a Python linter aimed at helping beginning programmers improve their coding style. At present moment, it integrates flake8 and pylint, with some tweaks to their default configuration.

The repository contains both the linter itself. For ease of use for the beginning programmers, there is a web version running at [edulint.rechtackova.cz](https://edulint.rechtackova.cz/).

You can install the latest release with pip:

```
python<version> -m pip install edulint
```


Once installed, you can run it as a python module:

```
python<the-same-version> -m edulint <file-to-lint>
```

Read the [documentation](https://edulint.readthedocs.io/) for more options and configuration details.
