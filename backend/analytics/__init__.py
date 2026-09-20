"""Read-only analytics for the weekly quant-manager report.

This package deliberately sits beside the existing import and dashboard paths.
It never writes to the production SQLite database.
"""

from __future__ import annotations

ANALYTICS_VERSION = "v2a"
