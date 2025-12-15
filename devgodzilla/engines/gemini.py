"""
DevGodzilla Gemini CLI Engine

Engine adapter for Google Gemini CLI tool.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from devgodzilla.engines.interface import (
    EngineInterface,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    EngineCapability,
)


class GeminiEngine(EngineInterface):
    """
    Engine adapter for Gemini CLI.
    
    Uses the `gemini` CLI tool to execute coding tasks.
    Supports multimodal inputs and long context.
    """
    
    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        timeout: int = 300,
        command: str = "gemini",
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._command = command
    
    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_id="gemini-cli",
            name="Gemini CLI",
            version="1.0.0",
            capabilities=[
                EngineCapability.CODE_GENERATION,
                EngineCapability.CODE_REVIEW,
                EngineCapability.MULTIMODAL,
                EngineCapability.LONG_CONTEXT,
            ],
            default_model=self._model,
            supported_models=[
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
            ],
        )
    
    def execute(self, request: EngineRequest) -> EngineResult:
        """Execute a coding task using Gemini CLI."""
        try:
            # Build command
            cmd = [self._command]
            
            # Add model if specified
            if request.model:
                cmd.extend(["--model", request.model])
            
            # Write prompt to temp file if long
            prompt = self._build_prompt(request)
            
            if len(prompt) > 1000:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".md", delete=False
                ) as f:
                    f.write(prompt)
                    prompt_file = f.name
                cmd.extend(["--prompt-file", prompt_file])
            else:
                cmd.extend(["--prompt", prompt])
            
            # Set working directory
            cwd = request.workspace_path or "."
            
            # Execute
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            
            if result.returncode == 0:
                return EngineResult(
                    success=True,
                    output=result.stdout,
                    files_modified=[],  # Parse from output if available
                    metadata={
                        "model": request.model or self._model,
                        "engine": "gemini-cli",
                    },
                )
            else:
                return EngineResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr or "Gemini CLI returned non-zero exit code",
                    metadata={"returncode": result.returncode},
                )
                
        except subprocess.TimeoutExpired:
            return EngineResult(
                success=False,
                error=f"Gemini CLI timed out after {self._timeout}s",
            )
        except FileNotFoundError:
            return EngineResult(
                success=False,
                error=f"Gemini CLI not found. Install with: pip install gemini-cli",
            )
        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Gemini CLI error: {e}",
            )
    
    def check_availability(self) -> bool:
        """Check if Gemini CLI is available."""
        try:
            result = subprocess.run(
                [self._command, "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _build_prompt(self, request: EngineRequest) -> str:
        """Build the prompt from request."""
        parts = []
        
        if request.system_prompt:
            parts.append(f"## System Instructions\n{request.system_prompt}\n")
        
        parts.append(f"## Task\n{request.prompt}\n")
        
        if request.context:
            parts.append(f"## Context\n{request.context}\n")
        
        if request.constraints:
            constraints = "\n".join(f"- {c}" for c in request.constraints)
            parts.append(f"## Constraints\n{constraints}\n")
        
        return "\n".join(parts)
