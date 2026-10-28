# Allows python3 -m md_anchor_lint to run the command line tool.

import sys

from .cli import main

sys.exit(main())
