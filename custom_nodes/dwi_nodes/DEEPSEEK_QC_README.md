# DeepSeek QC Supervisor Node

## Overview

The **DeepSeek QC Supervisor** is a specialized ComfyUI node that bridges neuroimaging quality control with AI-powered reasoning. It interfaces with a local Ollama instance running DeepSeek-R1 to perform automated analysis of neuroimaging statistics, comparing them against predefined standards and cohort baselines.

## Core Concept

This node acts as an intelligent QC layer that can be positioned above functional processing nodes (like ASLprep, fMRIprep, or DWI preprocessing nodes) to provide automated quality assessment and decision-making for pipeline integrity.

## Prerequisites

1. **Ollama installed and running** with DeepSeek-R1 model
   ```bash
   # Install Ollama (if not already installed)
   curl -fsSL https://ollama.ai/install.sh | sh

   # Pull DeepSeek-R1 model
   ollama pull deepseek-r1:7b
   # or for larger model:
   ollama pull deepseek-r1:14b

   # Verify Ollama is running
   ollama list
   ```

2. **Python `requests` library** (included in requirements.txt)

## Input Parameters

### Required Inputs

- **stats_text** (STRING, multiline)
  - Raw text output from neuroimaging tools
  - Examples: `fslstats -R -M -V` output, `mrinfo -property` output
  - Can be connected from the **NIfTI Stats** node output

- **rules_json** (STRING, multiline)
  - JSON dictionary defining expected ranges and validation criteria
  - Example:
    ```json
    {
      "mean_intensity": [200, 500],
      "voxel_size": [1, 1, 1],
      "volume_mm3": [1000000, 1800000]
    }
    ```

### Optional Inputs

- **group_context** (STRING, multiline)
  - Summary of cohort statistics for outlier detection
  - Example: `"Cohort mean intensity: 450 ± 50\nCohort volume: 1.2M ± 0.1M mm³"`

- **ollama_model** (COMBO)
  - DeepSeek-R1 model variant
  - Options: `deepseek-r1:7b`, `deepseek-r1:14b`, `deepseek-r1:32b`, `deepseek-r1:latest`
  - Default: `deepseek-r1:7b`

- **system_prompt** (STRING, multiline)
  - Instructions for the LLM to guide its analysis approach
  - Default: Pre-configured prompt for neuroimaging QC analyst role

- **ollama_url** (STRING)
  - Ollama API endpoint
  - Default: `http://localhost:11434`

- **temperature** (FLOAT, 0.0-2.0)
  - LLM sampling temperature (lower = more deterministic)
  - Default: 0.1

- **timeout** (INT, 10-300 seconds)
  - Request timeout for Ollama API call
  - Default: 60 seconds

## Output Ports

1. **qc_status** (STRING)
   - Simple flag: `PASS`, `WARN`, or `FAIL`
   - Use for conditional routing in workflows

2. **report_markdown** (STRING)
   - Formatted summary with visual indicators (🟢/🟡/🔴)
   - Connect to "Preview as Text" node for display

3. **structured_data** (JSON STRING)
   - Machine-readable JSON with full findings
   - Includes: qc_status, reason, details, model name
   - Use for logging, database storage, or downstream processing

## Usage Example

### Basic Workflow

1. **Load Image** → **NIfTI Stats** → **DeepSeek QC Supervisor**

```
[BIDS Loader]
    ↓
[Subject Selector]
    ↓
[NIfTI Stats (fslstats)]
    ↓ stats_text
[DeepSeek QC Supervisor]
    ↓ qc_status, report_markdown, structured_data
[Preview as Text] + [Conditional Router]
```

### Example Configuration

```python
# NIfTI Stats node
image: "/data/sub-01/anat/sub-01_T1w.nii.gz"
tool: "fslstats"

# DeepSeek QC Supervisor node
stats_text: {{ connected from NIfTI Stats }}
rules_json: {
  "mean": [100, 1000],
  "std": [0, 500],
  "volume_mm3": [800000, 2000000]
}
group_context: "Cohort mean: 450 ± 50, volume: 1.2M ± 0.1M mm³"
ollama_model: "deepseek-r1:7b"
```

## How It Works (The Bridge)

### Internal Logic Flow

1. **Prompt Construction**
   - Wraps inputs into a structured analysis prompt
   - Includes stats, rules, and optional group context
   - Instructs LLM to think step-by-step and provide clear decision

2. **Ollama API Call**
   - Sends payload to `http://localhost:11434/api/generate`
   - Streams reasoning (thought process) and response from DeepSeek-R1
   - Handles connection errors, timeouts, and HTTP errors gracefully

3. **Response Parsing**
   - Extracts QC decision (PASS/WARN/FAIL)
   - Parses reasoning and detailed findings
   - Handles malformed JSON with fallback strategies

4. **Output Generation**
   - Creates visual markdown report with status emoji
   - Formats structured JSON for machine consumption
   - Returns both human-readable and machine-readable outputs

## Visual Feedback

The node provides visual feedback through:

