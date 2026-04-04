"""
DWI Analysis Custom Nodes for ComfyUI
"""

from .bids_loader import BIDSLoaderNode
from .subject_selector import SubjectSelectorNode
from .subject_bucket import SubjectBucketNode
from .subject_iterator import SubjectIteratorNode
from .subject_batch_runner import SubjectBatchRunnerNode
from .brain_mask import DWIBrainMaskNode
from .denoising import DWIDenoiseNode
from .extract_b0 import ExtractB0Node
from .topup_correction import DWITopupCorrectionNode
from .eddy_correction import DWIEddyCorrectionNode
from .bias_correction import DWIBiasCorrectionNode
from .tensor_fitting import DWITensorFittingNode
from .dtifit import DTIfitNode
from .nifti_preview import NIfTIPreviewNode
from .brain_3d_viewer import Brain3DViewerNode
from .nifti_stats import NIfTIStatsNode
from .deepseek_qc_supervisor import DeepSeekQCSupervisorNode
from .tbss_fa_collector import TBSSFACollectorNode
from .tbss_preproc import TBSS1PreprocNode
from .tbss_reg import TBSS2RegNode
from .tbss_postreg import TBSS3PostregNode
from .tbss_prestats import TBSS4PrestatsNode

NODE_CLASS_MAPPINGS = {
    "BIDSLoader": BIDSLoaderNode,
    "SubjectSelector": SubjectSelectorNode,
    "SubjectBucket": SubjectBucketNode,
    "SubjectIterator": SubjectIteratorNode,
    "SubjectBatchRunner": SubjectBatchRunnerNode,
    "DWIBrainMask": DWIBrainMaskNode,
    "DWIDenoise": DWIDenoiseNode,
    "ExtractB0": ExtractB0Node,
    "DWITopupCorrection": DWITopupCorrectionNode,
    "DWIEddyCorrection": DWIEddyCorrectionNode,
    "DWIBiasCorrection": DWIBiasCorrectionNode,
    "DWITensorFitting": DWITensorFittingNode,
    "DTIfit": DTIfitNode,
    "NIfTIPreview": NIfTIPreviewNode,
    "Brain3DViewer": Brain3DViewerNode,
    "NIfTIStats": NIfTIStatsNode,
    "DeepSeekQCSupervisor": DeepSeekQCSupervisorNode,
    "TBSSFACollector": TBSSFACollectorNode,
    "TBSS1Preproc": TBSS1PreprocNode,
    "TBSS2Reg": TBSS2RegNode,
    "TBSS3Postreg": TBSS3PostregNode,
    "TBSS4Prestats": TBSS4PrestatsNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BIDSLoader": "BIDS Loader",
    "SubjectSelector": "Subject Selector",
    "SubjectBucket": "Subject Bucket",
    "SubjectIterator": "Subject Iterator",
    "SubjectBatchRunner": "Subject Batch Runner",
    "DWIBrainMask": "DWI Brain Mask",
    "DWIDenoise": "DWI Denoise",
    "ExtractB0": "Extract B0",
    "DWITopupCorrection": "DWI Topup Correction",
    "DWIEddyCorrection": "DWI Eddy Correction",
    "DWIBiasCorrection": "DWI Bias Correction",
    "DWITensorFitting": "DWI Tensor Fitting",
    "DTIfit": "DTIfit (FSL)",
    "NIfTIPreview": "NIfTI Preview",
    "Brain3DViewer": "Brain 3D Viewer",
    "NIfTIStats": "NIfTI Stats",
    "DeepSeekQCSupervisor": "DeepSeek QC Supervisor",
    "TBSSFACollector": "TBSS FA Collector",
    "TBSS1Preproc": "TBSS 1 Preproc",
    "TBSS2Reg": "TBSS 2 Reg",
    "TBSS3Postreg": "TBSS 3 Postreg",
    "TBSS4Prestats": "TBSS 4 Prestats",
}

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
