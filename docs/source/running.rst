.. _run edulint:

Running EduLint
---------------

.. _online instance:

Use online instance
^^^^^^^^^^^^^^^^^^^

A publicly available instance of EduLint is running at `edulint.com <https://edulint.com>`_.

.. _local installation:

Use local installation
^^^^^^^^^^^^^^^^^^^^^^

For ease of use there are multiple ways how to install and run edulint locally. You can use whichever is easiest for you. All the following examples presume that you have an interactive shell ready.

Using pipx
==========

Easiest installation method for Python packages is to `install pipx`_, if you don't have it already. After that you can install Edulint using:

.. _install pipx: https://pipx.pypa.io/latest/installation/

.. code:: bash

   pipx install edulint        # Installation
   edulint check some_file.py  # Usage example

Using pip
=========

If you are using Python with `virtual environment`_ already configured, you can install and use Edulint using the following commands:

.. _virtual environment: https://www.geeksforgeeks.org/python/create-virtual-environment-using-venv-python/

.. code:: bash

   python3 -m pip install edulint         # Installation
   python3 -m edulint check some_file.py  # Usage example

Using Docker
============

If you already have Docker installed then the easiest method how to use Edulint is to run it from a container. 

.. code:: bash

   docker run -v ${PWD}:/app edulint/edulint-cli check some_file.py
   # This is equivalent to:         `edulint     check some_file.py`

Edulint with optional dependencies
==================================

EduLint has an optional dependency, Z3, used for some of the checkers. The checkers that require Z3 are explicitly marked as such in :ref:`the list of checkers <checkers>`. None of these checkers are enabled by default. If you want to install EduLint including this dependency, run:

.. code:: bash

   python3 -m pip install edulint[z3]  # If you are using Python with venv
   pipx install edulint[z3]            # If you are using pipx
   # The Docker image already includes the optional dependencies 

.. note::
   If you run the basic version of EduLint without Z3, but enable one of the checkers using Z3, an error will be printed, instructing you to install the optional dependency.

If you are not sure what to install, you can always run the following commands, which install all optional dependencies.

.. code:: bash

   python3 -m pip install edulint[all]  # If you are using Python with venv
   pipx install edulint[all]            # If you are using pipx

Additional usage examples
=========================

To start using EduLint, open an interactive shell and run:

.. code::

   python3 -m edulint check path/to/code/to/check.py

.. note::
   Multiple filenames can be passed and linted at once. If a directory is passed, it is traversed and all :code:`.py` files it contains are linted.

EduLint can also produce the output as a JSON by passing the :code:`--json` option.

.. code::

   python3 -m edulint check path/to/code/to/check.py --json

.. _thonny plugin:

Use Thonny plugin
^^^^^^^^^^^^^^^^^

`Thonny <https://thonny.org/>`_ is an integrated development environment developed specifically for novice programmers. EduLint also comes as a plugin for this IDE. `Here <https://github.com/GiraffeReversed/thonny-edulint/blob/main/README.md>`_ you can learn how to install it.

.. TODO: VS Code
