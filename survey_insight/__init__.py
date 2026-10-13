"""AI Survey Insight package."""

import os

# Small/medium survey matrices are slower with dozens of OpenMP workers.
# Respect explicit deployment settings while keeping local defaults bounded.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(max(1, min(os.cpu_count() or 1, 8))))

from .pipeline import analyze_file, analyze_table

__all__ = ["analyze_file", "analyze_table"]
