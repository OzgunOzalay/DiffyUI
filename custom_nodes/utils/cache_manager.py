"""
DiffyUI Cache Manager - Parameter-aware skip/cache system.

Avoids re-running expensive neuroimaging tools when outputs already exist
with identical parameters. Cache files are stored per output directory.
"""

import json
import os
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timezone

DIFFYUI_VERSION = "0.4.0"


class CacheManager:

    @staticmethod
    def build_params_for_hash(kwargs: dict, file_keys: list) -> dict:
        """
        Build a parameter dict suitable for hashing.

        Keys in file_keys get: {"path": str, "mtime": float, "size": int}
        (for directories, size=0 and mtime of the dir itself is used)
        All other keys get: literal scalar values.
        Missing/empty file paths get: ""
        """
        params = {}
        for key, value in kwargs.items():
            if key in file_keys:
                path_str = str(value).strip() if value else ""
                if path_str:
                    p = Path(path_str)
                    try:
                        if p.exists():
                            stat = p.stat()
                            # Use path + size only (no mtime): mtime changes when a node
                            # rewrites an identical file, causing spurious downstream cache misses.
                            params[key] = {
                                "path": str(p.resolve()),
                                "size": stat.st_size if p.is_file() else 0,
                            }
                        else:
                            params[key] = {"path": path_str, "size": 0}
                    except Exception:
                        params[key] = {"path": path_str, "size": 0}
                else:
                    params[key] = ""
            else:
                params[key] = value
        return params

    @staticmethod
    def compute_param_hash(params: dict) -> str:
        """Compute SHA-256 hash of JSON-encoded params (sorted keys)."""
        encoded = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()

    @classmethod
    def check_cache(cls, cache_path, node_name: str, param_hash: str,
                    expected_outputs: list, files_to_check: list = None):
        """
        Check if cached outputs are valid.

        Returns (True, cached_output_list) on hit, (False, []) on miss.

        A hit requires:
        - Cache file exists and is valid JSON
        - _diffyui_version matches DIFFYUI_VERSION
        - param_hash matches stored hash
        - All paths in files_to_check (or all non-empty expected_outputs) exist on disk
        - Number of stored outputs matches len(expected_outputs)

        Args:
            cache_path: Path to .diffyui_cache.json
            node_name: Node identifier string (e.g. "DWIDenoise")
            param_hash: Hash computed from current inputs
            expected_outputs: List of output paths (empty strings for disabled optional outputs)
            files_to_check: Optional subset of paths to verify existence; defaults to all
                            non-empty entries in expected_outputs.
        """
        cache_path = Path(cache_path)
        if not cache_path.exists():
            return False, []

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
        except Exception:
            return False, []

        # Version check — bumping DIFFYUI_VERSION invalidates all caches
        stored_version = data.get("_diffyui_version")
        if stored_version != DIFFYUI_VERSION:
            print(f"[CacheManager] {node_name}: version mismatch (stored={stored_version}, current={DIFFYUI_VERSION})")
            return False, []

        nodes = data.get("nodes", {})
        entry = nodes.get(node_name)
        if not entry:
            print(f"[CacheManager] {node_name}: no cache entry found")
            return False, []

        # Hash check
        stored_hash = entry.get("param_hash")
        if stored_hash != param_hash:
            print(f"[CacheManager] {node_name}: hash mismatch (stored={stored_hash[:8]}..., current={param_hash[:8]}...)")
            stored_inputs = entry.get("inputs", {})
            if stored_inputs:
                print(f"[CacheManager] {node_name}: stored inputs:")
                for k, sv in stored_inputs.items():
                    print(f"[CacheManager]   {k}: {sv}")
            return False, []

        cached_outputs = entry.get("outputs", [])
        if not cached_outputs:
            print(f"[CacheManager] {node_name}: no outputs in cache entry")
            return False, []

        # Length check — if outputs changed (code update), force re-run
        if len(cached_outputs) != len(expected_outputs):
            print(f"[CacheManager] {node_name}: output count mismatch (stored={len(cached_outputs)}, expected={len(expected_outputs)})")
            return False, []

        # File/dir existence check
        paths_to_verify = (
            files_to_check
            if files_to_check is not None
            else [o for o in expected_outputs if o]
        )
        for p in paths_to_verify:
            if p and not Path(p).exists():
                print(f"[CacheManager] {node_name}: output missing on disk: {p}")
                return False, []

        print(f"[CacheManager] {node_name}: cache HIT")
        return True, cached_outputs

    @classmethod
    def update_cache(cls, cache_path, node_name: str, param_hash: str,
                     inputs_snapshot: dict, output_paths: list):
        """
        Atomically write/update a cache entry.

        Uses tempfile + os.replace() for atomic writes. Always writes
        DIFFYUI_VERSION. Version mismatch on load causes a full cache reset.
        """
        cache_path = Path(cache_path)

        # Load existing cache (reset on version mismatch)
        data = {}
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                if data.get("_diffyui_version") != DIFFYUI_VERSION:
                    data = {}
            except Exception:
                data = {}

        data["_version"] = 1
        data["_diffyui_version"] = DIFFYUI_VERSION
        if "nodes" not in data:
            data["nodes"] = {}

        data["nodes"][node_name] = {
            "param_hash": param_hash,
            "inputs": inputs_snapshot,
            "outputs": output_paths,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(cache_path.parent),
                prefix=".diffyui_cache_tmp_",
                suffix=".json",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                os.replace(tmp_path, str(cache_path))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            print(f"[CacheManager] Warning: Could not write cache to {cache_path}: {e}")
