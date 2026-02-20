"""
OrgMind AI Project Management - Schedulers (Phase 2 & 3)

This package contains the scheduling algorithms for the AI-powered
project management system:

Phase 2:
- PriorityCalculator: Calculates project priority scores
- ImpactAnalyzer: Analyzes ripple effects of changes
- NudgeGenerator: Generates AI-powered proactive notifications
- SkillMatcher: Matches tasks to people based on skills

Phase 3:
- SprintPlanner: AI-assisted sprint planning
- VelocityCalculator: Productivity tracking
- ConflictDetector: Resource conflict detection
"""

from .priority_calculator import PriorityCalculator
from .impact_analyzer import ImpactAnalyzer
from .nudge_generator import NudgeGenerator
from .skill_matcher import SkillMatcher
from .sprint_planner import SprintPlanner
from .velocity_calculator import VelocityCalculator
from .conflict_detector import ConflictDetector

__all__ = [
    # Phase 2
    "PriorityCalculator",
    "ImpactAnalyzer", 
    "NudgeGenerator",
    "SkillMatcher",
    # Phase 3
    "SprintPlanner",
    "VelocityCalculator",
    "ConflictDetector",
]
