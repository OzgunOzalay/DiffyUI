"""
Smoke tests for DiffyUI CORE Engine nodes.
Verifies imports, INPUT_TYPES(), and IS_CHANGED() without requiring
any neuroimaging tools (FSL / MRtrix3 / DIPY) to be installed.
"""

import sys
import os

# Make sure the project root is on the path so imports resolve
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# GibbsUnringingNode
# ---------------------------------------------------------------------------

def test_gibbs_unringing_import():
    from custom_nodes.dwi_nodes.gibbs_unringing import GibbsUnringingNode
    assert GibbsUnringingNode is not None


def test_gibbs_unringing_input_types():
    from custom_nodes.dwi_nodes.gibbs_unringing import GibbsUnringingNode
    schema = GibbsUnringingNode.INPUT_TYPES()
    assert "required" in schema
    assert "dwi_file" in schema["required"]
    optional = schema.get("optional", {})
    for key in ("axes", "maxlength", "minlength", "nshifts", "nthreads"):
        assert key in optional, f"Missing optional key: {key}"


def test_gibbs_unringing_return_types():
    from custom_nodes.dwi_nodes.gibbs_unringing import GibbsUnringingNode
    assert GibbsUnringingNode.RETURN_TYPES == ("STRING",)
    assert GibbsUnringingNode.RETURN_NAMES == ("degibbs_dwi",)


def test_gibbs_unringing_is_changed_no_file():
    from custom_nodes.dwi_nodes.gibbs_unringing import GibbsUnringingNode
    result = GibbsUnringingNode.IS_CHANGED("")
    # Should return a hash string or nan — not raise
    assert result is not None


# ---------------------------------------------------------------------------
# CSDNode
# ---------------------------------------------------------------------------

def test_csd_import():
    from custom_nodes.dwi_nodes.csd import CSDNode
    assert CSDNode is not None


def test_csd_input_types():
    from custom_nodes.dwi_nodes.csd import CSDNode
    schema = CSDNode.INPUT_TYPES()
    assert "required" in schema
    for key in ("dwi_file", "bvec_file", "bval_file", "mask_file"):
        assert key in schema["required"], f"Missing required key: {key}"
    optional = schema.get("optional", {})
    assert "lmax" in optional
    assert "nthreads" in optional


def test_csd_return_types():
    from custom_nodes.dwi_nodes.csd import CSDNode
    assert len(CSDNode.RETURN_TYPES) == 6
    assert "wm_fod" in CSDNode.RETURN_NAMES
    assert "wm_response" in CSDNode.RETURN_NAMES


def test_csd_is_changed_empty():
    from custom_nodes.dwi_nodes.csd import CSDNode
    result = CSDNode.IS_CHANGED("", "", "", "")
    assert result is not None


# ---------------------------------------------------------------------------
# EddyQCNode
# ---------------------------------------------------------------------------

def test_eddy_qc_import():
    from custom_nodes.dwi_nodes.eddy_qc import EddyQCNode
    assert EddyQCNode is not None


def test_eddy_qc_input_types():
    from custom_nodes.dwi_nodes.eddy_qc import EddyQCNode
    schema = EddyQCNode.INPUT_TYPES()
    assert "required" in schema
    assert "eddy_corrected_dwi" in schema["required"]
    optional = schema.get("optional", {})
    for key in ("acqp_file", "mask_file", "bval_file", "field_file", "verbose"):
        assert key in optional, f"Missing optional key: {key}"


def test_eddy_qc_return_types():
    from custom_nodes.dwi_nodes.eddy_qc import EddyQCNode
    assert EddyQCNode.RETURN_TYPES == ("STRING",)
    assert EddyQCNode.RETURN_NAMES == ("qc_report_dir",)


def test_eddy_qc_is_changed_empty():
    from custom_nodes.dwi_nodes.eddy_qc import EddyQCNode
    result = EddyQCNode.IS_CHANGED("")
    assert result is not None


