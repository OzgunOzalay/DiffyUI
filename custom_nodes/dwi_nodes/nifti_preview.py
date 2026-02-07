"""
NIfTI Preview Node - Preview NIfTI files using Python (nibabel + matplotlib).
Generates 3-panel overview (axial, coronal, sagittal) screenshots.
Displays preview directly in the node (like ComfyUI's Preview Image).
"""

import numpy as np
from pathlib import Path
import os
import uuid
import time

# Import ComfyUI's folder management (only available inside ComfyUI)
try:
    import folder_paths
    HAS_FOLDER_PATHS = True
except ImportError:
    HAS_FOLDER_PATHS = False
    folder_paths = None

# Import utils using helper module
try:
    import nibabel as nib
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib import cm
    import torch
    HAS_DEPS = True
except ImportError as e:
    HAS_DEPS = False
    IMPORT_ERROR = str(e)


class NIfTIPreviewNode:
    """
    NIfTI Preview Node - Uses Python (nibabel + matplotlib) to create 3-panel overview screenshots.
    """
    
    def __init__(self):
        print(f"[NIfTI Preview] Node initialized!")
        # Force execution by making it an output node
        # IMAGE outputs will display automatically in ComfyUI
    
    @classmethod
    def INPUT_TYPES(cls):
        print(f"[NIfTI Preview] INPUT_TYPES called")
        return {
            "required": {
                "nifti_file": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Path to NIfTI file (.nii or .nii.gz)"
                }),
            },
            "optional": {
                "json_file": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Path to JSON sidecar file (optional, for orientation info)"
                }),
                "volume_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "tooltip": "Volume index for 4D data (0 for first volume or 3D data)"
                }),
                "output_size": (["512x384", "1024x768", "2048x1536"], {
                    "default": "1024x768",
                    "tooltip": "Output image size (width x height)"
                }),
                "colormap": (["grayscale", "hot", "viridis", "jet"], {
                    "default": "grayscale",
                    "tooltip": "Colormap for visualization"
                }),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("preview",)
    FUNCTION = "preview_nifti"
    CATEGORY = "DWI"
    DESCRIPTION = "Preview NIfTI file using Python (3-panel overview: axial, coronal, sagittal). Shows preview directly in node."
    OUTPUT_NODE = True  # Enable built-in preview display
    
    def preview_nifti(
        self, 
        nifti_file: str,
        json_file: str = "",
        volume_index: int = 0,
        output_size: str = "1024x768",
        colormap: str = "grayscale"
    ):
        """
        Preview a NIfTI file by creating a 3-panel overview using Python.
        
        Args:
            nifti_file: Path to NIfTI file
            volume_index: Volume index for 4D data
            output_size: Output image size
            colormap: Colormap for visualization
            
        Returns:
            Image array in ComfyUI format [1, H, W, 3] (RGB)
        """
        print(f"[NIfTI Preview] ===== FUNCTION CALLED =====")
        print(f"[NIfTI Preview] Input file parameter: {repr(nifti_file)}")
        print(f"[NIfTI Preview] Input type: {type(nifti_file)}")
        
        if not HAS_DEPS:
            error_msg = f"Missing dependencies: {IMPORT_ERROR}. Install: pip install nibabel matplotlib Pillow"
            print(f"[NIfTI Preview] ERROR: {error_msg}")
            error_image = np.zeros((1, 512, 384, 3), dtype=np.uint8)
            return (error_image,)
        
        try:
            print(f"[NIfTI Preview] ===== STARTING PREVIEW =====")
            print(f"[NIfTI Preview] Input file: {nifti_file}")
            
            # Validate file path
            if not nifti_file or not nifti_file.strip():
                print(f"[NIfTI Preview] ERROR: NIfTI file path is empty!")
                raise ValueError("NIfTI file path is empty")
            
            # Handle comma-separated paths (take first)
            file_path = nifti_file.strip()
            if "," in file_path:
                file_path = file_path.split(",")[0].strip()
                print(f"[NIfTI Preview] Multiple paths detected, using first: {file_path}")
            
            nifti_path = Path(file_path)
            print(f"[NIfTI Preview] Resolved path: {nifti_path}")
            print(f"[NIfTI Preview] Path exists: {nifti_path.exists()}")
            
            if not nifti_path.exists():
                raise ValueError(f"NIfTI file not found: {nifti_path}")
            
            # Load NIfTI file
            print(f"[NIfTI Preview] Loading NIfTI file...")
            try:
                img = nib.load(str(nifti_path))
                # Use memmap=False to load into memory (safer for large files)
                data = np.array(img.get_fdata(caching='unchanged'))
                print(f"[NIfTI Preview] Data shape: {data.shape}, dtype: {data.dtype}")
                print(f"[NIfTI Preview] Data size: {data.nbytes / 1024 / 1024:.2f} MB")
                
                # Get affine matrix for orientation
                affine = img.affine
                print(f"[NIfTI Preview] Affine matrix:\n{affine}")
            except Exception as e:
                print(f"[NIfTI Preview] Error loading NIfTI: {e}")
                raise
            
            # Try to load JSON sidecar for orientation info (optional)
            json_data = None
            # Try to find JSON sidecar automatically (BIDS convention)
            json_path = nifti_path.with_suffix('').with_suffix('.json')
            if json_path.exists():
                try:
                    import json
                    with open(json_path, 'r') as f:
                        json_data = json.load(f)
                    print(f"[NIfTI Preview] Found and loaded JSON sidecar: {json_path}")
                    print(f"[NIfTI Preview] JSON keys: {list(json_data.keys())[:10]}")
                except Exception as e:
                    print(f"[NIfTI Preview] Could not load auto-found JSON: {e}")
            
            # Handle 4D data (select volume)
            if len(data.shape) == 4:
                if volume_index >= data.shape[3]:
                    volume_index = 0
                    print(f"[NIfTI Preview] Volume index out of range, using 0")
                data = data[:, :, :, volume_index]
                print(f"[NIfTI Preview] Selected volume {volume_index}, shape: {data.shape}")
            
            # Validate 3D shape
            if len(data.shape) != 3:
                raise ValueError(f"Expected 3D or 4D data, got shape: {data.shape}")
            
            # Determine orientation from affine matrix
            # Use nibabel's orientation tools if available
            try:
                from nibabel.orientations import aff2axcodes, ornt_transform, axcodes2ornt
                # Get current orientation codes from affine
                current_axcodes = aff2axcodes(affine)
                print(f"[NIfTI Preview] Current orientation codes: {current_axcodes}")
                
                # Target orientation for FSL display: RAS+ (Right-Anterior-Superior)
                target_axcodes = ('R', 'A', 'S')
                
                # Calculate transformation needed
                current_ornt = axcodes2ornt(current_axcodes)
                target_ornt = axcodes2ornt(target_axcodes)
                transform = ornt_transform(current_ornt, target_ornt)
                
                print(f"[NIfTI Preview] Orientation transform: {transform}")
                print(f"[NIfTI Preview] Will apply: {current_axcodes} -> {target_axcodes}")
                
                # Apply orientation transform to data
                from nibabel.orientations import apply_orientation
                data_oriented = apply_orientation(data, transform)
                print(f"[NIfTI Preview] Data reoriented, new shape: {data_oriented.shape}")
            except ImportError:
                print(f"[NIfTI Preview] nibabel.orientations not available, using default orientation")
                data_oriented = data
            except Exception as e:
                print(f"[NIfTI Preview] Error in orientation detection: {e}, using default")
                data_oriented = data
            
            # Get middle slices for 3-panel view following FSL conventions
            # FSL standard display: RAS+ orientation
            # - Sagittal: left side view (viewing from left, showing AP-IS plane)
            # - Coronal: front view (viewing from anterior, showing LR-IS plane)  
            # - Axial: top view (viewing from superior, showing LR-AP plane)
            # Display order: Sagittal (left), Coronal (middle), Axial (right)
            
            mid_x = data_oriented.shape[0] // 2  # R-L dimension (after reorientation)
            mid_y = data_oriented.shape[1] // 2  # A-P dimension
            mid_z = data_oriented.shape[2] // 2  # S-I dimension
            
            # Extract slices - now data should be in RAS+ orientation
            # Sagittal (LR): slice through R-L dimension, show A-P x S-I plane
            # FSL shows left side view: A-P horizontal, S-I vertical
            sagittal_raw = data_oriented[mid_x, :, :]  # Extract A-P x S-I plane
            # For left side view: transpose to get A-P horizontal, S-I vertical
            sagittal_slice = np.transpose(sagittal_raw, (1, 0))
            
            # Coronal (AP): slice through A-P dimension, show R-L x S-I plane
            # FSL shows front view: R-L horizontal, S-I vertical
            coronal_raw = data_oriented[:, mid_y, :]  # Extract R-L x S-I plane
            coronal_slice = np.transpose(coronal_raw, (1, 0))  # S-I vertical, R-L horizontal
            
            # Axial (IS): slice through S-I dimension, show R-L x A-P plane
            # FSL shows top view: R-L horizontal, A-P vertical
            axial_raw = data_oriented[:, :, mid_z]  # Extract R-L x A-P plane
            axial_slice = np.transpose(axial_raw, (1, 0))  # A-P vertical, R-L horizontal
            
            print(f"[NIfTI Preview] Extracted slices: sagittal {sagittal_slice.shape}, coronal {coronal_slice.shape}, axial {axial_slice.shape}")
            
            # Calculate aspect ratios for each slice to preserve proportions
            # Order: Sagittal, Coronal, Axial (left to right)
            sagittal_aspect = sagittal_slice.shape[1] / sagittal_slice.shape[0]  # width/height
            coronal_aspect = coronal_slice.shape[1] / coronal_slice.shape[0]
            axial_aspect = axial_slice.shape[1] / axial_slice.shape[0]
            
            # Parse output size
            target_width, target_height = map(int, output_size.split("x"))
            
            # Limit size to prevent memory issues
            max_width, max_height = 2048, 1536
            if target_width > max_width or target_height > max_height:
                print(f"[NIfTI Preview] Limiting size from {target_width}x{target_height} to {max_width}x{max_height}")
                scale = min(max_width / target_width, max_height / target_height)
                target_width = int(target_width * scale)
                target_height = int(target_height * scale)
            
            # Calculate individual panel sizes preserving aspect ratios
            # Each panel gets 1/3 of the width, height scales to maintain aspect
            # Order: Sagittal, Coronal, Axial
            panel_width = target_width / 3
            sagittal_height = panel_width / sagittal_aspect
            coronal_height = panel_width / coronal_aspect
            axial_height = panel_width / axial_aspect
            
            # Use the maximum height needed, but ensure it fits in target_height
            max_panel_height = max(sagittal_height, coronal_height, axial_height)
            if max_panel_height > target_height:
                # Scale down to fit
                scale = target_height / max_panel_height
                panel_width = panel_width * scale
                sagittal_height = sagittal_height * scale
                coronal_height = coronal_height * scale
                axial_height = axial_height * scale
            
            # Final figure dimensions
            fig_width = target_width / 100  # Convert to inches
            fig_height = max(sagittal_height, coronal_height, axial_height) / 100
            
            # Save to temporary file with unique name to avoid overwrites when multiple nodes are used
            # Use hash of input file path + UUID + timestamp for uniqueness
            import hashlib
            file_hash = hashlib.md5(str(nifti_path).encode()).hexdigest()[:8]
            unique_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time() * 1000000) % 1000000  # Microseconds, last 6 digits
            output_image_name = f"nifti_preview_{file_hash}_{unique_id}_{timestamp}.png"
            output_path = Path("/tmp") / output_image_name
            output_path.parent.mkdir(exist_ok=True, mode=0o777)
            
            # Create figure with 3 subplots preserving aspect ratios
            # Use lower DPI to reduce memory usage
            dpi = 72  # Lower DPI for smaller memory footprint
            fig = None
            try:
                print(f"[NIfTI Preview] Creating matplotlib figure...")
                fig, axes = plt.subplots(1, 3, figsize=(fig_width, fig_height), dpi=dpi)
                fig.patch.set_facecolor('black')
                
                # Normalize data for display
                slices = [axial_slice, coronal_slice, sagittal_slice]
                titles = ['Axial', 'Coronal', 'Sagittal']
                
                # Get colormap
                if colormap == "grayscale":
                    cmap = plt.cm.gray
                elif colormap == "hot":
                    cmap = plt.cm.hot
                elif colormap == "viridis":
                    cmap = plt.cm.viridis
                elif colormap == "jet":
                    cmap = plt.cm.jet
                else:
                    cmap = plt.cm.gray
                
                print(f"[NIfTI Preview] Rendering slices with preserved aspect ratios...")
                # Order: Sagittal (left), Coronal (middle), Axial (right)
                slice_configs = [
                    (axes[0], sagittal_slice, 'Sagittal (LR)', sagittal_aspect),
                    (axes[1], coronal_slice, 'Coronal (AP)', coronal_aspect),
                    (axes[2], axial_slice, 'Axial (IS)', axial_aspect)
                ]
                
                for ax, slice_data, title, aspect_ratio in slice_configs:
                    # Remove invalid values
                    valid_data = slice_data[np.isfinite(slice_data)]
                    if len(valid_data) == 0:
                        ax.imshow(np.zeros_like(slice_data), cmap=cmap, origin='lower', aspect=aspect_ratio)
                    else:
                        # Use percentile-based normalization (2-98%)
                        p2 = np.percentile(valid_data, 2)
                        p98 = np.percentile(valid_data, 98)
                        if p98 > p2:
                            normalized = np.clip((slice_data - p2) / (p98 - p2), 0, 1)
                        else:
                            normalized = np.zeros_like(slice_data)
                        
                        # Handle invalid values
                        normalized[~np.isfinite(slice_data)] = 0
                        
                        # Use aspect='equal' or calculated aspect to preserve proportions
                        # origin='lower' for neuroimaging convention (inferior at bottom)
                        ax.imshow(normalized, cmap=cmap, origin='lower', aspect=aspect_ratio)
                        ax.set_title(title, color='white', fontsize=10)
                        ax.axis('off')
                
                plt.tight_layout(pad=0.1)
                
                print(f"[NIfTI Preview] Saving preview to: {output_path}")
                plt.savefig(
                    str(output_path), 
                    bbox_inches='tight', 
                    pad_inches=0, 
                    facecolor='black', 
                    dpi=dpi,
                    format='png'
                )
                print(f"[NIfTI Preview] Figure saved successfully")
            except Exception as e:
                import traceback
                print(f"[NIfTI Preview] Error in matplotlib: {e}")
                print(traceback.format_exc())
                raise
            finally:
                if fig is not None:
                    plt.close(fig)
                # Force garbage collection
                import gc
                gc.collect()
            
            print(f"[NIfTI Preview] Preview saved, loading image...")
            
            # Load the saved image
            from PIL import Image
            try:
                img = Image.open(str(output_path))
                # Limit image size if too large
                max_img_dim = 2048
                if img.size[0] > max_img_dim or img.size[1] > max_img_dim:
                    print(f"[NIfTI Preview] Image too large {img.size}, resizing...")
                    scale = min(max_img_dim / img.size[0], max_img_dim / img.size[1])
                    new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                img_array = np.array(img)
                
                # Convert RGBA to RGB if needed
                if len(img_array.shape) == 3 and img_array.shape[2] == 4:
                    img_array = img_array[:, :, :3]
                
                # Ensure RGB format
                if len(img_array.shape) == 2:
                    # Grayscale, convert to RGB
                    img_array = np.stack([img_array, img_array, img_array], axis=-1)
                
                # Convert to ComfyUI format: [1, H, W, 3] as uint8
                preview_np = np.expand_dims(img_array.astype(np.uint8), axis=0)
                
                # Convert to float32 in range [0, 1] for ComfyUI IMAGE type
                # ComfyUI expects: [batch, height, width, channels] as float32 in [0, 1]
                preview_float = preview_np.astype(np.float32) / 255.0
                
                # Convert to PyTorch tensor for compatibility with SaveImage node
                preview_tensor = torch.from_numpy(preview_float)
                
                # Free memory
                del img, img_array, preview_np, preview_float
                import gc
                gc.collect()
            except Exception as e:
                print(f"[NIfTI Preview] Error loading image: {e}")
                raise
            
            print(f"[NIfTI Preview] Loaded image shape: {preview_tensor.shape}")
            print(f"[NIfTI Preview] Image dtype: {preview_tensor.dtype}")
            print(f"[NIfTI Preview] Value range: [{preview_tensor.min():.3f}, {preview_tensor.max():.3f}]")
            
            # Save preview image to ComfyUI's temp directory for UI display
            if HAS_FOLDER_PATHS and folder_paths:
                temp_dir = folder_paths.get_temp_directory()
            else:
                temp_dir = "/tmp"
            preview_filename = f"nifti_preview_{file_hash}_{unique_id}.png"
            preview_path = os.path.join(temp_dir, preview_filename)
            
            # Save the image for UI preview
            from PIL import Image as PILImage
            # Convert tensor back to PIL Image for saving
            img_for_preview = (preview_tensor[0].numpy() * 255).astype(np.uint8)
            pil_img = PILImage.fromarray(img_for_preview)
            pil_img.save(preview_path)
            print(f"[NIfTI Preview] Saved UI preview to: {preview_path}")
            
            # Clean up original temp file
            try:
                output_path.unlink()
            except:
                pass
            
            print(f"[NIfTI Preview] ===== PREVIEW COMPLETE =====")
            
            # Return both the image tensor AND UI data for preview display
            return {
                "ui": {
                    "images": [
                        {
                            "filename": preview_filename,
                            "subfolder": "",
                            "type": "temp"
                        }
                    ]
                },
                "result": (preview_tensor,)
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[NIfTI Preview] ERROR: {str(e)}")
            print(f"[NIfTI Preview] Traceback:\n{error_trace}")
            
            # Return a black image on error (as tensor)
            error_image_np = np.zeros((1, 512, 384, 3), dtype=np.float32)
            error_image_tensor = torch.from_numpy(error_image_np)
            return {
                "ui": {"images": []},
                "result": (error_image_tensor,)
            }
