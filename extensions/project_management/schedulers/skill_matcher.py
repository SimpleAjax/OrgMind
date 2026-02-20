"""
Skill Matcher Scheduler

Matches tasks to people based on required skills and proficiency levels.

Matching Algorithm:
```
match_score = Σ(skill_match × weight) / Σ(weights)

where skill_match =
    1.0 if person_proficiency >= required_proficiency
    person_proficiency / required_proficiency × 0.5 if below
    0 if missing required skill
```

Usage:
    matcher = SkillMatcher(db_adapter)
    
    # Find best matches for a task
    matches = await matcher.find_best_matches(task_id, limit=5)
    
    # Calculate match score for specific person
    score = await matcher.calculate_skill_match(person_id, task_id)
    
    # Identify org-wide skill gaps
    gaps = await matcher.identify_skill_gaps()
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, and_, or_

from .base import SchedulerBase, ObjectModel, Session

logger = logging.getLogger(__name__)


@dataclass
class SkillMatchResult:
    """Result of skill matching for a person-task pair."""
    person_id: str
    person_name: str
    match_score: float  # 0-100
    is_full_match: bool
    matching_skills: List[Dict[str, Any]]
    missing_skills: List[Dict[str, Any]]
    below_required: List[Dict[str, Any]]  # Has skill but below required level
    development_opportunities: List[Dict[str, Any]]
    availability_percent: float
    recommendation: str


@dataclass
class SkillGap:
    """Represents an organization-wide skill gap."""
    skill_id: str
    skill_name: str
    skill_category: str
    tasks_requiring: int
    qualified_people: int
    gap_severity: str  # 'critical', 'high', 'medium', 'low'
    affected_task_ids: List[str]
    training_suggestions: List[str]


class SkillMatcher(SchedulerBase):
    """
    Matches tasks to people based on required skills and proficiency.
    
    Features:
    - Calculate skill match scores
    - Find best matches for tasks
    - Identify organization-wide skill gaps
    - Suggest training paths
    """
    
    # Proficiency levels
    PROFICIENCY_LEVELS = {
        1: 'Beginner',
        2: 'Intermediate',
        3: 'Advanced',
        4: 'Expert'
    }
    
    # Score thresholds
    EXCELLENT_MATCH = 90
    GOOD_MATCH = 70
    ACCEPTABLE_MATCH = 50
    
    def __init__(self, db_adapter=None, neo4j_adapter=None):
        super().__init__(db_adapter, neo4j_adapter)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def run(self) -> Dict[str, Any]:
        """
        Run skill matching analysis.
        
        Returns:
            Summary of skill matching analysis
        """
        gaps = await self.identify_skill_gaps()
        return {
            'skill_gaps_identified': len(gaps),
            'critical_gaps': sum(1 for g in gaps if g.gap_severity == 'critical'),
            'high_gaps': sum(1 for g in gaps if g.gap_severity == 'high'),
            'gaps': [
                {
                    'skill_name': g.skill_name,
                    'severity': g.gap_severity,
                    'tasks_affected': g.tasks_requiring,
                    'qualified_people': g.qualified_people
                }
                for g in gaps[:10]  # Top 10 gaps
            ]
        }
    
    async def find_best_matches(
        self,
        task_id: str,
        limit: int = 5,
        min_score: float = 0.0
    ) -> List[SkillMatchResult]:
        """
        Find the best people for a given task.
        
        Args:
            task_id: Task to find matches for
            limit: Maximum number of matches to return
            min_score: Minimum match score (0-100) to include
            
        Returns:
            List of SkillMatchResult, sorted by match score (best first)
        """
        self.logger.info(f"Finding best matches for task {task_id}")
        
        with self.get_session() as session:
            task = self.get_object_by_id(session, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Get task skill requirements
            skill_requirements = self._get_task_skill_requirements(session, task_id)
            
            if not skill_requirements:
                # No specific requirements - return available people
                return self._get_available_people(session, limit)
            
            # Get all active people
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            matches = []
            for person in people:
                match_result = self._calculate_match(
                    session, person, skill_requirements, task
                )
                
                if match_result.match_score >= min_score:
                    matches.append(match_result)
            
            # Sort by match score (descending)
            matches.sort(key=lambda x: x.match_score, reverse=True)
            
            self.logger.info(
                f"Found {len(matches)} matches for task {task_id}, "
                f"returning top {limit}"
            )
            
            return matches[:limit]
    
    async def calculate_skill_match(
        self,
        person_id: str,
        task_id: str
    ) -> SkillMatchResult:
        """
        Calculate detailed skill match for a person-task pair.
        
        Args:
            person_id: Person to evaluate
            task_id: Task to match against
            
        Returns:
            Detailed SkillMatchResult
        """
        with self.get_session() as session:
            person = self.get_object_by_id(session, person_id)
            if not person:
                raise ValueError(f"Person {person_id} not found")
            
            task = self.get_object_by_id(session, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            skill_requirements = self._get_task_skill_requirements(session, task_id)
            
            if not skill_requirements:
                # No specific requirements
                availability = self._calculate_availability(session, person_id)
                return SkillMatchResult(
                    person_id=person_id,
                    person_name=person.data.get('name', 'Unknown'),
                    match_score=50.0,  # Neutral score when no requirements
                    is_full_match=True,
                    matching_skills=[],
                    missing_skills=[],
                    below_required=[],
                    development_opportunities=[],
                    availability_percent=availability,
                    recommendation="No specific skill requirements for this task"
                )
            
            return self._calculate_match(session, person, skill_requirements, task)
    
    async def identify_skill_gaps(self) -> List[SkillGap]:
        """
        Identify organization-wide skill gaps.
        
        Analyzes all tasks with skill requirements and compares against
        available talent pool.
        
        Returns:
            List of SkillGap objects, sorted by severity
        """
        self.logger.info("Identifying organization-wide skill gaps")
        
        with self.get_session() as session:
            # Get all skill requirements across all tasks
            all_requirements = self._get_all_skill_requirements(session)
            
            # Group by skill
            skill_stats = {}
            for req in all_requirements:
                skill_id = req['skill_id']
                min_proficiency = req['min_proficiency']
                
                if skill_id not in skill_stats:
                    skill_stats[skill_id] = {
                        'tasks': [],
                        'max_required_level': 0
                    }
                
                skill_stats[skill_id]['tasks'].append(req['task_id'])
                skill_stats[skill_id]['max_required_level'] = max(
                    skill_stats[skill_id]['max_required_level'],
                    min_proficiency
                )
            
            # Count qualified people for each skill
            gaps = []
            for skill_id, stats in skill_stats.items():
                skill = self.get_object_by_id(session, skill_id)
                if not skill:
                    continue
                
                qualified_count = self._count_qualified_people(
                    session, skill_id, stats['max_required_level']
                )
                
                # Calculate gap severity
                tasks_count = len(stats['tasks'])
                
                if qualified_count == 0 and tasks_count > 5:
                    severity = 'critical'
                elif qualified_count == 0:
                    severity = 'high'
                elif qualified_count < tasks_count / 3:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                gaps.append(SkillGap(
                    skill_id=skill_id,
                    skill_name=skill.data.get('name', 'Unknown'),
                    skill_category=skill.data.get('category', 'unknown'),
                    tasks_requiring=tasks_count,
                    qualified_people=qualified_count,
                    gap_severity=severity,
                    affected_task_ids=stats['tasks'],
                    training_suggestions=self._suggest_training(skill)
                ))
            
            # Sort by severity (critical first)
            severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            gaps.sort(key=lambda x: severity_order.get(x.gap_severity, 4))
            
            self.logger.info(f"Found {len(gaps)} skill gaps")
            return gaps
    
    async def suggest_training(
        self,
        skill_gap: Optional[SkillGap] = None,
        person_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Suggest training paths to address skill gaps.
        
        Args:
            skill_gap: Specific skill gap to address
            person_id: Specific person to train (or None for general suggestions)
            
        Returns:
            List of training recommendations
        """
        suggestions = []
        
        with self.get_session() as session:
            if skill_gap and person_id:
                # Personalized training suggestion
                person = self.get_object_by_id(session, person_id)
                if person:
                    # Check related skills
                    related_skills = self._find_related_skills(session, skill_gap.skill_id)
                    
                    person_skills = self.get_linked_objects(
                        session, person_id, link_type_id='lt_person_has_skill'
                    )
                    person_skill_ids = {
                        s['object'].data.get('skill_id') 
                        for s in person_skills
                    }
                    
                    # Find skills person has that are related
                    has_related = [
                        s for s in related_skills 
                        if s['skill_id'] in person_skill_ids
                    ]
                    
                    if has_related:
                        suggestions.append({
                            'type': 'related_skill_building',
                            'description': (
                                f"Build on existing skills: {', '.join(s['name'] for s in has_related)}"
                            ),
                            'estimated_duration_weeks': 4,
                            'priority': 'high'
                        })
                    
                    suggestions.append({
                        'type': 'formal_training',
                        'description': f"Formal training for {skill_gap.skill_name}",
                        'estimated_duration_weeks': 8,
                        'priority': 'high' if skill_gap.gap_severity == 'critical' else 'medium'
                    })
            
            elif skill_gap:
                # General training suggestions for skill gap
                suggestions.extend([
                    {
                        'type': 'group_training',
                        'description': f"Organize group training for {skill_gap.skill_name}",
                        'target_audience': 'team_members',
                        'estimated_duration_weeks': 6
                    },
                    {
                        'type': 'external_course',
                        'description': f"External certification in {skill_gap.skill_name}",
                        'target_audience': 'senior_members',
                        'estimated_duration_weeks': 12
                    }
                ])
            
            else:
                # Organization-wide training recommendations
                gaps = await self.identify_skill_gaps()
                critical_gaps = [g for g in gaps if g.gap_severity in ['critical', 'high']]
                
                if critical_gaps:
                    suggestions.append({
                        'type': 'urgent_training_program',
                        'description': (
                            f"Urgent training program for critical gaps: "
                            f"{', '.join(g.skill_name for g in critical_gaps[:3])}"
                        ),
                        'priority': 'critical',
                        'estimated_duration_weeks': 12
                    })
        
        return suggestions
    
    def _get_task_skill_requirements(
        self,
        session: Session,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """Get skill requirements for a task."""
        skill_reqs = self.get_linked_objects(
            session, task_id, link_type_id='lt_task_requires_skill'
        )
        
        requirements = []
        for req in skill_reqs:
            req_obj = req['object']
            skill_id = req_obj.data.get('skill_id')
            
            skill = self.get_object_by_id(session, skill_id)
            if skill:
                requirements.append({
                    'skill_id': skill_id,
                    'skill_name': skill.data.get('name', 'Unknown'),
                    'skill_category': skill.data.get('category', 'unknown'),
                    'min_proficiency': req_obj.data.get('minimum_proficiency', 1),
                    'preferred_proficiency': req_obj.data.get('preferred_proficiency'),
                    'is_mandatory': req_obj.data.get('is_mandatory', True),
                    'weight': 2.0 if req_obj.data.get('is_mandatory', True) else 1.0
                })
        
        return requirements
    
    def _calculate_match(
        self,
        session: Session,
        person: ObjectModel,
        skill_requirements: List[Dict[str, Any]],
        task: ObjectModel
    ) -> SkillMatchResult:
        """Calculate skill match for a person against requirements."""
        
        # Get person's skills
        person_skills = self.get_linked_objects(
            session, person.id, link_type_id='lt_person_has_skill'
        )
        
        person_skill_map = {}
        for ps in person_skills:
            skill_id = ps['object'].data.get('skill_id')
            proficiency = ps['link_data'].get('proficiency_level', 1)
            years = ps['link_data'].get('years_experience', 0)
            person_skill_map[skill_id] = {
                'proficiency': proficiency,
                'years': years
            }
        
        matching = []
        missing = []
        below = []
        development = []
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for req in skill_requirements:
            skill_id = req['skill_id']
            required_level = req['min_proficiency']
            weight = req['weight']
            
            person_skill = person_skill_map.get(skill_id)
            
            if person_skill:
                person_level = person_skill['proficiency']
                
                if person_level >= required_level:
                    # Full match
                    matching.append({
                        'skill_id': skill_id,
                        'skill_name': req['skill_name'],
                        'required_level': required_level,
                        'person_level': person_level,
                        'years_experience': person_skill['years']
                    })
                    skill_score = 1.0
                else:
                    # Below required but has skill
                    skill_score = (person_level / required_level) * 0.5
                    below.append({
                        'skill_id': skill_id,
                        'skill_name': req['skill_name'],
                        'required_level': required_level,
                        'person_level': person_level,
                        'gap': required_level - person_level,
                        'development_potential': True
                    })
                    development.append({
                        'skill_name': req['skill_name'],
                        'current_level': person_level,
                        'target_level': required_level
                    })
            else:
                # Missing skill entirely
                missing.append({
                    'skill_id': skill_id,
                    'skill_name': req['skill_name'],
                    'required_level': required_level,
                    'mandatory': req['is_mandatory']
                })
                skill_score = 0.0
            
            total_weight += weight
            weighted_score += skill_score * weight
        
        # Calculate final match score
        if total_weight > 0:
            match_score = (weighted_score / total_weight) * 100
        else:
            match_score = 100.0
        
        # Check availability
        availability = self._calculate_availability(session, person.id)
        
        # Determine recommendation
        if match_score >= self.EXCELLENT_MATCH:
            recommendation = "Excellent match - ideal candidate for this task"
        elif match_score >= self.GOOD_MATCH:
            recommendation = "Good match - can handle this task effectively"
        elif match_score >= self.ACCEPTABLE_MATCH:
            if development:
                recommendation = "Acceptable match with development opportunities"
            else:
                recommendation = "Acceptable match - may need support"
        else:
            recommendation = "Poor match - consider alternative resources or training"
        
        return SkillMatchResult(
            person_id=person.id,
            person_name=person.data.get('name', 'Unknown'),
            match_score=round(match_score, 2),
            is_full_match=len(missing) == 0 and len(below) == 0,
            matching_skills=matching,
            missing_skills=missing,
            below_required=below,
            development_opportunities=development,
            availability_percent=availability,
            recommendation=recommendation
        )
    
    def _get_available_people(
        self,
        session: Session,
        limit: int
    ) -> List[SkillMatchResult]:
        """Get available people when no specific skill requirements."""
        people = self.get_objects_by_type(session, 'ot_person', status='active')
        
        results = []
        for person in people[:limit]:
            availability = self._calculate_availability(session, person.id)
            results.append(SkillMatchResult(
                person_id=person.id,
                person_name=person.data.get('name', 'Unknown'),
                match_score=50.0,  # Neutral
                is_full_match=True,
                matching_skills=[],
                missing_skills=[],
                below_required=[],
                development_opportunities=[],
                availability_percent=availability,
                recommendation="Available resource"
            ))
        
        return results
    
    def _get_all_skill_requirements(
        self,
        session: Session
    ) -> List[Dict[str, Any]]:
        """Get all skill requirements across all tasks."""
        # Get all skill requirement objects
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_task_skill_requirement',
                ObjectModel.status != 'deleted'
            )
        )
        requirements = session.scalars(stmt).all()
        
        result = []
        for req in requirements:
            result.append({
                'skill_id': req.data.get('skill_id'),
                'task_id': req.data.get('task_id'),
                'min_proficiency': req.data.get('minimum_proficiency', 1),
                'is_mandatory': req.data.get('is_mandatory', True)
            })
        
        return result
    
    def _count_qualified_people(
        self,
        session: Session,
        skill_id: str,
        min_proficiency: int
    ) -> int:
        """Count people qualified for a skill at given proficiency."""
        # Get all person-skill links for this skill
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_person_skill',
                ObjectModel.data['skill_id'].astext == skill_id,
                ObjectModel.status != 'deleted'
            )
        )
        person_skills = session.scalars(stmt).all()
        
        count = 0
        for ps in person_skills:
            if ps.data.get('proficiency_level', 0) >= min_proficiency:
                # Check if person is active
                person_id = ps.data.get('person_id')
                person = self.get_object_by_id(session, person_id)
                if person and person.data.get('status') == 'active':
                    count += 1
        
        return count
    
    def _calculate_availability(
        self,
        session: Session,
        person_id: str
    ) -> float:
        """Calculate current availability percentage for a person."""
        # Get current assignments
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['person_id'].astext == person_id,
                ObjectModel.status == 'active'
            )
        )
        assignments = session.scalars(stmt).all()
        
        total_allocation = sum(
            a.data.get('allocation_percent', 0)
            for a in assignments
        )
        
        return max(0.0, 100.0 - total_allocation)
    
    def _find_related_skills(
        self,
        session: Session,
        skill_id: str
    ) -> List[Dict[str, str]]:
        """Find skills related to a given skill."""
        # Get skills linked via lt_skill_related_to
        related = self.get_linked_objects(
            session, skill_id, link_type_id='lt_skill_related_to'
        )
        
        return [
            {
                'skill_id': r['object'].id,
                'name': r['object'].data.get('name', 'Unknown'),
                'relationship_strength': r['link_data'].get('relationship_strength', 0.5)
            }
            for r in related
        ]
    
    def _suggest_training(self, skill: ObjectModel) -> List[str]:
        """Generate training suggestions for a skill."""
        category = skill.data.get('category', 'unknown')
        
        suggestions = [
            f"Formal training in {skill.data.get('name')}",
            f"Online courses for {skill.data.get('name')}",
            f"Practice projects using {skill.data.get('name')}"
        ]
        
        if category == 'technical':
            suggestions.extend([
                "Coding exercises and challenges",
                "Pair programming with experienced developers"
            ])
        elif category == 'design':
            suggestions.extend([
                "Design workshops",
                "Portfolio building projects"
            ])
        elif category == 'management':
            suggestions.extend([
                "Leadership training",
                "Project management certification"
            ])
        
        return suggestions
