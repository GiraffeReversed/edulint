# EduLint

[![Pypi](https://img.shields.io/pypi/v/edulint)](https://pypi.org/project/edulint/)
![Python versions](https://img.shields.io/badge/python-3.8%20--%203.14-blue)
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

For ease of use there are multiple ways how to install and run EduLint locally. You can find more examples, options and configurations details in the [documentation](https://edulint.readthedocs.io/).

#### Using pipx

```sh
pipx install edulint        # Installation
edulint check some_file.py  # Usage example
```

#### Using pip

```sh
python3 -m pip install --user edulint  # Installation
python3 -m edulint check some_file.py  # Usage example
```

#### Docker container

```sh
docker run -v ${PWD}:/app edulint/edulint-cli check some_file.py
```

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

Supported: Python 3.8+ (tested up-to Python 3.14)

Python 3.7 is no-longer officially supported, as Python 3.7 is already EOL. Last version that supported it was Edulint v3.6.1. Be aware that some linting results may be different between 3.7 and 3.8 due to different parsing between package `typed-ast` (<=3.7) and Python's native `ast` (>=3.8).
