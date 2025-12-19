"""
Project Setup Script

Full project initialization: clone, analyze, initialize SpecKit, and create database records.

Args:
    git_url: GitHub repository URL
    project_name: Name for the project
    branch: Branch to clone (default: main)
    constitution_template: Optional custom constitution

Returns:
    project_id: Created project ID in database
    project_path: Local path to project
    analysis: Project analysis results
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Import DevGodzilla services if available
try:
    from devgodzilla.db import get_database
    from devgodzilla.services import GitService
    DEVGODZILLA_AVAILABLE = True
except ImportError:
    DEVGODZILLA_AVAILABLE = False


def main(
    git_url: str,
    project_name: str,
    branch: str = "main",
    constitution_template: str = "",
) -> dict:
    """Full project setup with database integration."""
    
    start_time = datetime.now()
    
    # Step 1: Clone repository
    clone_result = _clone_repo(git_url, branch, project_name)
    if not clone_result["success"]:
        return {"error": clone_result["error"], "step": "clone"}
    
    project_path = Path(clone_result["path"])
    
    # Step 2: Analyze project
    analysis = _analyze_project(project_path)
    
    # Step 3: Initialize SpecKit
    speckit_result = _initialize_speckit(project_path, project_name, constitution_template)
    
    # Step 4: Create database record (if available)
    project_id = None
    if DEVGODZILLA_AVAILABLE:
        try:
            db = get_database()
            project = db.create_project({
                "name": project_name,
                "git_url": git_url,
                "local_path": str(project_path),
                "base_branch": branch,
                "project_classification": analysis.get("language", "unknown"),
            })
            project_id = project.id
        except Exception as e:
            # Log but don't fail - database may not be available
            print(f"Warning: Could not create database record: {e}")
    
    return {
        "project_id": project_id,
        "project_name": project_name,
        "project_path": str(project_path),
        "git_url": git_url,
        "branch": branch,
        "commit": clone_result.get("commit"),
        "analysis": analysis,
        "speckit_initialized": speckit_result.get("success", False),
        "constitution_path": speckit_result.get("constitution_path"),
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
    }


def _clone_repo(git_url: str, branch: str, project_name: str) -> dict:
    """Clone repository to workspace."""
    import re
    import shutil
    
    # Extract repo name from URL
    match = re.search(r'/([^/]+?)(?:\.git)?$', git_url)
    repo_name = match.group(1) if match else project_name
    
    target_path = Path("/tmp/devgodzilla/repos") / repo_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    if target_path.exists():
        shutil.rmtree(target_path)
    
    try:
        result = subprocess.run(
            ["git", "clone", "--branch", branch, "--single-branch", "--depth", "100", git_url, str(target_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
        
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(target_path),
            capture_output=True,
            text=True,
        ).stdout.strip()
        
        return {"success": True, "path": str(target_path), "commit": commit}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _analyze_project(project_path: Path) -> dict:
    """Analyze project structure."""
    from collections import Counter
    
    LANGUAGE_MAP = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
    }
    
    extension_counts = Counter()
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ("node_modules", "venv", "__pycache__")]
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in LANGUAGE_MAP:
                extension_counts[ext] += 1
    
    primary_language = "unknown"
    if extension_counts:
        most_common = extension_counts.most_common(1)[0][0]
        primary_language = LANGUAGE_MAP.get(most_common, "unknown")
    
    important_files = []
    for name in ["README.md", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"]:
        if (project_path / name).exists():
            important_files.append(name)
    
    return {
        "language": primary_language,
        "files": important_files,
        "total_files": sum(extension_counts.values()),
    }


def _initialize_speckit(project_path: Path, project_name: str, constitution: str) -> dict:
    """Initialize .specify/ directory."""
    
    specify_dir = project_path / ".specify"
    specs_dir = project_path / "specs"
    paths_created = []
    
    DEFAULT_CONSTITUTION = """# Project Constitution

## Article I: Library-First
Prefer existing libraries over custom code.

## Article III: Test-First
Write tests before implementation.

## Article V: Error Handling
Handle errors explicitly, never silently fail.

## Article VII: Simplicity
Prefer simple solutions over clever ones.
"""
    
    try:
        for subdir in ["memory", "templates"]:
            (specify_dir / subdir).mkdir(parents=True, exist_ok=True)
            paths_created.append(f".specify/{subdir}")

        specs_dir.mkdir(parents=True, exist_ok=True)
        paths_created.append("specs")
        
        constitution_path = specify_dir / "memory" / "constitution.md"
        if not constitution_path.exists():
            content = constitution if constitution else DEFAULT_CONSTITUTION
            constitution_path.write_text(content)
        
        return {
            "success": True,
            "paths_created": paths_created,
            "constitution_path": str(constitution_path),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
