# EduLint

[![Pypi](https://img.shields.io/pypi/v/edulint)](https://pypi.org/project/edulint/)
![Python versions](https://img.shields.io/badge/python-3.8%20--%203.13-blue)
![Tests](https://img.shields.io/github/actions/workflow/status/GiraffeReversed/edulint/test.yaml)
[![ReadTheDocs](https://img.shields.io/readthedocs/edulint)](https://edulint.readthedocs.io/)
[![Docker image](https://img.shields.io/docker/image-size/edulint/edulint-cli/latest?label=Docker%20image%20size)](https://hub.docker.com/r/edulint/edulint-cli)

EduLint is a Python linter aimed at helping novice programmers improve their coding style. Presently, it integrates flake8 and pylint, with some tweaks to their default configuration.

This repository contains the linter itself, which is packaged and published as a [Pypi package `edulint`](https://pypi.org/project/edulint/). There is also a web version running at [edulint.com](https://edulint.com/) for easy use. Its source code is in [another repository](https://github.com/GiraffeReversed/edulint-web).

![Demo GIF](docs/source/_static/demo2.gif)

## Usage

### Web version

Are you just starting with programming in Python? Then the web UI ([website](https://edulint.com), [repo](https://github.com/GiraffeReversed/edulint-web)) might be the best choice for you.

### Python package

You can install the latest release with pip:

```sh
python3 -m pip install --user edulint
```

Once installed, you can run it as a Python module:

```sh
python3 -m edulint check <file-to-lint>
```

Read the [documentation](https://edulint.readthedocs.io/) for more options and configuration details.

### Docker container

Don't want to install Python and Edulint as a Python package? You can also run it using Docker.

```sh
docker pull edulint/edulint-cli  # Optional

docker run -v ${PWD}:/app edulint/edulint-cli check some_file.py

# Additional example that lints a file with absolute path /tmp/some_file.py
docker run -v /tmp:/app edulint/edulint-cli check /app/some_file.py
```

<!-- TODO: volume mapping can be :ro, though it's not necessary -->

It supports the same configuration options as the native Python package.

## Road map (long-term)

- [x] Additional explanations for problems detected in code
- [x] [Thonny plugin](https://github.com/GiraffeReversed/thonny-edulint)
- [x] More code quality defects (from WPS; detecting duplicate code)
- [x] Rewrite web to [React](https://github.com/GiraffeReversed/edulint-react-web)
- [ ] Add additional functionality to web (more settings, better teacher onboarding, …)
- [ ] Speed-up linting by switching to [Ruff](https://github.com/charliermarsh/ruff)
- [ ] official VS Code plugin (3rd party plugin already exists: [Github](https://github.com/matousekm/edulint-vscode), [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=matousekm.edulint-vscode))


## Sponsorship and academic collaboration

Are you interested in sponsoring this project, want to collaborate on an academic paper, or know of any interesting grants? Feel free to reach out to anna.rechtackova@mail.muni.cz.

## Compatibility with other software

#### Python version

Supported: Python 3.8+ (tested up-to Python 3.12)

Python 3.7 is no-longer officially supported, as Python 3.7 is already EOL. Last version that supported it was Edulint v3.6.1. Be aware that some linting results may be different between 3.7 and 3.8 due to different parsing between package `typed-ast` (<=3.7) and Python's native `ast` (>=3.8).
