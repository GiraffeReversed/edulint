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

Installation
""""""""""""

To install EduLint locally, open an interactive shell and run:

.. code:: bash

    python3 -m pip install --user edulint

.. note::
   EduLint needs Python 3.8 (or higher).

EduLint has an optional dependency, Z3, used for some of the checkers. The checkers that require Z3 are explicitly marked as such in :ref:`the list of checkers <checkers>`. None of these checkers are enabled by default. If you want to install EduLint including this dependency, run:

.. code:: bash

   python3 -m pip install --user edulint[z3]

.. note::
   If you run the basic version of EduLint without Z3, but enable one of the checkers using Z3, an error will be printed, instructing you to install the optional dependency.

If you are not sure what to install, you can always run the following command, which installs all optional dependencies.

.. code:: bash

   python3 -m pip install --user edulint[all]

Run EduLint locally
"""""""""""""""""""

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

.. TODO: Docker, VS Code