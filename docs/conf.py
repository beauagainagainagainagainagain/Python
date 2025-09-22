from pathlib import Path

from sphinx_pyproject import SphinxConfig


ROOT = Path(__file__).resolve().parents[1]
project = SphinxConfig(ROOT / "pyproject.toml", globalns=globals()).name
