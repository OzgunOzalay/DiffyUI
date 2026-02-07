"""
Brain 3D Viewer Node - Convert brain-extracted NIfTI to 3D mesh (OBJ or STL) for viewing.
Uses marching cubes (skimage) and optionally NIfTI affine for world (mm) coordinates.
"""
import struct

import os
import hashlib
import uuid
from pathlib import Path

try:
    import nibabel as nib
    import numpy as np
    HAS_NIBABEL = True
except ImportError as e:
    HAS_NIBABEL = False
    IMPORT_ERROR_NIBABEL = str(e)

try:
    from skimage import measure
    HAS_SKIMAGE = True
except ImportError as e:
    HAS_SKIMAGE = False
    IMPORT_ERROR_SKIMAGE = str(e)

try:
    import folder_paths
    HAS_FOLDER_PATHS = True
except ImportError:
    HAS_FOLDER_PATHS = False
    folder_paths = None


class Brain3DViewerNode:
    """
    Brain 3D Viewer - Extract a surface mesh from a brain NIfTI using marching cubes
    and save as OBJ for ComfyUI 3D preview.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "nifti_file": ("STRING", {
                    "default": "",
                    "tooltip": "Path to brain-extracted NIfTI (.nii or .nii.gz)"
                }),
            },
            "optional": {
                "level": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "Marching cubes iso-value (0.5 for binary mask)"
                }),
                "mesh_detail": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": 8,
                    "step": 1,
                    "tooltip": "1=full resolution (most vertices), 2–8=subsample volume for fewer triangles. Use 2–4 for Preview 3D."
                }),
                "use_world_coords": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Transform vertices to world (mm) using NIfTI affine"
                }),
                "volume_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "tooltip": "Volume index for 4D data (0 = first volume)"
                }),
                "output_format": (["obj", "stl"], {
                    "default": "obj",
                    "tooltip": "Output mesh format: OBJ or STL (binary)."
                }),
                "viewer_up": (["RAS (no change)", "Y-up (ComfyUI / standard 3D)"], {
                    "default": "Y-up (ComfyUI / standard 3D)",
                    "tooltip": "Reorient so the brain appears right-way-up. NIfTI uses RAS (Z=superior); most 3D viewers use Y-up. Use Y-up so the brain isn't tilted in ComfyUI."
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("mesh_path",)
    FUNCTION = "mesh_brain"
    CATEGORY = "DWI"
    DESCRIPTION = "Extract 3D mesh from brain NIfTI (marching cubes) and save as OBJ or STL for 3D viewer. Connect mesh_path to Preview 3D & Animation so this node runs and the mesh is shown."
    OUTPUT_NODE = True

    def mesh_brain(
        self,
        nifti_file: str,
        level: float = 0.5,
        mesh_detail: int = 2,
        use_world_coords: bool = True,
        volume_index: int = 0,
        output_format: str = "obj",
        viewer_up: str = "Y-up (ComfyUI / standard 3D)",
    ):
        """
        Load NIfTI, run marching cubes, write OBJ, return path and register for 3D preview.
        """
        print("[Brain 3D Viewer] mesh_brain() called", flush=True)
        if not HAS_NIBABEL:
            err = f"Missing nibabel: {IMPORT_ERROR_NIBABEL}"
            print(f"[Brain 3D Viewer] {err}", flush=True)
            return {"ui": {"files": []}, "result": (err,)}
        if not HAS_SKIMAGE:
            err = f"Missing scikit-image: {IMPORT_ERROR_SKIMAGE}. Install: pip install scikit-image"
            print(f"[Brain 3D Viewer] {err}", flush=True)
            return {"ui": {"files": []}, "result": (err,)}

        # Accept path from widget (str) or from linked input (may be list/tuple with one element)
        if nifti_file is None:
            nifti_file = ""
        elif isinstance(nifti_file, (list, tuple)):
            nifti_file = nifti_file[0] if nifti_file else ""
        nifti_file = str(nifti_file).strip() if nifti_file else ""
        nifti_path = Path(nifti_file).expanduser() if nifti_file else None
        if not nifti_path or not nifti_path.exists():
            err = f"NIfTI file not found: {nifti_file!r}"
            print(f"[Brain 3D Viewer] {err}", flush=True)
            return {"ui": {"files": []}, "result": (err,)}

        try:
            img = nib.load(str(nifti_path))
            data = np.asarray(img.dataobj)
            if data.ndim == 4:
                data = data[:, :, :, volume_index]
            if data.ndim != 3:
                err = f"Expected 3D or 4D data, got ndim={data.ndim}"
                print(f"[Brain 3D Viewer] {err}", flush=True)
                return {"ui": {"files": []}, "result": (err,)}

            # Subsample volume to reduce mesh complexity; cap mesh size so viewers don't crash
            MAX_FACES = 500_000  # Meshlab often crashes on very large meshes
            data_full = data
            s = max(1, int(mesh_detail))
            while True:
                data = np.ascontiguousarray(data_full[::s, ::s, ::s]) if s > 1 else data_full
                result = measure.marching_cubes(data, level=level)
                verts = np.asarray(result[0], dtype=np.float64)
                faces = np.asarray(result[1], dtype=np.int32)
                if s > 1:
                    verts = verts * s
                if use_world_coords and hasattr(img, 'affine') and img.affine is not None:
                    affine = img.affine
                    verts_h = np.c_[verts, np.ones(len(verts))]
                    verts = (affine @ verts_h.T).T[:, :3]
                n_faces = len(faces)
                if n_faces <= MAX_FACES or s >= 8:
                    break
                s = min(s + 1, 8)
                print(f"[Brain 3D Viewer] Mesh too large ({n_faces} faces), re-running with subsample {s}", flush=True)

            # Sanitize: NaN/Inf break Meshlab and many viewers
            bad = ~np.isfinite(verts)
            if np.any(bad):
                verts = np.where(bad, 0.0, verts)
                print(f"[Brain 3D Viewer] Replaced non-finite vertex values", flush=True)

            # Normalize to unit scale so viewers don't crash on huge world coords (e.g. mm)
            n_verts = len(verts)
            extent = np.abs(verts).max()
            if extent > 1e-6:
                verts = verts / extent
            # Reorient for Y-up viewers (ComfyUI, Three.js, etc.): NIfTI RAS has Z=superior
            if "Y-up" in viewer_up:
                # RAS (X=right, Y=anterior, Z=superior) -> Y-up (X=right, Y=up, Z=back): (x,y,z)->(x, z, -y)
                verts = np.column_stack([verts[:, 0], verts[:, 2], -verts[:, 1]])
            n_faces = len(faces)

            if HAS_FOLDER_PATHS and folder_paths:
                out_dir = Path(folder_paths.get_output_directory()) / "3d"
            else:
                out_dir = Path("/tmp") / "brain_3d"
            out_dir.mkdir(parents=True, exist_ok=True)

            fmt = "stl" if output_format == "stl" else "obj"
            file_hash = hashlib.md5(str(nifti_path).encode()).hexdigest()[:8]
            short_uuid = str(uuid.uuid4())[:8]
            out_name = f"brain_mesh_{file_hash}_{short_uuid}.{fmt}"
            out_path = out_dir / out_name

            if n_verts == 0 or n_faces == 0:
                err = "Marching cubes produced no mesh (empty or invalid mask?). Try a different level or check the NIfTI."
                print(f"[Brain 3D Viewer] {err}", flush=True)
                return {"ui": {"files": []}, "result": (err,)}

            print(f"[Brain 3D Viewer] Mesh: {n_verts} vertices, {n_faces} faces (detail={s}, format={fmt})", flush=True)

            if fmt == "stl":
                # Binary STL: only write non-degenerate triangles (same verts => zero area => skip)
                verts_f = verts.astype(np.float32)
                stl_triangles = []
                for face in faces:
                    i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
                    if not (0 <= i0 < n_verts and 0 <= i1 < n_verts and 0 <= i2 < n_verts):
                        continue
                    if i0 == i1 or i1 == i2 or i0 == i2:
                        continue
                    a, b, c = verts_f[i0], verts_f[i1], verts_f[i2]
                    n = np.cross(b - a, c - a)
                    nlen = np.linalg.norm(n)
                    if nlen < 1e-10:
                        continue
                    n = (n / nlen).astype(np.float32)
                    stl_triangles.append((n, a, b, c))
                n_stl = len(stl_triangles)
                if n_stl == 0:
                    err = "No valid triangles after filtering. Try different mesh_detail or level."
                    print(f"[Brain 3D Viewer] {err}", flush=True)
                    return {"ui": {"files": []}, "result": (err,)}
                if n_stl < n_faces:
                    print(f"[Brain 3D Viewer] STL: skipped {n_faces - n_stl} degenerate faces", flush=True)
                with open(out_path, "wb") as f:
                    f.write(b"\x00" * 80)
                    f.write(struct.pack("<I", n_stl))
                    for n, a, b, c in stl_triangles:
                        f.write(struct.pack("<12f", n[0], n[1], n[2], a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]))
                        f.write(struct.pack("<H", 0))
            else:
                # OBJ: fixed precision, 1-based indices, no degenerate faces (Meshlab crashes on them)
                valid_faces = []
                for face in faces:
                    a, b, c = int(face[0]), int(face[1]), int(face[2])
                    if not (0 <= a < n_verts and 0 <= b < n_verts and 0 <= c < n_verts):
                        continue
                    if a == b or b == c or a == c:
                        continue
                    valid_faces.append((a + 1, b + 1, c + 1))
                n_valid = len(valid_faces)
                if n_valid == 0:
                    err = "No valid faces after filtering (degenerate mesh). Try different mesh_detail or level."
                    print(f"[Brain 3D Viewer] {err}", flush=True)
                    return {"ui": {"files": []}, "result": (err,)}
                if n_valid < n_faces:
                    print(f"[Brain 3D Viewer] Skipped {n_faces - n_valid} invalid/degenerate faces", flush=True)
                with open(out_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write("# OBJ mesh from Brain 3D Viewer\n")
                    for i in range(n_verts):
                        f.write(f"v {verts[i, 0]:.6f} {verts[i, 1]:.6f} {verts[i, 2]:.6f}\n")
                    for (a, b, c) in valid_faces:
                        f.write(f"f {a} {b} {c}\n")
                    f.write("\n")

            # Preview 3D & Animation frontend hardcodes loadFolder='output'
            # and constructs: /view?filename=<name>&type=output&subfolder=<sub>
            # So the mesh_path must be a clean path relative to ComfyUI's
            # output root (e.g. "3d/brain_mesh_xxx.obj"), NOT an annotated
            # path like "file.obj[input]" which the frontend cannot parse.
            if HAS_FOLDER_PATHS and folder_paths:
                import shutil
                # Also copy to input/3d so the file appears in the Load 3D dropdown
                input_dir = Path(folder_paths.get_input_directory())
                input_3d = input_dir / "3d"
                input_3d.mkdir(parents=True, exist_ok=True)
                preview_name = f"brain_mesh_preview.{fmt}"
                preview_path_3d = input_3d / preview_name
                shutil.copy2(out_path, preview_path_3d)
                # Return path relative to output root so Preview 3D can fetch it
                mesh_path_str = f"3d/{out_name}"
                print(f"[Brain 3D Viewer] Mesh saved: {out_path}")
                print(f"[Brain 3D Viewer] Copied to {preview_path_3d} for Load 3D dropdown.")
                print(f"[Brain 3D Viewer] Preview 3D path: {mesh_path_str} (type=output)")
            else:
                mesh_path_str = str(out_path)

            ui = {
                "files": [
                    {
                        "filename": out_name,
                        "subfolder": "3d",
                        "type": "output",
                    }
                ]
            }
            return {"ui": ui, "result": (mesh_path_str,)}

        except Exception as e:
            import traceback
            err = f"Error: {str(e)}"
            print(f"[Brain 3D Viewer] {err}\n{traceback.format_exc()}")
            return {"ui": {"files": []}, "result": (err,)}
