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

.. code::

    python3 -m pip install --user edulint

.. note::
   EduLint needs Python 3.8 (or higher).

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