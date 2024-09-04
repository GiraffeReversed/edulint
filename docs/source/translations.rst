Translating messages
====================

EduLint enables translating defect messages to different (natural) languages. This feature can also be used to change wording of selected messages. Currently, EduLint does not provide prepared translations to any other language, but it is possible to create and use own translations. For the sake of keeping the documentation in English, the examples here will show reworded messages, not messages translated to another language.

Message translation format
--------------------------

Translations are specified as lines :code:`<message id or symbol> = <translated text>`, for example :code:`unnecessary-pass = "You shall not (use) pass (here)"` (the original message is :code:`Unnecessary pass statement`).

For messages that show snippets of the checked code, EduLint is able to extract these snippets and place them into the translations at specified spots. For example, :code:`redefined-builtin` detector could show message :code:`"Redefining built-in sum"`, where :code:`sum` is the specific name of the redefined function used in the code. A translation for this message could be :code:`redefining-builtin = "Name {} shadows a built-in function. Choose another name to avoid bugs and confusion."` The built-in name EduLint extracts from the original message will be put in place of the :code:`{}` Python's :code:`.format` method is used to pass the extracts to the new message, so it is also possible to change the order, or use only some arguments.

Some messages do not only use code snippets to dynamically create the message, some also add words based on the code. For example, the message for :code:`identical-if-branches-part` says :code:`Identical code inside all if's branches, move %d lines %s the if.`, where :code:`%s` can be :code:`before` or :code: `after`. In such case, the translation can look as follows:

.. code::

    identical-if-branches-part = "There are {} identical lines {} of the if branches."
    translated_extracts.identical-if-branches-part.2 = { before = "at the start", after = "at the end" }

The number after the checker name indicates which of the extracts should the extract translation apply to. Here, the extracts are numbered from one.

Flake8's rules do not have symbol, only ID, so the code is used to pair the translation, e.g., :code:`E501 = "line is definitely too long"`. Pylint's message IDs can also be used for Pylint's messages.

Setting language translations
-----------------------------

The translations can either be specified in a dedicated language file, or directly inside :ref:`a custom configuration file <configuration files>`.

A dedicated language file is a TOML containing just translation pairs in the format described above, for example:

.. code:: toml

    unnecessary-pass = "You shall not (use) pass (here)"
    redefining-builtin = "Name {} shadows a built-in function. Choose another name to avoid bugs and confusion."
    identical-if-branches-part = "There are {} identical lines {} of the if branches."
    translated_extracts.identical-if-branches-part.2 = { before = "at the start", after = "at the end" }
    E501 = "line is definitely too long"

A language file to use can be set using the :link_option:`language-file` option. The option can be set by any of the means described in the :ref:`configuration section <configuration>`.

The translations can also be placed directly into a configuration file. For example:

.. code:: toml

    [pylint]
    enable = ["unnecessary-pass", "redefining-builtin", "identical-if-branches-part"]

    [flake8]
    select = "E501"

    [language-translations]
    unnecessary-pass = "You shall not (use) pass (here)"
    redefining-builtin = "Name {} shadows a built-in function. Choose another name to avoid bugs and confusion."
    identical-if-branches-part = "There are {} identical lines {} of the if branches."
    translated_extracts.identical-if-branches-part.2 = { before = "at the start", after = "at the end" }
    E501 = "line is definitely too long"

To create the translations, it is useful to know the original message patterns. For EduLint, the patterns can be found in the :ref:`checkers' documentation <checkers>`. Pylint's patterns can be found in `Pylint's documentation <https://pylint.readthedocs.io/en/stable/user_guide/messages/messages_overview.html>`_. Flake8's patterns are not well documented, so the best resource is probably `the list that EduLint uses internally <https://raw.githubusercontent.com/GiraffeReversed/edulint/main/edulint/config/raw_flake8_patterns.py>`_.

.. note::

    If EduLint emits a message for which it has no translation, it will use the original (English) message.

.. note::

    Currently, it is not possible to set translations for :ref:`explanations <explanations>`.