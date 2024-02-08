.. role:: python(code)
   :language: python

Configuration
=============

EduLint wraps around `Pylint <https://pylint.pycqa.org/>`_ and `Flake8 <https://flake8.pycqa.org/>`_, allowing for separate configuration of each of the tools. It provides a reasonable default and convenience "bulk names" for groups of checks that make sense to be enabled together. It transforms some messages to make them clearer to a beginner, or drops some messages entirely. It also provides extra checks for situations not covered by either of the linters.

As of now, it is possible to configure the tool in three ways:

- by augmenting the checked source with lines beginning with :python:`# edulint:`, with the configuration applying to that file only
- by passing arguments through the CLI, applying to all files linted by that command
- by setting a config file, specified by one of the two means above

Edulint takes arguments in one of the following forms: ``<option-name>`` for options that do not take an argument and either ``<option-name>=<value-without-spaces>`` or ``<option-name>="<value-with-spaces>"`` for options that do take an argument.

.. note::
   In-file configuration always applies to the whole file, even if the configuration lines are only after some code.

.. note::
   CLI configuration always applies to all files linted with that command, even if some files are specified before an option.

.. note::
   CLI configuration takes precedence over in-file configuration, which takes precedence over configuration from a config file.

   For example, if a check is disabled in-file and enabled in CLI, it ends up enabled.

   The options are evaluated in the order in which they are written.

Configuration through comments in the code
------------------------------------------

When configuring in the linted file directly, the lines must start with :python:`# edulint:`

.. code::

   # edulint: set-groups=enhancement
   # edulint: flake8=--max-line-length=20

It is also possible to combine multiple options on one line:

.. code::

   # edulint: set-groups=python-specific allowed-onechar-names=ijk

One option can be used multiple times, the rules for how its values are combined are listed in the :ref:`Options table <options-table>`. For both of the following snippets, the resulting value for :code:`allowed-onechar-names` would be :code:`ijk`, because with the option, the method of combining result is replacing the old one with the new one.

.. code::

   # edulint: allowed-onechar-names=abc
   # edulint: allowed-onechar-names=ijk

.. code::

   # edulint: allowed-onechar-names=abc allowed-onechar-names=ijk

.. _cli configuration:

Configuration through CLI
-------------------------

When configuring through CLI, pass the configuration through the option ``--option`` (``-o`` for short).

.. code::

   python3 -m edulint --option set-groups=enhancement -o pylint=--enable=no-self-use code/to/check.py

It is also possible to pass multiple options in one ``--option`` argument.

.. code::

   python3 -m edulint --option "set-groups=enhancement pylint=--enable=no-self-use" code/to/check.py

.. _configuration files:

Configuration files
-------------------

.. _set config file:

Setting configuration file
^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to specify a config file, either in linted file (:python:`# edulint: config-file=default`) or through the command line (:code:`-o config-file=default`). It is possible to choose a prepared config file (:code:`empty` for no checks, :code:`default` for default configuration), or specify one's own.

Apart from prepared configuration files, the :link_option:`config-file` option also accepts a local path (:code:`config-file=/path/to/local/toml/file`) or URL (:code:`config-file=https://web.tld/path/to/remote/toml`). Relative local config files specified in-file are evaluated related to the file. Local config files specified from CLI are evaluated related to the current working directory.

If the config file name does not end in :code:`.toml`, it is treated as a packaged configuration (and looked up accordingly). If the name starts with :code:`http/https` protocol, it is treated as a remote configuration, otherwise (ends with :code:`.toml`, but does not start with a protocol) it is processed as a local configuration.

.. _create config file:

Creating custom configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Format
""""""

An EduLint config file is a TOML storing option-value pairs, with several convenience tweaks.

A simple configuration example:

.. code::

   pylint = "--enable=no-self-use,use-foreach"
   disallowed-builtin-names = "sum,len"

To set more options for Pylint and flake8, TOML tables can be used. In this case, Pylint and flake8 options are not prefixed with --.

