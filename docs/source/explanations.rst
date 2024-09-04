.. _explanations:

Message Explanations
--------------------

EduLint can display explanations and examples of defective and fixed code for many of the defects. To show the explanation for, for example, the message with ID R6201, run

.. code-block::

    python3 -m edulint explain R6201

This command outputs the following text to the standard output.

.. code-block::

    ### Why is it a problem?
    Having unnecessary conditions in code makes the code more cluttered and therefore harder to understand.

    ### How to solve it?
    A condition that returns bool in both branches can be simplified even if it contains a logical statement.

    ```py
    def problematic(a: bool, b: bool) -> bool:
        if a or b:
            return True
        else:
            return False
    ```

    ```py
    def good(a: bool, b: bool) -> bool:
        return a or b
    ```

    **Danger:** if the condition is not a `bool` value (e.g. `if lst`), then returning the value directly is not equivalent. In such case, take care to change the condition to an expression that does evaluate to bool (e.g. `len(lst) > 0`).


It is also possible to request explanation for multiple messages:

.. code::

    python3 -m edulint explain R6201 C2401

EduLint can also provide the explanation as a JSON by passing the :code:`--json` option:

.. code::

    python3 -m edulint explain R6201 --json

This command outputs the following text to the standard output.

.. code-block::

    {
      "explanations": {
        "R6201": {
          "why": "Having unnecessary conditions in code makes the code more cluttered and therefore harder to understand.",
          "examples": "A condition that returns bool in both branches can be simplified even if it contains a logical statement.\n\n```py\ndef problematic(a: bool, b: bool) -> bool:\n    if a or b:\n        return True\n    else:\n        return False\n```\n\n```py\ndef good(a: bool, b: bool) -> bool:\n    return a or b\n```\n\n**Danger:** if the condition is not a `bool` value (e.g. `if lst`), then returning the value directly is not equivalent. In such case, take care to change the condition to an expression that does evaluate to bool (e.g. `len(lst) > 0`).\n"
        }
      }
    }
