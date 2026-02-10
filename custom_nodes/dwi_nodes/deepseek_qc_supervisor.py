"""
ComfyUI DeepSeek QC Supervisor Node
A specialized node that interfaces with a local Ollama instance (running DeepSeek-R1)
to perform automated Quality Control on neuroimaging data by comparing live
fslstats/mrinfo text outputs against predefined JSON standards and group averages.
"""

import json
import requests
from typing import Dict, Any, Tuple


class DeepSeekQCSupervisorNode:
    """
    DeepSeek QC Supervisor - Automated neuroimaging quality control using DeepSeek-R1 via Ollama.

    This node acts as a bridge between neuroimaging QC data and a local LLM reasoning engine,
    providing automated analysis and decision-making for pipeline integrity checks.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "stats_text": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Raw text output from neuroimaging tools (e.g., fslstats -R -M -V or mrinfo -property)"
                }),
                "rules_json": ("STRING", {
                    "default": '{"mean_intensity": [200, 500], "voxel_size": [1, 1, 1]}',
                    "multiline": True,
                    "tooltip": "JSON dictionary defining expected ranges and validation rules"
                }),
            },
            "optional": {
                "group_context": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Optional: Summary of previous runs (mean/std) for outlier detection relative to current cohort"
                }),
                "ollama_model": (["deepseek-r1:7b", "deepseek-r1:14b", "deepseek-r1:32b", "deepseek-r1:latest"], {
                    "default": "deepseek-r1:7b",
                    "tooltip": "DeepSeek-R1 model variant to use for analysis"
                }),
                "system_prompt": ("STRING", {
                    "default": "You are a Senior Neuroimaging Analyst specializing in pipeline quality control. Your role is to analyze neuroimaging statistics, compare them against established standards, and make clear QC decisions to ensure pipeline integrity. Think step-by-step and provide reasoned judgments.",
                    "multiline": True,
                    "tooltip": "System instructions for the LLM to guide its analysis approach"
                }),
                "ollama_url": ("STRING", {
                    "default": "http://localhost:11434",
                    "tooltip": "Ollama API endpoint URL"
                }),
                "temperature": ("FLOAT", {
                    "default": 0.1,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "LLM temperature (lower = more deterministic)"
                }),
                "timeout": ("INT", {
                    "default": 60,
                    "min": 10,
                    "max": 300,
                    "tooltip": "Request timeout in seconds"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("qc_status", "report_markdown", "structured_data")
    FUNCTION = "run_qc_analysis"
    CATEGORY = "DWI/QC"
    DESCRIPTION = "Automated QC analysis using DeepSeek-R1 via Ollama. Compares neuroimaging stats against rules and provides PASS/WARN/FAIL decisions with detailed reasoning."
    OUTPUT_NODE = True

    def _construct_analysis_prompt(
        self,
        stats_text: str,
        rules_json: str,
        group_context: str
    ) -> str:
        """
        Construct a structured prompt for the LLM to analyze QC data.

        Args:
            stats_text: Raw neuroimaging statistics
            rules_json: JSON validation rules
            group_context: Optional cohort baseline data

        Returns:
            Formatted prompt string for the LLM
        """
        prompt_parts = [
            "# Neuroimaging Quality Control Analysis\n",
            "Analyze the following neuroimaging statistics and make a QC decision.\n",
            "\n## Current Image Statistics:",
            stats_text.strip(),
            "\n## Validation Rules:",
            rules_json.strip(),
        ]

        if group_context and group_context.strip():
            prompt_parts.extend([
                "\n## Group Context (Cohort Baseline):",
                group_context.strip(),
            ])

        prompt_parts.extend([
            "\n## Task:",
            "1. Parse and understand the image statistics",
            "2. Compare against the validation rules",
            "3. If group context is provided, check for outliers relative to the cohort",
            "4. Think step-by-step about potential issues",
            "5. Make a final QC decision: PASS, WARN, or FAIL",
            "\n## Output Format:",
            "Provide your analysis and then conclude with:",
            "QC_DECISION: [PASS/WARN/FAIL]",
            "REASON: [Brief explanation]",
            "DETAILS: [Key metrics and findings in JSON format]",
        ])

        return "\n".join(prompt_parts)

    def _call_ollama_api(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        ollama_url: str,
        temperature: float,
        timeout: int
    ) -> Tuple[str, str]:
        """
        Call the Ollama API with the constructed prompt.

        Args:
            prompt: The analysis prompt
            system_prompt: System instructions for the LLM
            model: Model name/tag
            ollama_url: Ollama API base URL
            temperature: Sampling temperature
            timeout: Request timeout

        Returns:
            Tuple of (full_response_text, error_message)
        """
        api_endpoint = f"{ollama_url.rstrip('/')}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        try:
            print(f"[DeepSeek QC] Calling Ollama API at {api_endpoint} with model {model}", flush=True)
            response = requests.post(
                api_endpoint,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()

            result = response.json()
            response_text = result.get("response", "")

            if not response_text:
                return "", "Empty response from Ollama API"

            print(f"[DeepSeek QC] Received response ({len(response_text)} chars)", flush=True)
            return response_text, ""

        except requests.exceptions.Timeout:
            error = f"Request timed out after {timeout} seconds"
            print(f"[DeepSeek QC] ERROR: {error}", flush=True)
            return "", error
        except requests.exceptions.ConnectionError:
            error = f"Could not connect to Ollama at {api_endpoint}. Is Ollama running?"
            print(f"[DeepSeek QC] ERROR: {error}", flush=True)
            return "", error
        except requests.exceptions.HTTPError as e:
            error = f"HTTP error: {e}. Response: {e.response.text if hasattr(e, 'response') else 'N/A'}"
            print(f"[DeepSeek QC] ERROR: {error}", flush=True)
            return "", error
        except Exception as e:
            error = f"Unexpected error calling Ollama API: {str(e)}"
            print(f"[DeepSeek QC] ERROR: {error}", flush=True)
            return "", error

    def _parse_qc_decision(self, response_text: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Parse the LLM response to extract QC decision, reasoning, and structured data.

        Args:
            response_text: Full LLM response text

        Returns:
            Tuple of (qc_status, reason, details_dict)
        """
        qc_status = "WARN"  # Default to WARN if parsing fails
        reason = "Unable to parse LLM response"
        details = {}

        try:
            # Look for QC_DECISION line
            for line in response_text.split('\n'):
                line_upper = line.upper().strip()

                if line_upper.startswith("QC_DECISION:"):
                    decision_part = line_upper.split("QC_DECISION:", 1)[1].strip()
                    if "PASS" in decision_part:
                        qc_status = "PASS"
                    elif "FAIL" in decision_part:
                        qc_status = "FAIL"
                    elif "WARN" in decision_part:
                        qc_status = "WARN"

                elif line_upper.startswith("REASON:"):
                    reason = line.split("REASON:", 1)[1].strip()

                elif line_upper.startswith("DETAILS:"):
                    # Try to parse JSON details
                    details_str = line.split("DETAILS:", 1)[1].strip()
                    try:
                        details = json.loads(details_str)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, store as raw string
                        details = {"raw": details_str}

            # If no explicit decision found, try to infer from response
            if qc_status == "WARN" and reason == "Unable to parse LLM response":
                response_lower = response_text.lower()
                if "pass" in response_lower and "fail" not in response_lower:
                    qc_status = "PASS"
                    reason = "Inferred from response content"
                elif "fail" in response_lower:
                    qc_status = "FAIL"
                    reason = "Inferred from response content"
                else:
                    reason = "No clear decision in response"

        except Exception as e:
            print(f"[DeepSeek QC] Error parsing response: {e}", flush=True)
            reason = f"Parsing error: {str(e)}"

        return qc_status, reason, details

    def _create_markdown_report(
        self,
        qc_status: str,
        reason: str,
        full_response: str,
        details: Dict[str, Any]
    ) -> str:
        """
        Create a formatted markdown report with visual indicators.

        Args:
            qc_status: PASS/WARN/FAIL
            reason: Brief explanation
            full_response: Complete LLM response
            details: Structured findings

        Returns:
            Formatted markdown string
        """
        # Status emoji
        status_emoji = {
            "PASS": "🟢",
            "WARN": "🟡",
            "FAIL": "🔴"
        }.get(qc_status, "⚪")

        report_parts = [
            f"# {status_emoji} QC Analysis Report\n",
            f"**Status:** {qc_status}\n",
            f"**Summary:** {reason}\n",
        ]

        if details:
            report_parts.append("\n## Key Findings\n")
            for key, value in details.items():
                report_parts.append(f"- **{key}:** {value}")
            report_parts.append("")

        report_parts.extend([
            "\n## Detailed Analysis\n",
            "```",
            full_response.strip(),
            "```"
        ])

        return "\n".join(report_parts)

    def run_qc_analysis(
        self,
        stats_text: str,
        rules_json: str,
        group_context: str = "",
        ollama_model: str = "deepseek-r1:7b",
        system_prompt: str = "",
        ollama_url: str = "http://localhost:11434",
        temperature: float = 0.1,
        timeout: int = 60
    ):
        """
        Main execution function for QC analysis.

        Args:
            stats_text: Raw neuroimaging statistics
            rules_json: JSON validation rules
            group_context: Optional cohort baseline
            ollama_model: DeepSeek model variant
            system_prompt: System instructions
            ollama_url: Ollama API URL
            temperature: LLM temperature
            timeout: Request timeout

        Returns:
            Dictionary with UI and result outputs
        """
        print(f"[DeepSeek QC] Starting analysis with model {ollama_model}", flush=True)

        # Validate inputs
        if not stats_text or not stats_text.strip():
            error_msg = "❌ Error: stats_text is required and cannot be empty"
            print(f"[DeepSeek QC] {error_msg}", flush=True)
            return {
                "ui": {"text": (error_msg,)},
                "result": ("FAIL", error_msg, json.dumps({"error": "Empty stats_text"}))
            }

        # Validate rules_json
        try:
            rules = json.loads(rules_json)
            if not isinstance(rules, dict):
                raise ValueError("rules_json must be a JSON object (dictionary)")
        except json.JSONDecodeError as e:
            error_msg = f"❌ Error: Invalid JSON in rules_json: {str(e)}"
            print(f"[DeepSeek QC] {error_msg}", flush=True)
            return {
                "ui": {"text": (error_msg,)},
                "result": ("FAIL", error_msg, json.dumps({"error": str(e)}))
            }

        # Use default system prompt if not provided
        if not system_prompt or not system_prompt.strip():
            system_prompt = "You are a Senior Neuroimaging Analyst specializing in pipeline quality control. Your role is to analyze neuroimaging statistics, compare them against established standards, and make clear QC decisions to ensure pipeline integrity. Think step-by-step and provide reasoned judgments."

        # Step 1: Construct the analysis prompt
        prompt = self._construct_analysis_prompt(stats_text, rules_json, group_context)

        # Step 2: Call Ollama API
        response_text, error = self._call_ollama_api(
            prompt, system_prompt, ollama_model, ollama_url, temperature, timeout
        )

        if error:
            error_msg = f"❌ Ollama API Error: {error}"
            return {
                "ui": {"text": (error_msg,)},
                "result": ("FAIL", error_msg, json.dumps({"error": error}))
            }

        # Step 3: Parse the response
        qc_status, reason, details = self._parse_qc_decision(response_text)

        # Step 4: Create markdown report
        report_markdown = self._create_markdown_report(qc_status, reason, response_text, details)

        # Step 5: Create structured data output
        structured_data = json.dumps({
            "qc_status": qc_status,
            "reason": reason,
            "details": details,
            "model": ollama_model,
            "timestamp": None,  # Could add timestamp if needed
        }, indent=2)

        print(f"[DeepSeek QC] Analysis complete. Status: {qc_status}", flush=True)

        # Return all outputs
        return {
            "ui": {
                "text": (report_markdown,),
            },
            "result": (qc_status, report_markdown, structured_data)
        }
