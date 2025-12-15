"""
DevGodzilla Constitution Service

Manages project governance constitutions - markdown files with articles
that define development principles and quality gates.

Constitution files are stored at `.specify/memory/constitution.md` in project repos.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)

# Default path for constitution file
DEFAULT_CONSTITUTION_PATH = ".specify/memory/constitution.md"


@dataclass
class Article:
    """A single article from a constitution."""
    number: str  # E.g., "I", "II", "III"
    title: str
    content: str
    blocking: bool = False
    
    @property
    def gate_name(self) -> str:
        """Gate name for QA integration."""
        return f"article_{self.number.lower()}"


@dataclass
class Constitution:
    """Parsed constitution with articles."""
    version: str
    content: str
    articles: List[Article]
    hash: str
    source_path: Optional[str] = None
    
    @classmethod
    def empty(cls) -> "Constitution":
        """Create an empty constitution."""
        return cls(
            version="0.0.0",
            content="",
            articles=[],
            hash="empty",
        )
    
    def get_article(self, number: str) -> Optional[Article]:
        """Get an article by number."""
        for article in self.articles:
            if article.number.upper() == number.upper():
                return article
        return None
    
    def get_blocking_articles(self) -> List[Article]:
        """Get all blocking articles."""
        return [a for a in self.articles if a.blocking]
    
    def get_warning_articles(self) -> List[Article]:
        """Get all warning-only articles."""
        return [a for a in self.articles if not a.blocking]


# Default blocking articles per architecture spec
DEFAULT_BLOCKING_ARTICLES = {"III", "IV", "IX"}


def parse_constitution(
    content: str,
    *,
    blocking_articles: Optional[set] = None,
) -> List[Article]:
    """
    Parse constitution markdown into articles.
    
    Expected format:
    ```markdown
    # Project Constitution
    
    ## Article I: Title Here
    Article content...
    
    ## Article II: Another Title
    More content...
    ```
    
    Args:
        content: Constitution markdown content
        blocking_articles: Set of article numbers that are blocking (default: III, IV, IX)
        
    Returns:
        List of parsed Article objects
    """
    if not content:
        return []
    
    blocking = blocking_articles or DEFAULT_BLOCKING_ARTICLES
    articles = []
    
    # Pattern: ## Article [Roman Numeral]: [Title]
    article_pattern = r'^## Article ([IVXLCDM]+):\s*(.+)$'
    
    lines = content.split('\n')
    current_article = None
    current_content: List[str] = []
    
    for line in lines:
        match = re.match(article_pattern, line, re.IGNORECASE)
        if match:
            # Save previous article
            if current_article:
                article_content = '\n'.join(current_content).strip()
                articles.append(Article(
                    number=current_article[0],
                    title=current_article[1],
                    content=article_content,
                    blocking=current_article[0].upper() in blocking,
                ))
            
            # Start new article
            current_article = (match.group(1), match.group(2))
            current_content = []
        elif current_article:
            current_content.append(line)
    
    # Don't forget the last article
    if current_article:
        article_content = '\n'.join(current_content).strip()
        articles.append(Article(
            number=current_article[0],
            title=current_article[1],
            content=article_content,
            blocking=current_article[0].upper() in blocking,
        ))
    
    return articles


def hash_constitution(content: str) -> str:
    """Generate a stable hash for constitution content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def extract_version(content: str) -> str:
    """
    Extract version from constitution content.
    
    Looks for a version line like: `Version: 1.0.0` or `## Version 1.0`
    """
    if not content:
        return "1.0.0"
    
    # Try pattern: Version: X.Y.Z
    match = re.search(r'Version:\s*(\d+(?:\.\d+)*)', content, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Try pattern: ## Version X.Y
    match = re.search(r'^## Version\s+(\d+(?:\.\d+)*)', content, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1)
    
    return "1.0.0"


class ConstitutionService(Service):
    """
    Service for loading and managing project constitutions.
    
    Constitutions define project governance principles through articles
    that can be enforced as QA gates.
    
    Example:
        constitution_svc = ConstitutionService(context, db)
        
        # Load from project repository
        constitution = constitution_svc.load_from_repo(
            project_id=1,
            repo_root=Path("/path/to/repo")
        )
        
        # Get blocking articles for QA
        blocking = constitution.get_blocking_articles()
    """

    def __init__(self, context: ServiceContext, db) -> None:
        super().__init__(context)
        self.db = db

    def load_from_repo(
        self,
        project_id: int,
        repo_root: Path,
        *,
        constitution_path: Optional[str] = None,
        blocking_articles: Optional[set] = None,
    ) -> Constitution:
        """
        Load constitution from a project repository.
        
        Args:
            project_id: Project ID
            repo_root: Repository root path
            constitution_path: Custom path to constitution file (relative to repo_root)
            blocking_articles: Override set of blocking article numbers
            
        Returns:
            Parsed Constitution object
        """
        path = repo_root / (constitution_path or DEFAULT_CONSTITUTION_PATH)
        
        if not path.exists():
            self.logger.debug(
                "constitution_not_found",
                extra=self.log_extra(project_id=project_id, path=str(path)),
            )
            return Constitution.empty()
        
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.warning(
                "constitution_read_error",
                extra=self.log_extra(project_id=project_id, path=str(path), error=str(e)),
            )
            return Constitution.empty()
        
        articles = parse_constitution(content, blocking_articles=blocking_articles)
        version = extract_version(content)
        content_hash = hash_constitution(content)
        
        constitution = Constitution(
            version=version,
            content=content,
            articles=articles,
            hash=content_hash,
            source_path=str(path),
        )
        
        self.logger.info(
            "constitution_loaded",
            extra=self.log_extra(
                project_id=project_id,
                version=version,
                hash=content_hash,
                article_count=len(articles),
                blocking_count=len(constitution.get_blocking_articles()),
            ),
        )
        
        return constitution

    def persist_constitution_metadata(
        self,
        project_id: int,
        constitution: Constitution,
    ) -> None:
        """
        Persist constitution version and hash to project for tracking.
        
        Args:
            project_id: Project ID
            constitution: Loaded constitution
        """
        self.db.update_project(
            project_id,
            constitution_version=constitution.version,
            constitution_hash=constitution.hash,
        )

    def get_default_constitution(self) -> Constitution:
        """
        Get the default constitution template.
        
        Returns a standard constitution with common development principles.
        """
        content = """# Project Constitution

Version: 1.0.0

## Article I: Library-First Development
Prefer existing, well-tested libraries over custom implementations.
Write less code. Leverage the ecosystem.

## Article II: Documentation-Driven
Document intent before implementation. README-first approach.

## Article III: Test-First Development
Write failing tests before implementation code.
No feature is complete without tests.

## Article IV: Security by Default
Never store secrets in code. Use environment variables.
Validate all inputs. Sanitize all outputs.

## Article V: Accessibility
All UI components must meet WCAG 2.1 AA standards.

## Article VI: Performance Budgets
Define and enforce performance budgets for all features.

## Article VII: Simplicity
Prefer simple solutions over complex ones.
When in doubt, choose the simpler approach.

## Article VIII: Anti-Abstraction
Duplicate code 3 times before abstracting.
Avoid premature abstraction.

## Article IX: Integration Testing
Every feature must have integration tests.
Unit tests are not sufficient for feature completeness.

## Article X: Incremental Delivery
Ship small, complete increments. Each commit should be deployable.
"""
        articles = parse_constitution(content)
        return Constitution(
            version="1.0.0",
            content=content,
            articles=articles,
            hash=hash_constitution(content),
        )

    def create_constitution_file(
        self,
        repo_root: Path,
        *,
        constitution_path: Optional[str] = None,
        template: Optional[Constitution] = None,
    ) -> Path:
        """
        Create a constitution file in a repository.
        
        Args:
            repo_root: Repository root path
            constitution_path: Custom path for the file
            template: Constitution to use as template (default: default constitution)
            
        Returns:
            Path to the created file
        """
        path = repo_root / (constitution_path or DEFAULT_CONSTITUTION_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        constitution = template or self.get_default_constitution()
        path.write_text(constitution.content, encoding="utf-8")
        
        self.logger.info(
            "constitution_created",
            extra={"path": str(path), "version": constitution.version},
        )
        
        return path

    def validate_constitution(
        self,
        constitution: Constitution,
    ) -> List[str]:
        """
        Validate a constitution for common issues.
        
        Returns list of warning messages.
        """
        warnings = []
        
        if not constitution.articles:
            warnings.append("Constitution has no articles")
        
        if not constitution.get_blocking_articles():
            warnings.append("Constitution has no blocking articles defined")
        
        # Check for duplicate article numbers
        numbers = [a.number.upper() for a in constitution.articles]
        if len(numbers) != len(set(numbers)):
            warnings.append("Constitution has duplicate article numbers")
        
        # Check for empty content
        for article in constitution.articles:
            if not article.content.strip():
                warnings.append(f"Article {article.number} has no content")
        
        return warnings
