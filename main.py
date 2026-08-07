"""Entry point for the Fly-in drone routing simulation."""

import sys

from flyin.cli import main

try:
    main()
except Exception as e:
    print(e)
    sys.exit(1)
