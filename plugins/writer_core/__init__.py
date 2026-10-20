"""Shared local writing runtime; contains no DJ or fictional-world prompts."""
from pathlib import Path
import sys

# Source DJ launches run outside src/. Frozen apps bundle plagued_ai normally.
_source = Path(__file__).resolve().parents[2] / 'src'
if _source.is_dir() and str(_source) not in sys.path:
    sys.path.insert(0, str(_source))
