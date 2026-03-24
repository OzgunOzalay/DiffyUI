"""
Helper module to import utils from custom_nodes directory.
This ensures imports work correctly regardless of how ComfyUI loads the modules.
"""

import sys
import importlib.util
from pathlib import Path

# Get the custom_nodes directory
_custom_nodes_dir = Path(__file__).parent.parent

# Add to path if not already there
if str(_custom_nodes_dir) not in sys.path:
    sys.path.insert(0, str(_custom_nodes_dir))

# Try normal import first
try:
    from utils.bids_handler import BIDSHandler
    from utils.system_executor import get_executor
    from utils.file_manager import FileManager
    from utils.cache_manager import CacheManager
except ImportError:
    # Fallback: direct file loading
    _utils_path = _custom_nodes_dir / "utils"

    # Load bids_handler
    _bids_spec = importlib.util.spec_from_file_location(
        "bids_handler",
        _utils_path / "bids_handler.py"
    )
    _bids_module = importlib.util.module_from_spec(_bids_spec)
    _bids_spec.loader.exec_module(_bids_module)
    BIDSHandler = _bids_module.BIDSHandler

    # Load system_executor
    _system_spec = importlib.util.spec_from_file_location(
        "system_executor",
        _utils_path / "system_executor.py"
    )
    _system_module = importlib.util.module_from_spec(_system_spec)
    _system_spec.loader.exec_module(_system_module)
    get_executor = _system_module.get_executor

    # Load file_manager
    _file_spec = importlib.util.spec_from_file_location(
        "file_manager",
        _utils_path / "file_manager.py"
    )
    _file_module = importlib.util.module_from_spec(_file_spec)
    _file_spec.loader.exec_module(_file_module)
    FileManager = _file_module.FileManager

    # Load cache_manager
    _cache_spec = importlib.util.spec_from_file_location(
        "cache_manager",
        _utils_path / "cache_manager.py"
    )
    _cache_module = importlib.util.module_from_spec(_cache_spec)
    _cache_spec.loader.exec_module(_cache_module)
    CacheManager = _cache_module.CacheManager

def _is_upstream_error(value: str) -> bool:
    """Return True if value looks like a propagated error string rather than a real path."""
    if not value:
        return False
    # Real paths on Linux start with '/'
    return not str(value).startswith("/")


__all__ = ['BIDSHandler', 'get_executor', 'FileManager', 'CacheManager', '_is_upstream_error']
