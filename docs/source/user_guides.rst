User guides
-----------

Student
^^^^^^^

To run EduLint, use the :ref:`the online instance <online instance>` or :ref:`the Thonny plugin <thonny plugin>`. `Thonny <https://thonny.org/>`_ is an integrated development environment for novice programmers that we recommend if you are starting to learn programming.

If you were asked to use a specific configuration, make sure that the file with your code contains a line like :code:`# edulint: config-file=<the-configuration-name>`.

Teacher
^^^^^^^

EduLint can provide feedback for a lot of different code quality defects, not all of which may be relevant for your students. Therefore, a good first step to using EduLint in class is to choose which set of defects (described in a configuration files) the students should use. Several presets do exist, see them `here <packaged configurations>`.

Choosing configuration
""""""""""""""""""""""

You can either just skip this step and stick with :ref:`the default configuration <default>`, pick another one of :ref:`the packaged configurations <packaged configurations>` or :ref:`create your own <create config file>`. Packaged configurations are easier to use (no need to deliver a custom configuration to the students), but less flexible. Custom configuration is very flexible (there are hundreds of detectors), but can take substantial time to create and needs to be distributed to students separately.

Distributing the configuration
""""""""""""""""""""""""""""""

If you choose a non-default configuration, then you need to setup EduLint to use the correct configuration. The most convenient way is to set the :link_option:`config-file` option in the linted file (:ref:`detailed description here <set config file>`).

Then you need to instruct the students to put the configuration line into the file they create, or if you are already distributing solution templates to the student, you can put the configuration line directly into the solution template like so:

.. code:: python

    # edulint: config-file=<selected-config-file>

    # write function returning how many 'a's and 'A's are there in the passed string.
    def count_a(text):
        return 0  # implement this

The configuration line can be anywhere in the file. More on configuring through in-file comments can be found :ref:`here <infile configuration>`.

Students use EduLint
""""""""""""""""""""

There are several ways in which the students themselves can use EduLint, described in section `Student`_.

Running EduLint for evaluation
""""""""""""""""""""""""""""""

To evaluate students, we recommend :ref:`running EduLint locally <local installation>`.

You may want to enforce that students implement all of EduLint's feedback generated based on the configuration you selected. For evaluation, we recommend setting the :link_option:`ignore-infile-config-for` to :code:`all`. This way, EduLint will report comments used to suppress Flake8's and Pylint's messages by using :code:`# noqa` and :code:`# pylint: disable=all`. Students will therefore not be able to suppress all reports, there will always be at least the report of these comments. But careful, the student will still be able to change the *number* of reported defects, just not bring it down to zero.

The command used for evaluation should look as follows:

.. code:: bash

    python3 -m edulint check -o config-file=<selected-config-file> -o ignore-infile-config-for=all <file-or-directory>

It is necessary to specify the config file to use, even if it is already specified in the checked file itself. The :code:`ignore-infile-config-for=all` will ignore even EduLint's configuration.

EduLint terminates with a non-zero code if it encountered a defect during the linting process or if there was an error.

Researcher
^^^^^^^^^^

EduLint can be used for easily reproducible experiments. A :code:`requirements.txt` specifying package versions and :ref:`EduLint's configuration file <configuration files>`, together with a dataset are enough to reproduce the reported defects.

EduLint will automatically use any installed flake8 plugins, even if the plugin is not in EduLint's dependencies. Use of Pylint plugins needs to be set through Pylint's :code:`load-plugins` option. Then, you also need to use a configuration file that enables checks from these plugins.
