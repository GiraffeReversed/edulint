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

    python<version> -m pip install edulint

.. note::
   EduLint needs Python version at least 3.7 to work.

Run EduLint locally
^^^^^^^^^^^^^^^^^^^

To start using EduLint, open an interactive shell and run: 

.. code::

   python<version> -m edulint path/to/code/to/check.py

Overview
--------

EduLint wraps around `Pylint <https://pylint.pycqa.org/>`_ and `Flake8 <https://flake8.pycqa.org/>`_, allowing for separate configuration of each of the tools. Most importantly, it provides a reasonable default and convenience configurations for check that we deemed useful for beginning programmers.

As of now, it is only possible to configure the tool by augmenting the checked source with lines beginning with :python:`# edulint`, with the configuration applying to that file only. I intend to make it possible to configure via CLI and possibly a configuration file.

The tool also provides tweakers, which filter out or alter the checkers' messages.

Configuration
-------------

EduLint enables configuring performed checks by inserting lines into the checked source code. The lines start with ``# edulint:``, following by values in one of the following forms: ``<option-name>`` for options that do not take an argument and either ``<option-name>=<value-without-spaces>`` or ``<option-name>="<value-with-spaces>"`` for options that do take an argument.

Options
^^^^^^^

Currently available options are as follows:

.. options::

Examples
^^^^^^^^

.. code::

   # edulint: enhancement
   # edulint: pylint=--enable=no-self-use

It is also possible to combine multiple options on one line:

.. code::

   # edulint: python-spec allowed-onechar-names=ijk

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

Enhancement
""""""""""""

The flag `enhancement` enables the following checks:

.. message-table::
   enhancement

Python-spec
""""""""""""

The flag `python-spec` enables the following checks:

.. message-table::
   python-spec


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
   * - :link_pylint:`consider-using-in`
     -
      * if all enumerated values are all single characters, suggests joining them into string rather than using a tuple (:code:`ch in ".,?"` instead of :code:`ch in ('.', ',', '?')`)

.. Indices and tables
.. ------------------

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
