Custom changes
^^^^^^^^^^^^^^

Custom checkers
---------------


EduLint provides custom checkers to report more problems frequent in novice code. It does so by extending Pylint with extra plugins. The checkers can therefore be invoked in the standard Pylint manner (e.g. using :code:`--enable` or :code:`--disable`) on the Edulint's :link_option:`pylint` option.

.. checkers-block::

Tweakers
--------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Tweaked message
     - Effects
   * - :link_pylint:`disallowed-name`
     -
      * when :link_option:`allowed-onechar-names` is enabled, complains on all single-character variable names, encouraging choosing a different name
  ..  * - :link_pylint:`consider-using-in`
  ..    -
  ..     * if all enumerated values are all single characters, suggests joining them into string rather than using a tuple (:code:`ch in ".,?"` instead of :code:`ch in ('.', ',', '?')`)
