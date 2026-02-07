"""
Command executor utility for running system-installed commands.
No Docker - uses local system commands directly.
"""

import os
import subprocess
import logging
import shutil
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SystemExecutor:
    """Execute commands using system-installed tools."""
    
    def __init__(self, tool_name: str):
        """
        Initialize system executor.
        
        Args:
            tool_name: Name of the tool (e.g., "fsl", "mrtrix", "ants")
        """
        self.tool_name = tool_name
        self._check_tool_available()
    
    def _check_tool_available(self):
        """Check if the tool is available in the system PATH."""
        tool_commands = {
            "fsl": ["bet", "fslroi", "eddy"],
            "mrtrix": ["mrconvert", "dwidenoise", "dwifslpreproc"],
            "mrtrix3": ["mrconvert", "dwidenoise", "dwifslpreproc"],
            "ants": ["N4BiasFieldCorrection", "antsRegistration"]
        }
        
        commands = tool_commands.get(self.tool_name.lower(), [])
        if not commands:
            logger.warning(f"Unknown tool: {self.tool_name}")
            return
        
        # Check if at least one command is available
        available = False
        for cmd in commands:
            if shutil.which(cmd):
                available = True
                logger.info(f"Tool {self.tool_name}: {cmd} is available")
                break
        
        if not available:
            logger.warning(f"Tool {self.tool_name} commands not found in PATH. Commands checked: {commands}")
    
    def execute(self, command: List[str], input_files: Optional[Dict[str, str]] = None,
                output_files: Optional[Dict[str, str]] = None,
                working_dir: Optional[str] = None,
                environment: Optional[Dict[str, str]] = None,
                timeout: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Execute a command on the system.
        
        Args:
            command: Command to execute as list of strings
            input_files: Not used (kept for compatibility)
            output_files: Not used (kept for compatibility)
            working_dir: Working directory for command execution
            environment: Environment variables to set
            timeout: Timeout in seconds (None for no timeout)
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        logger.info(f"Executing system command: {' '.join(command)}")
        
        # Prepare environment
        env = os.environ.copy()
        if environment:
            env.update(environment)
        
        # For FSL, ensure FSL environment is set up
        if self.tool_name.lower() == "fsl":
            # Try to source FSL setup if available
            fsl_dir = os.environ.get("FSLDIR", "/usr/share/fsl")
            if Path(fsl_dir).exists():
                env["FSLDIR"] = fsl_dir
                env["FSLOUTPUTTYPE"] = os.environ.get("FSLOUTPUTTYPE", "NIFTI_GZ")
                # Add FSL bin to PATH if not already there
                fsl_bin = Path(fsl_dir) / "bin"
                if fsl_bin.exists():
                    current_path = env.get("PATH", "")
                    if str(fsl_bin) not in current_path:
                        env["PATH"] = f"{fsl_bin}:{current_path}"
        
        try:
            # Execute command
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env=env
            )
            
            if result.returncode != 0:
                logger.error(f"Command failed with return code {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
            
            return result.returncode, result.stdout, result.stderr
        
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout} seconds")
            return -1, "", f"Command timed out after {timeout} seconds"
        
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            return -1, "", str(e)
    
    def check_container_running(self) -> bool:
        """Not applicable for system executor - always returns True."""
        return True
    
    def ensure_container_running(self):
        """Not applicable for system executor - does nothing."""
        pass


def get_executor(tool: str) -> SystemExecutor:
    """
    Get system executor for a specific tool.
    
    Args:
        tool: Tool name ("fsl", "mrtrix", or "ants")
        
    Returns:
        SystemExecutor instance
    """
    return SystemExecutor(tool)
