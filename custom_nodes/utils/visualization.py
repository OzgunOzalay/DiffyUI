"""
Visualization utilities for QC and image viewing.
"""

import numpy as np
from typing import Optional
import nibabel as nib


def get_slice_data(nifti_file: str, axis: int = 2, slice_idx: Optional[int] = None) -> np.ndarray:
    """
    Extract a slice from a NIfTI file for visualization.
    
    Args:
        nifti_file: Path to NIfTI file
        axis: Axis to slice along (0=x, 1=y, 2=z)
        slice_idx: Index of slice (None for middle slice)
        
    Returns:
        Slice data as 2D numpy array
    """
    try:
        img = nib.load(nifti_file)
        data = img.get_fdata()
        
        if slice_idx is None:
            slice_idx = data.shape[axis] // 2
        
        if axis == 0:
            return data[slice_idx, :, :]
        elif axis == 1:
            return data[:, slice_idx, :]
        else:  # axis == 2
            return data[:, :, slice_idx]
    except Exception:
        return np.array([])


def calculate_snr(dwi_data: np.ndarray, b0_idx: int = 0) -> float:
    """
    Calculate signal-to-noise ratio from DWI data.
    
    Args:
        dwi_data: 4D DWI data array
        b0_idx: Index of b0 volume
        
    Returns:
        SNR value
    """
    try:
        b0 = dwi_data[:, :, :, b0_idx]
        signal = np.mean(b0[b0 > 0])
        noise = np.std(b0[b0 > 0])
        
        if noise > 0:
            return signal / noise
        return 0.0
    except Exception:
        return 0.0
