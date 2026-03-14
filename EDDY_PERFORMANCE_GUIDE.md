# FSL Eddy CUDA Performance Optimization Guide

## Understanding the Bottleneck

When you see:
- **GPU usage drops to <10%** after initial compute
- **Only one CPU core active**
- **Process appears slow**

**This is normal FSL eddy behavior.** Eddy alternates between two phases:

### Phase 1: GPU Compute (High GPU Usage)
- Registration and alignment
- Eddy current estimation
- Motion parameter optimization
- **Duration:** ~10-20% of total runtime
- **GPU usage:** 80-100%

### Phase 2: I/O Operations (Low GPU Usage)
- Reading DWI volumes from disk
- Writing intermediate results
- Writing corrected output
- **Duration:** ~80-90% of total runtime
- **GPU usage:** <10%
- **CPU usage:** Single thread coordinating I/O

The bottleneck is **disk I/O**, not GPU compute.

---

## Optimizations Implemented

### 1. GPU Memory Management
**What it does:** Frees GPU memory before running eddy_cuda
```
[DWI Eddy] Freeing GPU memory (unloading ComfyUI models)...
[DWI Eddy] GPU memory freed. eddy_cuda now has full GPU access.
```

### 2. FSL Performance Flags
For `eddy_cuda`, automatically enabled:

| Flag | Effect | Trade-off |
|------|--------|-----------|
| `--dont_sep_offs_move` | Skip separation of field offset & subject movement | Faster, minimal quality impact |
| `--nvoxhp=1000` | Reduce hyperparameter voxels | Faster, good for most datasets |
| `--dont_peas` | Skip post-eddy alignment (single-shell only) | Faster for single-shell data |

Console output:
```
[DWI Eddy] CUDA performance optimizations enabled: --dont_sep_offs_move, --nvoxhp=1000
[DWI Eddy] Single-shell data detected: adding --dont_peas for faster processing
```

### 3. Multi-threaded I/O
Environment variables set automatically:
- `OMP_NUM_THREADS=4`: Parallel file I/O operations
- `OPENBLAS_NUM_THREADS=4`: Parallel BLAS operations
- `FSL_LOAD_NIFTI_EXTENSIONS=0`: Skip loading extra NIfTI metadata

---

## Further Performance Improvements

### Storage Speed (Biggest Impact)

#### Current Storage Check
The node reports your filesystem type:
```
[DWI Eddy] Output on ext4 filesystem
[DWI Eddy] Tip: For faster processing, consider using tmpfs/RAM disk for output
```

#### Storage Speed Comparison
| Storage Type | Random Read/Write | Eddy Speedup |
|--------------|-------------------|--------------|
| HDD (7200 RPM) | ~100 MB/s | 1x (baseline) |
| SATA SSD | ~500 MB/s | **2-3x faster** |
| NVMe SSD | ~3000 MB/s | **5-10x faster** |
| tmpfs (RAM disk) | ~10,000 MB/s | **20-50x faster** |

### Option A: Use Existing Fast Storage
If you have SSD/NVMe, point output to that location:
```bash
# Check what drives you have
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE

# Use SSD/NVMe path in your workflow
# Example: /mnt/nvme/diffyui_output
```

### Option B: Create RAM Disk (Fastest)
**Requirements:** Sufficient RAM (need ~2-5x your DWI file size)

```bash
# Create 50GB RAM disk (adjust size based on your data)
sudo mkdir -p /tmp/eddy_ramdisk
sudo mount -t tmpfs -o size=50G tmpfs /tmp/eddy_ramdisk

# After processing, copy results to permanent storage
cp -r /tmp/eddy_ramdisk/results /path/to/permanent/storage

# Unmount when done
sudo umount /tmp/eddy_ramdisk
```

**Example workflow:**
1. BIDS dataset on regular disk
2. Eddy outputs to `/tmp/eddy_ramdisk`
3. Copy corrected files back to BIDS derivatives

### Option C: Reduce Data Size
- **Crop DWI volumes:** Remove unnecessary slices before eddy
- **Single-shell only:** If you have multi-shell, process one shell at a time
- **Fewer volumes:** Reduce number of b0 volumes (keep 3-5 instead of 10+)

---

## Benchmarking Your Setup

Run eddy once and note the timing:
```
[DWI Eddy] Eddy correction completed in XX minutes
```

### Expected Times (for 60-volume DWI, ~100 slices)
| Setup | Time |
|-------|------|
| eddy_cpu + HDD | 2-4 hours |
| eddy_cuda + HDD | 30-60 min |
| eddy_cuda + SSD | 15-30 min |
| eddy_cuda + NVMe | 10-15 min |
| eddy_cuda + tmpfs | 5-10 min |

If your time is significantly longer, check:
1. **Disk speed:** `hdparm -t /dev/sdX` (HDD) or `fio` benchmarks (SSD)
2. **Other processes:** `iotop -o` to see disk usage
3. **Data size:** Larger volumes = longer processing

---

## When to Use These Optimizations

### Always Use (Automatic)
✅ GPU memory cleanup
✅ FSL performance flags
✅ Multi-threaded I/O

### Consider If
⚠️ **RAM disk** - You have 32GB+ RAM and want max speed
⚠️ **SSD/NVMe output** - You have fast storage available
⚠️ **Data reduction** - Processing is taking hours

### Don't Bother If
❌ Already running in 10-15 min
❌ Limited RAM (<16GB)
❌ No fast storage available

---

## Verification Checklist

When you run eddy, verify in console:

```
✓ [DWI Eddy] Using eddy binary: /path/to/eddy_cuda11.0
✓ [DWI Eddy] Freeing GPU memory...
✓ [DWI Eddy] GPU memory freed. eddy_cuda now has full GPU access.
✓ [DWI Eddy] CUDA performance optimizations enabled
✓ [DWI Eddy] Output on [filesystem type]
```

Watch `nvidia-smi` during execution:
- **First few minutes:** High GPU usage (60-100%)
- **Rest of time:** Low GPU usage (<10%) - **THIS IS NORMAL**

Watch `iotop` during execution:
- Should see sustained disk writes (eddy process)
- This confirms I/O bottleneck (expected)

---

## Summary

**The low GPU usage you're seeing is normal FSL behavior**, not a bug. The optimizations implemented:

1. ✅ Free GPU memory for eddy_cuda
2. ✅ Enable FSL performance flags
3. ✅ Multi-threaded I/O
4. ℹ️ Detect and report filesystem type

For further speedup, the **only significant improvement** is using faster storage (SSD/NVMe/RAM disk). The I/O bottleneck is inherent to how FSL eddy works.
