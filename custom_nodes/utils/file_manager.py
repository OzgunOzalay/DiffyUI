"""
File manager utility for BIDS-compliant file handling.
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import nibabel as nib


class FileManager:
    """Manage file I/O and validation for BIDS datasets."""
    
    @staticmethod
    def validate_nifti(file_path: str) -> bool:
        """
        Validate that a file is a valid NIfTI file.
        
        Args:
            file_path: Path to NIfTI file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            img = nib.load(file_path)
            return img is not None
        except Exception:
            return False
    
    @staticmethod
    def ensure_directory(path: str):
        """
        Ensure a directory exists, create if it doesn't.
        
        Args:
            path: Directory path
        """
        Path(path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def copy_file(source: str, destination: str, overwrite: bool = False) -> bool:
        """
        Copy a file from source to destination.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite if destination exists
            
        Returns:
            True if successful, False otherwise
        """
        source_path = Path(source)
        dest_path = Path(destination)
        
        if not source_path.exists():
            return False
        
        if dest_path.exists() and not overwrite:
            return False
        
        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(source_path, dest_path)
            return True
        except Exception:
            return False
    
    @staticmethod
    def cleanup_temp_files(directory: str, pattern: str = "*"):
        """
        Clean up temporary files in a directory.
        
        Args:
            directory: Directory to clean
            pattern: File pattern to match
        """
        temp_dir = Path(directory)
        if temp_dir.exists():
            for file in temp_dir.glob(pattern):
                try:
                    if file.is_file():
                        file.unlink()
                except Exception:
                    pass
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes, or 0 if file doesn't exist
        """
        path = Path(file_path)
        if path.exists():
            return path.stat().st_size
        return 0
    
    @staticmethod
    def get_nifti_info(file_path: str) -> Optional[dict]:
        """
        Get information about a NIfTI file.
        
        Args:
            file_path: Path to NIfTI file
            
        Returns:
            Dictionary with file information or None if invalid
        """
        try:
            img = nib.load(file_path)
            return {
                "shape": img.shape,
                "affine": img.affine.tolist(),
                "header": dict(img.header),
                "dtype": str(img.get_data_dtype())
            }
        except Exception:
            return None
