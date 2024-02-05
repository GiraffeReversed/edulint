Running EduLint
---------------

Use online instance
^^^^^^^^^^^^^^^^^^^

A publicly available instance of EduLint with is running at `edulint.com <https://edulint.com>`_.

Use local installation
^^^^^^^^^^^^^^^^^^^^^^

Installation
""""""""""""

To install EduLint locally, open an interactive shell and run:

.. code::

    python3 -m pip install --user edulint

.. note::
   EduLint needs Python version at least 3.7 to work.

Run EduLint locally
"""""""""""""""""""

To start using EduLint, open an interactive shell and run:

.. code::

   python3 -m edulint path/to/code/to/check.py

.. note::
   Multiple filenames can be passed and linted at once. If a directory is passed, it is traversed and all :code:`.py` files it contains are linted.

Use Thonny plugin
^^^^^^^^^^^^^^^^^

`Thonny <https://thonny.org/>`_ is an integrated development environment developed specifically for novice programmers. EduLint also comes as a plugin for this IDE. `Here <https://github.com/GiraffeReversed/thonny-edulint/blob/main/README.md>`_ you can learn how to install it.
