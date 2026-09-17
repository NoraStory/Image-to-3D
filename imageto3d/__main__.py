"""Allow ``python -m imageto3d`` to behave like the installed CLI."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
