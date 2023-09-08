.. EduLint documentation master file, created by
   sphinx-quickstart on Sun Jul 17 12:16:02 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. sections of this document were adapted from flake8's documentation, available
.. at https://github.com/PyCQA/flake8/blob/6027577d325b0dd8bf1e465ebd29b71b5f0d005b/docs/source/index.rst

.. role:: python(code)
   :language: python

.. EduLint: Python linter for programming students
.. ================================================

Quick start
-----------

Simply use
^^^^^^^^^^

A publicly available instance of EduLint with is running at `EduLint <https://edulint.rechtackova.cz/editor>`_.

Installation
^^^^^^^^^^^^

To install EduLint locally, open an interactive shell and run:

.. code::

    python3 -m pip install --user edulint

.. note::
   EduLint needs Python version at least 3.7 to work.

Run EduLint locally
^^^^^^^^^^^^^^^^^^^

To start using EduLint, open an interactive shell and run:

.. code::

   python3 -m edulint path/to/code/to/check.py

.. note::
   Multiple filenames can be passed and linted at once. If a directory is passed, it is traversed and all :code:`.py` files it contains are linted.

Overview
--------

EduLint wraps around `Pylint <https://pylint.pycqa.org/>`_ and `Flake8 <https://flake8.pycqa.org/>`_, allowing for separate configuration of each of the tools. It provides a reasonable default and convenience "bulk names" for groups of checks that make sense to be enabled together. It transforms some messages to make them clearer to a beginner, or drops some messages entirely. It also provides extra checks for situations not covered by either of the linters.

As of now, it is possible to configure the tool in three ways:

-  by augmenting the checked source with lines beginning with :python:`# edulint`, with the configuration applying to that file only
- by passing arguments through the CLI, applying to all files linted by that command
- by setting a config file, specified by one of the two means above

Configuration
-------------

Edulint takes arguments in one of the following forms: ``<option-name>`` for options that do not take an argument and either ``<option-name>=<value-without-spaces>`` or ``<option-name>="<value-with-spaces>"`` for options that do take an argument.

.. note::
   In-file configuration always applies to the whole file, even if configuration lines are only after some code.

.. note::
   CLI configuration always applies to all files linted with that command, even if some files are specified before an option.

.. note::
   CLI configuration takes precedence over in-file configuration, which takes precedence over configuration from a config file.

   For example, if a check is disabled in-file and enabled in CLI, it ends up enabled.

   The options are evaluated in the order in which they are written.

Configuration through comments in the code
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When configuring in the linted file directly, the lines must start with :python:`# edulint:`

.. code::

   # edulint: enhancement
   # edulint: flake8=--max-line-length=20

It is also possible to combine multiple options on one line:

.. code::

   # edulint: python-specific allowed-onechar-names=ijk

One option can be used multiple times, the rules for how its values are combined are listed in the :ref:`Options table <options-table>`. For both of the following snippets, the resulting value for :code:`allowed-onechar-names` would be :code:`ijk`, because with the option, the method of combining result is replacing the old one with the new one.

.. code::

   # edulint: allowed-onechar-names=abc
   # edulint: allowed-onechar-names=ijk

.. code::

   # edulint: allowed-onechar-names=abc allowed-onechar-names=ijk

Configuration through CLI
^^^^^^^^^^^^^^^^^^^^^^^^^

When configuring through CLI, pass the configuration through the option ``--option`` (``-o`` for short).

.. code::

   python3 -m edulint --option enhancement -o pylint=--enable=no-self-use code/to/check.py

It is also possible to pass multiple options in one ``--option`` argument.

.. code::

   python3 -m edulint --option "enhancement pylint=--enable=no-self-use" code/to/check.py

Configuration files
^^^^^^^^^^^^^^^^^^^

It is possible to specify a config file, either in linted file (:python:`# edulint: config=default`) or through command line (:code:`-o config=default`). It is possible to choose a prepared config file (:code:`empty` for no checks, :code:`default` for default configuration), or specify one's own.

Apart from prepared configuration files, the :link_option:`config` also accepts a local path (:code:`config=/path/to/local/toml/file`) or URL (:code:`config=https://web.tld/path/to/remote/toml`).

The required format is currently undocumented.

Options
^^^^^^^

Currently available options are as follows:

.. _options-table:

.. options-table::

Capabilities
------------

On top of the linters used, EduLint provides several extra or convenience capabilities: it has (what we deemed) reasonable default set of pylint checks, with shortcut names for enabling groups of more checks, that are not necessarily essential for a beginning programmer, but can be useful for one who no longer struggles with the basics, but wants to improve further.

It filters out or tweaks emitted messages to make them more comprehensible to a beginning programmer (currently there is no way to turn these off).

It provides explanation (currently only a very limited number) for why is some reported problem really a problem and how it can be fixed (at present, available in web version only).

.. note::

   In this section, the descriptions of Pylint messages are scraped directly from Pylint documentation: `(1) <https://pylint.pycqa.org/en/latest/user_guide/checkers/features.html>`_, `(2) <https://pylint.pycqa.org/en/latest/user_guide/checkers/extensions.html>`_.

Default
^^^^^^^

In the default configuration, the default configuration of ``flake8`` is used. For ``pylint``, the following checks are enabled:

.. message-table::
   default

Translations
^^^^^^^^^^^^

EduLint provides convenience "bulk names" for groups of ``pylint`` messages. One flag enables multiple messages that have a common theme.

These can be enabled by specifying :link_option:`set-groups` (e.g. ``set-groups=enhancement,complexity``).

Enhancement
""""""""""""

``enhancement`` groups those messages, that should be followed but it is not essential skill for a beginner:

.. message-table::
   enhancement

Python-specific
"""""""""""""""

``python-specific`` enables those messages that improve the code, but are specific to Python:

.. message-table::
   python-specific


Complexity
""""""""""

``complexity`` enables those messages that check for overly complex code but provide little guidance on how to fix it:

.. message-table::
   complexity

Custom checkers
^^^^^^^^^^^^^^^

EduLint provides custom checkers to report more problems frequent in beginners' code. It does so by extending Pylint with extra plugins. The checkers can therefore be invoked in the standard Pylint manner (e.g. using :code:`--enable` or :code:`--disable`) on the Edulint's :link_option:`pylint` option.

.. checkers-block::

Tweakers
^^^^^^^^

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Tweaked message
     - Effects
   * - :link_pylint:`invalid-name`
     -
      * does not emit messages about invalid module name
      * emits messages only about variable names that do indeed break :code:`snake_case`
   * - :link_pylint:`disallowed-name`
     -
      * when :link_option:`allowed-onechar-names` is enabled, complains on all single-character variable names, encouraging choosing a different name
   * - :link_pylint:`consider-using-in`
     -
      * if all enumerated values are all single characters, suggests joining them into string rather than using a tuple (:code:`ch in ".,?"` instead of :code:`ch in ('.', ',', '?')`)

.. Indices and tables
.. ------------------

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
