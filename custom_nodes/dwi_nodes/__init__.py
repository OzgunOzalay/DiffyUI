"""
DWI Analysis Custom Nodes for ComfyUI
"""

from .bids_loader import BIDSLoaderNode
from .subject_batch_runner import SubjectBatchRunnerNode
from .workflow_packs import DWIPreprocPack, DerivedFilePicker
from .brain_mask import DWIBrainMaskNode
from .denoising import DWIDenoiseNode
from .extract_b0 import ExtractB0Node
from .topup_correction import DWITopupCorrectionNode
from .eddy_correction import DWIEddyCorrectionNode
from .bias_correction import DWIBiasCorrectionNode
from .dtifit import DTIfitNode
from .nifti_preview import NIfTIPreviewNode
from .brain_3d_viewer import Brain3DViewerNode
from .nifti_stats import NIfTIStatsNode
from .tractography import DWITractographyNode
try:
    from .gibbs_unringing import GibbsUnringingNode
except Exception as _e:
    print(f"[DiffyUI] Warning: could not load GibbsUnringingNode: {_e}")
    GibbsUnringingNode = None
try:
    from .csd import CSDNode
except Exception as _e:
    print(f"[DiffyUI] Warning: could not load CSDNode: {_e}")
    CSDNode = None
try:
    from .eddy_qc import EddyQCNode
except Exception as _e:
    print(f"[DiffyUI] Warning: could not load EddyQCNode: {_e}")
    EddyQCNode = None
try:
    from .dki_fit import DKIFitNode
except Exception as _e:
    print(f"[DiffyUI] Warning: could not load DKIFitNode: {_e}")
    DKIFitNode = None
from .tbss_fa_collector import TBSSFACollectorNode
from .tbss_preproc import TBSS1PreprocNode
from .tbss_reg import TBSS2RegNode
from .tbss_postreg import TBSS3PostregNode
from .tbss_prestats import TBSS4PrestatsNode
from .fba_prep import FBAPrepNode
from .fba_subject1 import FBASubject1Node
from .fba_response_avg import FBAResponseAvgNode
from .fba_subject2 import FBASubject2Node
from .fba_template_prep import FBATemplatePrepNode
from .fba_template_build import FBATemplateBuildNode
from .fba_subject3a import FBASubject3aNode
from .fba_template_mask import FBATemplateMaskNode
from .fba_subject3b import FBASubject3bNode
from .fba_logfc_fdc import FBALogFCFDCNode
from .fba_group import FBAGroupNode

NODE_CLASS_MAPPINGS = {
    # --- Entry / batch ---
    "BIDSLoader": BIDSLoaderNode,
    "SubjectBatchRunner": SubjectBatchRunnerNode,
    # --- Workflow packs ---
    "DWIPreprocPack": DWIPreprocPack,
    "DerivedFilePicker": DerivedFilePicker,
    # --- Preprocessing ---
    "DWIBrainMask": DWIBrainMaskNode,
    "DWIDenoise": DWIDenoiseNode,
    "ExtractB0": ExtractB0Node,
    "DWITopupCorrection": DWITopupCorrectionNode,
    "DWIEddyCorrection": DWIEddyCorrectionNode,
    "DWIBiasCorrection": DWIBiasCorrectionNode,
    "DTIfit": DTIfitNode,
    # --- QC / visualisation ---
    "NIfTIPreview": NIfTIPreviewNode,
    "Brain3DViewer": Brain3DViewerNode,
    "NIfTIStats": NIfTIStatsNode,
    # --- Tractography ---
    "DWITractography": DWITractographyNode,
    # --- New CORE nodes ---
    **({} if GibbsUnringingNode is None else {"GibbsUnringing": GibbsUnringingNode}),
    **({} if CSDNode         is None else {"CSD":            CSDNode}),
    **({} if EddyQCNode      is None else {"EddyQC":         EddyQCNode}),
    **({} if DKIFitNode      is None else {"DKIFit":         DKIFitNode}),
    # --- TBSS ---
    "TBSSFACollector": TBSSFACollectorNode,
    "TBSS1Preproc": TBSS1PreprocNode,
    "TBSS2Reg": TBSS2RegNode,
    "TBSS3Postreg": TBSS3PostregNode,
    "TBSS4Prestats": TBSS4PrestatsNode,
    # --- FBA ---
    "FBAPrep": FBAPrepNode,
    "FBASubject1": FBASubject1Node,
    "FBAResponseAvg": FBAResponseAvgNode,
    "FBASubject2": FBASubject2Node,
    "FBATemplatePrep": FBATemplatePrepNode,
    "FBATemplateBuild": FBATemplateBuildNode,
    "FBASubject3a": FBASubject3aNode,
    "FBATemplateMask": FBATemplateMaskNode,
    "FBASubject3b": FBASubject3bNode,
    "FBALogFCFDC": FBALogFCFDCNode,
    "FBAGroup": FBAGroupNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # --- Entry / batch ---
    "BIDSLoader": "BIDS Project Loader",
    "SubjectBatchRunner": "Subject Batch Runner",
    # --- Workflow packs ---
    "DWIPreprocPack": "DWI Preproc Pack",
    "DerivedFilePicker": "Derived File Picker",
    # --- Preprocessing ---
    "DWIBrainMask": "DWI Brain Mask",
    "DWIDenoise": "DWI Denoise",
    "ExtractB0": "Extract B0",
    "DWITopupCorrection": "DWI Topup Correction",
    "DWIEddyCorrection": "DWI Eddy Correction",
    "DWIBiasCorrection": "DWI Bias Correction",
    "DTIfit": "DTIfit (FSL)",
    # --- QC / visualisation ---
    "NIfTIPreview": "NIfTI Preview",
    "Brain3DViewer": "Brain 3D Mesh",
    "NIfTIStats": "NIfTI Stats",
    # --- Tractography ---
    "DWITractography": "DWI Tractography",
    # --- New CORE nodes ---
    **({} if GibbsUnringingNode is None else {"GibbsUnringing": "Gibbs Unringing"}),
    **({} if CSDNode         is None else {"CSD":            "CSD (Multi-Tissue)"}),
    **({} if EddyQCNode      is None else {"EddyQC":         "Eddy QC (eddy_quad)"}),
    **({} if DKIFitNode      is None else {"DKIFit":         "DKI Fit (DIPY)"}),
    # --- TBSS ---
    "TBSSFACollector": "TBSS FA Collector",
    "TBSS1Preproc": "TBSS 1 Preproc",
    "TBSS2Reg": "TBSS 2 Reg",
    "TBSS3Postreg": "TBSS 3 Postreg",
    "TBSS4Prestats": "TBSS 4 Prestats",
    # --- FBA ---
    "FBAPrep": "FBA Prep",
    "FBASubject1": "FBA Subject 1 (Upsample + Response)",
    "FBAResponseAvg": "FBA Response Average",
    "FBASubject2": "FBA Subject 2 (FOD + Normalise)",
    "FBATemplatePrep": "FBA Template Prep",
    "FBATemplateBuild": "FBA Template Build",
    "FBASubject3a": "FBA Subject 3a (Register + Warp Mask)",
    "FBATemplateMask": "FBA Template Mask",
    "FBASubject3b": "FBA Subject 3b (Fixels + FD + FC)",
    "FBALogFCFDC": "FBA Log FC + FDC",
    "FBAGroup": "FBA Group (Tractography + Smooth)",
}

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
