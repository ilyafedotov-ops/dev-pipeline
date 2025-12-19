"""
Initialize SpecKit Script

Initializes the .specify/ directory structure for a project.

Args:
    project_path: Path to the project directory
    project_name: Name of the project
    constitution_template: Optional custom constitution content

Returns:
    success: Whether initialization succeeded
    paths_created: List of paths that were created
"""

from pathlib import Path


DEFAULT_CONSTITUTION = """# Project Constitution

> Governance principles for AI-driven development

## Article I: Library-First
Prefer using existing libraries over writing custom code.

## Article II: Type Safety
Use type hints and static typing where available.

## Article III: Test-First
Write tests before or alongside implementation.

## Article IV: Documentation
Document public APIs and complex logic.

## Article V: Error Handling
Handle errors explicitly, never silently fail.

## Article VI: Security
Never commit secrets, always validate input.

## Article VII: Simplicity
Prefer simple solutions over clever ones.

## Article VIII: Anti-Abstraction
Avoid premature abstraction. Start concrete.

## Article IX: Integration Testing
Test real integrations, not just mocks.

## Article X: Incremental Delivery
Ship small, working increments.
"""

SPEC_TEMPLATE = """# Feature Specification: {feature_name}

## Summary
<!-- Brief description of the feature -->

## User Stories
- [ ] As a user, I want to...

## Requirements
### Functional
1. 

### Non-Functional
1. 

## Acceptance Criteria
- [ ] 

## Open Questions
- 
"""

PLAN_TEMPLATE = """# Implementation Plan: {feature_name}

## Overview
<!-- Technical approach -->

## Tech Stack
- 

## Components
### New
- 

### Modified
- 

## Risks
- 

## Timeline
- 
"""

TASKS_TEMPLATE = """# Task Breakdown: {feature_name}

## Phase 1: Setup
- [ ] T001: Initialize project structure [DEPENDS: none]

## Phase 2: Core Implementation
- [ ] T002: Implement core logic [DEPENDS: T001]

## Phase 3: Testing
- [ ] T003: Write unit tests [DEPENDS: T002] [PARALLEL]
- [ ] T004: Write integration tests [DEPENDS: T002] [PARALLEL]

## Phase 4: Documentation
- [ ] T005: Update documentation [DEPENDS: T003, T004]
"""


def main(
    project_path: str,
    project_name: str,
    constitution_template: str = "",
) -> dict:
    """Initialize .specify/ directory structure."""
    
    path = Path(project_path)
    if not path.exists():
        return {"success": False, "error": f"Project path does not exist: {project_path}"}
    
    specify_dir = path / ".specify"
    specs_dir = path / "specs"
    paths_created = []
    
    try:
        # Create directory structure
        dirs_to_create = [
            specify_dir,
            specify_dir / "memory",
            specify_dir / "templates",
            specs_dir,
        ]
        
        for dir_path in dirs_to_create:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                paths_created.append(str(dir_path.relative_to(path)))
        
        # Create constitution
        constitution_path = specify_dir / "memory" / "constitution.md"
        if not constitution_path.exists():
            content = constitution_template if constitution_template else DEFAULT_CONSTITUTION
            constitution_path.write_text(content)
            paths_created.append(str(constitution_path.relative_to(path)))
        
        # Create templates
        templates = [
            ("spec-template.md", SPEC_TEMPLATE.format(feature_name="{{feature_name}}")),
            ("plan-template.md", PLAN_TEMPLATE.format(feature_name="{{feature_name}}")),
            ("tasks-template.md", TASKS_TEMPLATE.format(feature_name="{{feature_name}}")),
        ]
        
        for template_name, template_content in templates:
            template_path = specify_dir / "templates" / template_name
            if not template_path.exists():
                template_path.write_text(template_content)
                paths_created.append(str(template_path.relative_to(path)))
        
        # Add .specify to .gitignore runtime section
        gitignore_path = path / ".gitignore"
        gitignore_entry = "\n# DevGodzilla runtime artifacts\nspecs/*/_runtime/runs/\n"
        
        if gitignore_path.exists():
            content = gitignore_path.read_text()
            if "_runtime/runs/" not in content:
                with gitignore_path.open("a") as f:
                    f.write(gitignore_entry)
                paths_created.append(".gitignore (updated)")
        
        return {
            "success": True,
            "paths_created": paths_created,
            "specify_path": str(specify_dir),
            "constitution_path": str(constitution_path),
            "project_name": project_name,
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "paths_created": paths_created}
