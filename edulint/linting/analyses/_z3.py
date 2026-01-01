import sys
import os
from loguru import logger


class _MissingZ3:
    def __getattr__(self, _name):
        python_executable = sys.executable or (
            "python" if os.name == "nt" else "python3"
        )  # nt is Windows
        logger.critical(
            f"Z3 support is not installed. Install it with: {python_executable} -m pip install --user edulint[z3]"
        )
        sys.exit(32)


try:
    import z3  # pyright: ignore[reportMissingImports]

    z3.ArithRef
except (ImportError, AttributeError):
    z3 = _MissingZ3()
