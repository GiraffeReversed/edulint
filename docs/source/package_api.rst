.. _package-api:

Package API
===========

Basic usage example
-------------------

.. code:: python

    from edulint import check_code

    # using default configuration
    _, problems = check_code(["/path/to/file.py"])

    # changing configuration; options are treated as if passed through the command line interface
    _, problems = check_code(["/path/to/file.py"], ["config-file=empty", "pylint=--enable=identical-if-branches"])

In each case, variable ``problems`` now contains a list of all detected :any:`Problem` instances.

If the detection does not behave as expected, the first element of the returned tuple (here ignored) contains detailed information on what exact configuration options were used.

.. warning::

    Encountered errors are logged to stderr using `loguru <https://loguru.readthedocs.io/en/stable/>`_. By default, the package API uses loguru's default settings, which also display INFO level logs, which edulint emits frequently. To get rid of these, change the minimal log level or redirect the logs to a different sink.

    This code changes the minimal log level to WARNING. Place it before the first call to :any:`check_code` to get rid of the INFO logs.

    .. code:: python

        from loguru import logger
        import sys

        logger.remove()
        logger.add(sys.stderr, level="WARNING")

Full reference
--------------

.. automodule:: edulint
    :members:
