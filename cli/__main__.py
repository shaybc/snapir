"""Expose the migration CLI through python -m cli."""

from cli.main import main

raise SystemExit(main())
