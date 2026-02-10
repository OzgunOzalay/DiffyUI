"""
DWI Analysis Custom Nodes for ComfyUI
"""

from .bids_loader import BIDSLoaderNode
from .subject_selector import SubjectSelectorNode
from .subject_bucket import SubjectBucketNode
from .subject_iterator import SubjectIteratorNode
from .brain_mask import DWIBrainMaskNode
from .denoising import DWIDenoiseNode
from .extract_b0 import ExtractB0Node
from .topup_correction import DWITopupCorrectionNode
from .eddy_correction import DWIEddyCorrectionNode
from .bias_correction import DWIBiasCorrectionNode
from .tensor_fitting import DWITensorFittingNode
from .tractography import DWITractographyNode
from .nifti_preview import NIfTIPreviewNode
from .brain_3d_viewer import Brain3DViewerNode
from .nifti_stats import NIfTIStatsNode
from .deepseek_qc_supervisor import DeepSeekQCSupervisorNode

NODE_CLASS_MAPPINGS = {
    "BIDSLoader": BIDSLoaderNode,
    "SubjectSelector": SubjectSelectorNode,
    "SubjectBucket": SubjectBucketNode,
    "SubjectIterator": SubjectIteratorNode,
    "DWIBrainMask": DWIBrainMaskNode,
    "DWIDenoise": DWIDenoiseNode,
    "ExtractB0": ExtractB0Node,
    "DWITopupCorrection": DWITopupCorrectionNode,
    "DWIEddyCorrection": DWIEddyCorrectionNode,
    "DWIBiasCorrection": DWIBiasCorrectionNode,
    "DWITensorFitting": DWITensorFittingNode,
    "DWITractography": DWITractographyNode,
    "NIfTIPreview": NIfTIPreviewNode,
    "Brain3DViewer": Brain3DViewerNode,
    "NIfTIStats": NIfTIStatsNode,
    "DeepSeekQCSupervisor": DeepSeekQCSupervisorNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BIDSLoader": "BIDS Loader",
    "SubjectSelector": "Subject Selector",
    "SubjectBucket": "Subject Bucket",
    "SubjectIterator": "Subject Iterator",
    "DWIBrainMask": "DWI Brain Mask",
    "DWIDenoise": "DWI Denoise",
    "ExtractB0": "Extract B0",
    "DWITopupCorrection": "DWI Topup Correction",
    "DWIEddyCorrection": "DWI Eddy Correction",
    "DWIBiasCorrection": "DWI Bias Correction",
    "DWITensorFitting": "DWI Tensor Fitting",
    "DWITractography": "DWI Tractography",
    "NIfTIPreview": "NIfTI Preview",
    "Brain3DViewer": "Brain 3D Viewer",
    "NIfTIStats": "NIfTI Stats",
    "DeepSeekQCSupervisor": "DeepSeek QC Supervisor",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
