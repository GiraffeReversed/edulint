User guides
-----------

Student
^^^^^^^

To run EduLint, use the :ref:`the online instance <online instance>` or :ref:`the Thonny plugin <thonny plugin>`. Thonny <https://thonny.org/> is an integrated development environment for novice programmers that we recommend if you are starting to learn programming.

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

Then you need to instruct the students to put the configuration line into the file they create, or if you are already distributing solution templates to the student, you can put the configuration line directly into the template.

.. Todo: example solution template code

Students use EduLint
""""""""""""""""""""

There are several ways in which the students themselves can use EduLint, described in section `Student`_.

Running EduLint for evaluation
""""""""""""""""""""""""""""""

To evaluate students, we recommend :ref:`running EduLint locally <local installation>`.

If you want to enforce that students implement all of EduLints feedback that is generated based on a given configuration, we recommend setting the :link_option:`ignore-infile-config-for` to :code:`all`. This way, the students will not be able to get a clean pass by turning off the checks by infile configuration of their own rather than fixing the defects. Even with the option set, the student may be able to change the *number* of reported defects, but will not be able to bring it to zero. Depending on which means of disabling detectors the student uses, an unfixed defect may end up not reported, but instead, EduLint will issue a report of using disallowed configuration option.

.. todo example command

EduLint terminates with a non-zero code if it encountered a defect during the linting process or if there was an error.

Researcher
^^^^^^^^^^

EduLint can be used for easily reproducible experiments. A :code:`requirements.txt` specifying package versions and :ref:`EduLint's configuration file <configuration files>`, together with a dataset are enough to reproduce the reported defects.

EduLint will automatically use any installed flake8 plugins, even if the plugin is not in EduLint's dependencies. Use of Pylint plugins needs to be set through Pylint's :code:`load-plugins` option. Then, you also need to use a configuration file that enables checks from these plugins.