def test_eddy_qc_missing_input_returns_error_not_raises():
    from custom_nodes.dwi_nodes.eddy_qc import EddyQCNode
    node = EddyQCNode()
    result = node.run_qc("")
    assert isinstance(result, tuple)
    assert len(result) == 1
    assert result[0].startswith("Error:")


# ---------------------------------------------------------------------------
# DKIFitNode
# ---------------------------------------------------------------------------

def test_dki_fit_import():
    from custom_nodes.dwi_nodes.dki_fit import DKIFitNode
    assert DKIFitNode is not None


def test_dki_fit_input_types():
    from custom_nodes.dwi_nodes.dki_fit import DKIFitNode
    schema = DKIFitNode.INPUT_TYPES()
    assert "required" in schema
    for key in ("dwi_file", "bvec_file", "bval_file", "mask_file"):
        assert key in schema["required"], f"Missing required key: {key}"
    optional = schema.get("optional", {})
    assert "min_kurtosis" in optional
    assert "max_kurtosis" in optional


def test_dki_fit_return_types():
    from custom_nodes.dwi_nodes.dki_fit import DKIFitNode
    assert len(DKIFitNode.RETURN_TYPES) == 8
    for name in ("mk_map", "ak_map", "rk_map", "kfa_map", "fa_map", "md_map", "ad_map", "rd_map"):
        assert name in DKIFitNode.RETURN_NAMES, f"Missing return name: {name}"


def test_dki_fit_is_changed_empty():
    from custom_nodes.dwi_nodes.dki_fit import DKIFitNode
    result = DKIFitNode.IS_CHANGED("", "", "", "")
    assert result is not None


def test_dki_fit_missing_input_returns_error_not_raises():
    from custom_nodes.dwi_nodes.dki_fit import DKIFitNode
    node = DKIFitNode()
    result = node.run_dki("", "", "", "")
    assert isinstance(result, tuple)
    assert len(result) == 8
    # First element is an error string (either "Error: ..." or dipy import message)
    assert isinstance(result[0], str)


# ---------------------------------------------------------------------------
# Existing nodes still importable after refactor
# ---------------------------------------------------------------------------

def test_denoising_import():
    from custom_nodes.dwi_nodes.denoising import DWIDenoiseNode
    assert DWIDenoiseNode is not None


def test_denoising_input_types():
    from custom_nodes.dwi_nodes.denoising import DWIDenoiseNode
    schema = DWIDenoiseNode.INPUT_TYPES()
    assert "dwi_file" in schema["required"]


def test_tractography_import():
    from custom_nodes.dwi_nodes.tractography import DWITractographyNode
    assert DWITractographyNode is not None


def test_tractography_input_types():
    from custom_nodes.dwi_nodes.tractography import DWITractographyNode
    schema = DWITractographyNode.INPUT_TYPES()
    assert "fod_file" in schema["required"]
    assert "mask_file" in schema["required"]
    # Old inputs must be gone
    assert "dwi_file" not in schema.get("required", {})
    assert "bids_dataset" not in schema.get("required", {})


def test_tractography_is_changed_empty():
    from custom_nodes.dwi_nodes.tractography import DWITractographyNode
    result = DWITractographyNode.IS_CHANGED("", "")
    assert result is not None


# ---------------------------------------------------------------------------
# __init__ registration
# ---------------------------------------------------------------------------

def test_init_registers_new_nodes():
    from custom_nodes.dwi_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    for key in ("GibbsUnringing", "CSD", "EddyQC", "DKIFit"):
        assert key in NODE_CLASS_MAPPINGS, f"NODE_CLASS_MAPPINGS missing: {key}"
        assert key in NODE_DISPLAY_NAME_MAPPINGS, f"NODE_DISPLAY_NAME_MAPPINGS missing: {key}"


def test_init_existing_nodes_present():
    from custom_nodes.dwi_nodes import NODE_CLASS_MAPPINGS
    for key in ("DWIDenoise", "DWITractography", "BIDSLoader", "SubjectBatchRunner", "DTIfit"):
        assert key in NODE_CLASS_MAPPINGS, f"NODE_CLASS_MAPPINGS missing: {key}"