- **Report Markdown** with status emojis:
  - 🟢 PASS - Image meets all quality criteria
  - 🟡 WARN - Minor issues detected, proceed with caution
  - 🔴 FAIL - Critical issues found, exclude from analysis

- **Header Color** (planned feature): Node header changes based on qc_status
  - Future enhancement for at-a-glance status in ComfyUI interface

## Use Cases

### 1. Structural T1w QC
```json
{
  "mean_intensity": [200, 600],
  "std": [50, 300],
  "volume_mm3": [1000000, 1800000],
  "robust_range": [0, 1000]
}
```

### 2. DWI B0 QC
```json
{
  "mean_nonzero": [300, 1200],
  "std_nonzero": [100, 500],
  "volume_nonzero_mm3": [900000, 1600000],
  "percentile_95": [500, 2000]
}
```

### 3. fMRI QC with Cohort Context
```json
{
  "mean_bold": [800, 1200],
  "temporal_snr": [20, 100],
  "fd_mean": [0.0, 0.5]
}
```
Group context: `"Cohort tSNR: 45 ± 8, FD: 0.15 ± 0.08"`

## Troubleshooting

### Ollama Connection Error
```
ERROR: Could not connect to Ollama at http://localhost:11434
```
**Solution**: Start Ollama service
```bash
ollama serve
```

### Model Not Found
```
ERROR: Model 'deepseek-r1:7b' not found
```
**Solution**: Pull the model
```bash
ollama pull deepseek-r1:7b
```

### Timeout Errors
```
ERROR: Request timed out after 60 seconds
```
**Solution**: Increase timeout parameter or use faster model (7b instead of 14b)

### Empty Stats Input
```
ERROR: stats_text is required and cannot be empty
```
**Solution**: Ensure NIfTI Stats node is connected and executed before QC Supervisor

### Invalid JSON in rules_json
```
ERROR: Invalid JSON in rules_json: Expecting property name enclosed in double quotes
```
**Solution**: Validate JSON syntax (use double quotes, proper nesting)

## Advanced Features

### Conditional Workflow Routing

Use the `qc_status` output to route the workflow:

```
[QC Supervisor] → qc_status
    ↓
[Conditional Node]
    ├─ PASS → [Continue Processing]
    ├─ WARN → [Flag for Manual Review]
    └─ FAIL → [Stop Pipeline + Alert]
```

### Batch Processing with Group Context

For cohort studies, aggregate stats from first N subjects, then use as `group_context` for outlier detection:

```python
# After processing first 10 subjects
group_context = """
Cohort statistics (n=10):
- Mean intensity: 425 ± 45
- Volume: 1.15M ± 0.08M mm³
- SNR: 42 ± 6
"""
```

### Custom System Prompts

Tailor the LLM behavior for specific protocols:

```
"You are an expert in ASL imaging QC. Focus on perfusion signal quality,
labeling efficiency, and common ASL artifacts. Be conservative with PASS
decisions - flag anything that might indicate poor labeling or excessive motion."
```

## Technical Details

### API Communication

The node uses the Ollama `/api/generate` endpoint:

```python
POST http://localhost:11434/api/generate
{
  "model": "deepseek-r1:7b",
  "prompt": "...",
  "system": "...",
  "stream": false,
  "options": {"temperature": 0.1}
}
```

### Error Handling

- Connection errors → FAIL status with error message
- Timeout → FAIL status
- Malformed response → WARN status with partial parsing
- Invalid JSON rules → FAIL status before API call

### Performance Considerations

- **7b model**: ~2-5 seconds per analysis (fast)
- **14b model**: ~5-15 seconds per analysis (more accurate)
- **32b model**: ~15-30 seconds per analysis (highest quality)

## Integration with Existing Nodes

### With NIfTI Stats Node

```
[NIfTI Stats] --stats--> [DeepSeek QC Supervisor]
```

### With Brain Mask Node

```
[Brain Mask] → [NIfTI Stats (on mask)] → [QC Supervisor]
```

### Pipeline Integration

```
[BIDS Loader]
    ↓
[Subject Iterator] ────┐
    ↓                  │
[DWI Denoise]          │
    ↓                  │
[NIfTI Stats] ─────────┤
    ↓                  │
[QC Supervisor] ←──────┘
    ↓ (qc_status)
[Conditional Router]
    ├─ PASS → [Continue Eddy Correction]
    ├─ WARN → [Log Warning + Continue]
    └─ FAIL → [Stop + Move to QC Failures Folder]
```

## Future Enhancements

- [ ] Visual header color change based on QC status
- [ ] Integration with ComfyUI's native notification system
- [ ] Database logging of QC decisions
- [ ] Multi-modal QC (analyze multiple images simultaneously)
- [ ] Custom rule templates library
- [ ] QC report aggregation across subjects

## License

Same as parent DiffyUI project

## Credits

- DeepSeek-R1 by DeepSeek AI
- Ollama for local LLM hosting
- ComfyUI framework
- DiffyUI neuroimaging extension
