How do I run EduLint?
    If you do not want to install anything, you can try EduLint `here <https://edulint.com/editor/umime_count_a>`_. Otherwise, see install instructions :ref:`here <run edulint#local-installation>`.

What does EduLint do?
   EduLint is an educational linter for Python code. It provides feedback on code quality, style, and common mistakes to help students improve their programming skills. EduLint can be customized with different configurations to suit various educational needs. For the complete list of defects it detects, see :ref:`here <checkers>`.

How can I use EduLint?
   You can run it locally through the command line or using the package API, or you can host a web API server. For more information, read :ref:`the user guides <user guides>`.

What configuration should I use?
    If you are unsure, start with :ref:`the default configuration <default>`. If you want more control, you can pick one of :ref:`the packaged configurations <packaged configurations>` or :ref:`create your own <create config file>`. For more information on choosing and distributing configurations, see :ref:`here <user guides#choosing-configuration>`.

    There is no easy answer. Try running some configuration on some sample codes and see what you like best.

How do I stop students from disabling reports via Pylint's disable, Flake8's noqa comments or EduLint's own configuration comments?
   Set the :link_option:`ignore-infile-config-for` option to :code:`all` when running EduLint. The disabled defects **will stay disabled** (Pylint has no option to force ignore disable comments), but EduLint will emit an additional defect which you can check for.
