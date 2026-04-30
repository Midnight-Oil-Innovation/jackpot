"""jackpot_schema — paths to the canonical LinkML schema artefacts.

The LinkML metadata schema and its generated JSON form ship as data
inside this package. Importers should reference the paths exposed here
rather than hard-coding `schema/schema/*.yaml` (the doubled-path
convention is preserved on disk for historical reasons but the import
contract is single-name).

Usage:
    from jackpot_schema import SCHEMA_YAML_PATH, SCHEMA_JSON_PATH
    yaml.safe_load(SCHEMA_YAML_PATH.read_text())
"""

from importlib.resources import files
from pathlib import Path

_SCHEMA_DIR: Path = Path(str(files("jackpot_schema").joinpath(""))).parent / "schema"

SCHEMA_YAML_PATH: Path = _SCHEMA_DIR / "jackpot_schema.yaml"
SCHEMA_JSON_PATH: Path = _SCHEMA_DIR / "jackpot_schema.json"
MAPPING_CONFIGS_DIR: Path = _SCHEMA_DIR / "mapping_configs"

__all__ = ["SCHEMA_YAML_PATH", "SCHEMA_JSON_PATH", "MAPPING_CONFIGS_DIR"]