.. code::

   disallowed-builtin-names = "sum,len"

   [pylint]
   enable = "no-self-use,use-foreach"
   bad-names-rgxs = "^[a-z]$"

   [flake8]
   ignore = "E"
   extend-select = "E225,E211"

Finally, instead of comma separated lists, TOML lists can be used:

.. code::

   disallowed-builtin-names = ["sum", "len"]

   [pylint]
   enable = ["no-self-use", "use-foreach"]
   bad-names-rgxs = "^[a-z]$"

   [flake8]
   ignore = "E"
   extend-select = ["E225", "E211"]

Configuration inheritance
"""""""""""""""""""""""""

The :link_option:`config-file` option can be used inside config files as well. In that case, the configuration from the referenced file will also be used, as if prepended to the current file's configuration.

For example, consider following two configurations files (in the same folder):

.. code::

   # file: A.toml

   [pylint]
   enable = "no-self-use"

.. code::

   # file: B.toml

   config-file = "A.toml"
   [pylint]
   enable = "use-foreach"

When using :code:`B.toml`, both :code:`no-self-use` and :code:`use-foreach` will be enabled.

.. TODO: link empty config

If the :link_option:`config-file` option is not specified in a configuration file, the empty configuration will be used.

Custom translations
"""""""""""""""""""

It is possible to define own names for groups of options. If a configuration contains the following tables, then passing :link_option:`set-groups` with value :code:`extra` adds the specified options to the configuration used for the respective tool.

.. code::

   [translations.extra.pylint]
   enable = ["no-self-use", "use-foreach"]
   bad-names-rgxs = "^[a-z]$"

   [translations.extra.flake8]
   ignore = "E"
   extend-select = ["E225", "E211"]

The string :code:`translations` is required (verbatim), followed by the name of the group and the name of the linter to which the options belong.

Multiple translations can be specified using different names. The previous example could be extended with the following table:

.. code::

   [translations.even-more-extra.pylint]
   enable = ["duplicate-if-branches", "duplicate-seq-ifs", "duplicate-exprs"]

Options
-------

Currently available options are as follows:

.. _options-table:

.. options-table::

.. _packaged configurations:

Packaged configurations
=======================

EduLint offers two configurations that are directly packaged with the tool: :code:`empty` and :code:`default`. The :code:`empty` configuration runs no checks. The :code:`default` configuration provides a reasonable default set of checks. On top of these, additional three convenience extension groups of checks can be enabled: :code:`python-specific`, :code:`enhancement` and :code:`complexity`. The check in these extensions groups are not necessarily essential for a novice programmer, but addressing them can improve the code further.

EduLint filters out or tweaks emitted messages to make them more comprehensible to a beginning programmer (currently there is no way to turn these tweakers off).

EduLint provides explanations for why and how can a reported problem be fixed (at present, available in web version only).

.. note::

   In this section, the descriptions of Pylint messages are scraped directly from Pylint documentation: `(1) <https://pylint.pycqa.org/en/latest/user_guide/checkers/features.html>`_, `(2) <https://pylint.pycqa.org/en/latest/user_guide/checkers/extensions.html>`_.

.. _default:

Default
-------

In the default configuration, the default configuration of ``flake8`` is used. For ``pylint``, the following checks are enabled:

.. message-table::
   default

Extension groups
----------------

EduLint provides convenience "bulk names" for groups of ``pylint`` messages. One flag enables multiple messages that have a common theme.

These can be enabled by specifying :link_option:`set-groups` (e.g. ``set-groups=enhancement,complexity``).

Enhancement
^^^^^^^^^^^

The ``enhancement`` extension groups contains those messages, that should be followed but it is not essential skill for a beginner:

.. message-table::
   enhancement

Python-specific
^^^^^^^^^^^^^^^

The ``python-specific`` extension group enables those messages that improve the code, but are specific to Python:

.. message-table::
   python-specific


Complexity
^^^^^^^^^^

The ``complexity`` extension group enables those messages that check for overly complex code but provide little guidance on how to fix it:

.. message-table::
   complexity
