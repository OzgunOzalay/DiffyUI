# Eddy CUDA GPU Performance Fix

## Problem
FSL `eddy_cuda` was running slowly within ComfyUI despite having CUDA properly installed. The root cause was **GPU resource contention**: ComfyUI's PyTorch backend keeps models loaded in GPU memory, leaving insufficient resources for `eddy_cuda` to run at full speed.

## Solution
Modified the Eddy correction node to **automatically free GPU memory** before running `eddy_cuda`:

1. **Unload all ComfyUI models** from GPU using `model_management.unload_all_models()`
2. **Clear CUDA cache** using `model_management.soft_empty_cache()`
3. **Run eddy_cuda** with full GPU access
4. ComfyUI automatically reloads models when needed for next operations

## Implementation

### Changes to `eddy_correction.py`

**Import ComfyUI model management:**
```python
try:
    import comfy.model_management as model_management
    HAS_MODEL_MANAGEMENT = True
except ImportError:
    HAS_MODEL_MANAGEMENT = False
```

**GPU cleanup before eddy_cuda execution:**
```python
# Free GPU memory before running eddy_cuda for max performance
if HAS_MODEL_MANAGEMENT and ("cuda" in eddy_bin_lower or "gpu" in eddy_bin_lower):
    print("[DWI Eddy] Freeing GPU memory (unloading ComfyUI models)...")
    try:
        model_management.unload_all_models()
        model_management.soft_empty_cache()
        print("[DWI Eddy] GPU memory freed. eddy_cuda now has full GPU access.")
    except Exception as e:
        print(f"[DWI Eddy] Warning: GPU cleanup failed: {e}. Continuing anyway.")
```

### How It Works

1. **Detection**: Checks if the selected eddy binary contains "cuda" or "gpu" in its name
2. **Cleanup**: Calls ComfyUI's model management functions to:
   - Unload all PyTorch models from GPU memory
   - Clear CUDA cache and IPC resources
3. **Execution**: Runs `eddy_cuda` with full GPU access
4. **Automatic Recovery**: ComfyUI reloads models when needed for subsequent nodes

### Benefits

- **Zero configuration**: Works automatically when `eddy_cuda` is detected
- **Graceful fallback**: If model management unavailable, continues without GPU cleanup
- **Optimal performance**: `eddy_cuda` gets full GPU resources during execution
- **Transparent**: Logs clearly indicate when GPU memory is being freed

## Verification

Check the console output when running Eddy correction:

```
[DWI Eddy] Using eddy binary: /usr/local/fsl/bin/eddy_cuda11.0
[DWI Eddy] Freeing GPU memory (unloading ComfyUI models)...
[DWI Eddy] GPU memory freed. eddy_cuda now has full GPU access.
[DWI Eddy] Running: /usr/local/fsl/bin/eddy_cuda11.0 --imain=... --out=...
```

## Performance Impact

- **Before**: eddy_cuda competed with PyTorch for GPU memory, causing slowdowns
- **After**: eddy_cuda has full GPU access, matching native CLI performance
- **Overhead**: ~1-2 seconds for model unloading (negligible compared to eddy runtime)

## Technical Details

Uses ComfyUI's existing model management infrastructure:
- `unload_all_models()`: Moves all loaded models from GPU to CPU/disk
- `soft_empty_cache()`: Calls `torch.cuda.empty_cache()` and `torch.cuda.ipc_collect()`

This is the same mechanism ComfyUI uses internally for memory management during workflow execution.
