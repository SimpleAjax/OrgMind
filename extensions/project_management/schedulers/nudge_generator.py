"""
Nudge Generator Scheduler

AI-powered proactive notification system that generates nudges for:
- Delay risks (tasks likely to miss deadlines)
- Resource conflicts (overallocations)
- Skill gaps (unassignable tasks)
- Burnout risks (overallocated people)
- Opportunities (underutilized resources)
- Dependency bottlenecks

Usage:
    generator = NudgeGenerator(db_adapter, neo4j_adapter)
    
    # Generate all nudges
    nudges = await generator.generate_nudges()
    
    # Generate specific type
    risks = await generator.detect_delay_risks()
"""

import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy import select, and_, or_, func

from .base import SchedulerBase, ObjectModel, LinkModel, Session

logger = logging.getLogger(__name__)


class NudgeType(str, Enum):
    """Types of nudges."""
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    CONFLICT = "conflict"
    SUGGESTION = "suggestion"


class NudgeSeverity(str, Enum):
    """Severity levels for nudges."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class NudgeCandidate:
    """Candidate nudge before persistence."""
    type: NudgeType
    severity: NudgeSeverity
    title: str
    description: str
    recipient_id: str
    related_project_id: Optional[str] = None
    related_person_id: Optional[str] = None
    related_task_id: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)


class NudgeGenerator(SchedulerBase):
    """
    AI-powered nudge generation system.
    
    Generates proactive notifications for project managers about:
    - Tasks at risk of delay
    - Resource conflicts and overallocations
    - Skill gaps
    - Burnout risks
    - Optimization opportunities
    
    Nudges are ranked by importance and deduplicated to prevent spam.
    """
    
    # Thresholds for various nudge types
    DELAY_RISK_THRESHOLD = 0.7  # 70% probability
    OVERALLOCATION_THRESHOLD = 100  # Percentage
    BURNOUT_WEEKS_THRESHOLD = 4
    BURNOUT_ALLOCATION_THRESHOLD = 90
    UNDERUTILIZED_THRESHOLD = 50  # Less than 50% allocated
    HIGH_PRIORITY_THRESHOLD = 70  # Priority score
    
    # Deduplication window (hours)
    DEDUP_WINDOW_HOURS = 24
    
    def __init__(self, db_adapter=None, neo4j_adapter=None):
        super().__init__(db_adapter, neo4j_adapter)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def run(
        self,
        max_nudges: int = 50,
        severity_threshold: str = "info"
    ) -> Dict[str, Any]:
        """
        Main entry point - generate all nudges.
        
        Args:
            max_nudges: Maximum number of nudges to generate
            severity_threshold: Minimum severity level to include
            
        Returns:
            Summary of generated nudges
        """
        return await self.generate_nudges(max_nudges, severity_threshold)
    
    async def generate_nudges(
        self,
        max_nudges: int = 50,
        severity_threshold: str = "info"
    ) -> Dict[str, Any]:
        """
        Generate all types of nudges and persist to database.
        
        Args:
            max_nudges: Maximum number of nudges to generate
            severity_threshold: Minimum severity level
            
        Returns:
            Summary of generation results
        """
        self.logger.info(f"Starting nudge generation (max={max_nudges})")
        
        all_candidates = []
        
        # Detect various types of nudges
        all_candidates.extend(await self.detect_delay_risks())
        all_candidates.extend(await self.detect_resource_conflicts())
        all_candidates.extend(await self.detect_skill_gaps())
        all_candidates.extend(await self.detect_burnout_risks())
        all_candidates.extend(await self.detect_opportunities())
        all_candidates.extend(await self.detect_dependency_bottlenecks())
        
        # Rank nudges by importance
        ranked = self.rank_nudges(all_candidates)
        
        # Filter by severity threshold
        severity_order = ["info", "warning", "critical"]
        min_index = severity_order.index(severity_threshold)
        filtered = [
            n for n in ranked
            if severity_order.index(n.severity.value) >= min_index
        ]
        
        # Deduplicate
        deduplicated = self._deduplicate_nudges(filtered)
        
        # Limit to max
        final_candidates = deduplicated[:max_nudges]
        
        # Persist to database
        created_count = 0
        skipped_count = 0
        
        with self.get_session() as session:
            for candidate in final_candidates:
                try:
                    if self._should_create_nudge(session, candidate):
                        self._create_nudge_object(session, candidate)
                        created_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.logger.error(f"Error creating nudge: {e}")
            
            session.commit()
        
        self.logger.info(
            f"Nudge generation complete: {created_count} created, "
            f"{skipped_count} skipped (duplicates)"
        )
        
        return {
            'candidates_found': len(all_candidates),
            'after_ranking': len(ranked),
            'after_deduplication': len(deduplicated),
            'created': created_count,
            'skipped_duplicates': skipped_count,
            'by_type': self._count_by_type(final_candidates),
            'by_severity': self._count_by_severity(final_candidates)
        }
    
    async def detect_delay_risks(self) -> List[NudgeCandidate]:
        """
        Detect tasks at risk of missing deadlines.
        
        Returns:
            List of delay risk nudge candidates
        """
        candidates = []
        
        with self.get_session() as session:
            # Find tasks with high delay probability
            tasks = self.get_objects_by_type(session, 'ot_task', limit=1000)
            
            for task in tasks:
                delay_prob = task.data.get('predicted_delay_probability', 0)
                status = task.data.get('status', '')
                
                # Only consider active tasks with high delay probability
                if delay_prob >= self.DELAY_RISK_THRESHOLD and status in ['todo', 'in_progress']:
                    # Determine severity based on probability
                    if delay_prob >= 0.9:
                        severity = NudgeSeverity.CRITICAL
                    elif delay_prob >= 0.8:
                        severity = NudgeSeverity.WARNING
                    else:
                        severity = NudgeSeverity.INFO
                    
                    # Get project info
                    project_id = task.data.get('project_id')
                    project = self.get_object_by_id(session, project_id) if project_id else None
                    
                    # Get assignee info
                    assignees = self._get_task_assignees(session, task.id)
                    
                    # Build nudge
                    candidate = NudgeCandidate(
                        type=NudgeType.RISK,
                        severity=severity,
                        title=f"Task at risk of delay: {task.data.get('title', 'Unknown')[:50]}",
                        description=(
                            f"Task '{task.data.get('title')}' has a "
                            f"{delay_prob*100:.0f}% probability of missing its deadline. "
                            f"Due date: {task.data.get('due_date', 'Not set')}. "
                            f"Consider reallocating resources or reducing scope."
                        ),
                        recipient_id=project.data.get('pm_id') if project else assignees[0]['id'] if assignees else None,
                        related_project_id=project_id,
                        related_task_id=task.id,
                        related_person_id=assignees[0]['id'] if assignees else None,
                        context_data={
                            'delay_probability': delay_prob,
                            'due_date': task.data.get('due_date'),
                            'estimated_hours': task.data.get('estimated_hours'),
                            'actual_hours': task.data.get('actual_hours', 0)
                        },
                        confidence=delay_prob,
                        suggested_actions=[
                            {'type': 'reassign', 'description': 'Reassign to different resource'},
                            {'type': 'extend', 'description': 'Extend deadline'},
                            {'type': 'split', 'description': 'Split into smaller tasks'}
                        ]
                    )
                    
                    if candidate.recipient_id:
                        candidates.append(candidate)
        
        self.logger.info(f"Detected {len(candidates)} delay risks")
        return candidates
    
    async def detect_resource_conflicts(self) -> List[NudgeCandidate]:
        """
        Detect resource conflicts and overallocations.
        
        Returns:
            List of conflict nudge candidates
        """
        candidates = []
        
        with self.get_session() as session:
            # Get all active people
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            for person in people:
                person_id = person.id
                
                # Calculate allocation per day (simplified)
                # In production, this would be a proper time-series calculation
                assignments = self._get_person_assignments_with_overlap(session, person_id)
                
                # Check for overallocations
                for date_range, total_allocation in assignments.items():
                    if total_allocation > self.OVERALLOCATION_THRESHOLD:
                        excess = total_allocation - 100
                        
                        if excess > 50:
                            severity = NudgeSeverity.CRITICAL
                        elif excess > 20:
                            severity = NudgeSeverity.WARNING
                        else:
                            severity = NudgeSeverity.INFO
                        
                        candidate = NudgeCandidate(
                            type=NudgeType.CONFLICT,
                            severity=severity,
                            title=f"Resource conflict: {person.data.get('name')} overallocated",
                            description=(
                                f"{person.data.get('name')} is allocated at "
                                f"{total_allocation:.0f}% during {date_range}. "
                                f"This exceeds capacity by {excess:.0f}%."
                            ),
                            recipient_id=person.data.get('manager_id') or person_id,
                            related_person_id=person_id,
                            context_data={
                                'allocation_percent': total_allocation,
                                'excess_percent': excess,
                                'date_range': date_range
                            },
                            confidence=min(total_allocation / 150, 1.0),
                            suggested_actions=[
                                {'type': 'rebalance', 'description': 'Redistribute workload'},
                                {'type': 'delegate', 'description': 'Delegate to other team member'},
                                {'type': 'extend', 'description': 'Extend timeline'}
                            ]
                        )
                        
                        candidates.append(candidate)
        
        self.logger.info(f"Detected {len(candidates)} resource conflicts")
        return candidates
    
    async def detect_skill_gaps(self) -> List[NudgeCandidate]:
        """
        Detect tasks with no qualified assignees.
        
        Returns:
            List of skill gap nudge candidates
        """
        candidates = []
        
        with self.get_session() as session:
            # Find unassigned tasks with skill requirements
            tasks = self.get_objects_by_type(session, 'ot_task', limit=500)
            
            for task in tasks:
                # Check if task has skill requirements
                skill_reqs = self.get_linked_objects(
                    session, task.id, link_type_id='lt_task_requires_skill'
                )
                
                if not skill_reqs:
                    continue
                
                # Check if task is unassigned
                assignments = self.get_linked_objects(
                    session, task.id, link_type_id='lt_task_assigned_to'
                )
                
                if assignments:
                    continue  # Already assigned
                
                # Check for qualified people
                qualified_people = self._find_qualified_people(session, skill_reqs)
                
                if not qualified_people:
                    # No one has the required skills
                    skill_names = [
                        self.get_object_by_id(
                            session, req['object'].data.get('skill_id')
                        ).data.get('name', 'Unknown') if self.get_object_by_id(
                            session, req['object'].data.get('skill_id')
                        ) else 'Unknown'
                        for req in skill_reqs
                    ]
                    
                    project_id = task.data.get('project_id')
                    project = self.get_object_by_id(session, project_id) if project_id else None
                    
                    candidate = NudgeCandidate(
                        type=NudgeType.SUGGESTION,
                        severity=NudgeSeverity.WARNING,
                        title=f"Skill gap: No qualified resource for '{task.data.get('title', 'Unknown')[:40]}'",
                        description=(
                            f"Task '{task.data.get('title')}' requires skills "
                            f"that no available team member possesses: "
                            f"{', '.join(skill_names)}. Consider training or hiring."
                        ),
                        recipient_id=project.data.get('pm_id') if project else None,
                        related_project_id=project_id,
                        related_task_id=task.id,
                        context_data={
                            'required_skills': skill_names,
                            'task_priority': task.data.get('priority')
                        },
                        confidence=0.9,
                        suggested_actions=[
                            {'type': 'train', 'description': 'Arrange skill training'},
                            {'type': 'outsource', 'description': 'Consider outsourcing'},
                            {'type': 'hire', 'description': 'Hire for required skills'}
                        ]
                    )
                    
                    if candidate.recipient_id:
                        candidates.append(candidate)
        
        self.logger.info(f"Detected {len(candidates)} skill gaps")
        return candidates
    
    async def detect_burnout_risks(self) -> List[NudgeCandidate]:
        """
        Detect people at risk of burnout from overallocation.
        
        Returns:
            List of burnout risk nudge candidates
        """
        candidates = []
        
        with self.get_session() as session:
            # Check for people with high allocation for extended periods
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            for person in people:
                # Check allocation over last 4 weeks
                avg_allocation = self._calculate_average_allocation(
                    session, person.id, weeks=4
                )
                
                if avg_allocation >= self.BURNOUT_ALLOCATION_THRESHOLD:
                    if avg_allocation >= 100:
                        severity = NudgeSeverity.CRITICAL
                    elif avg_allocation >= 95:
                        severity = NudgeSeverity.WARNING
                    else:
                        severity = NudgeSeverity.INFO
                    
                    candidate = NudgeCandidate(
                        type=NudgeType.RISK,
                        severity=severity,
                        title=f"Burnout risk: {person.data.get('name')} overallocated for 4+ weeks",
                        description=(
                            f"{person.data.get('name')} has been at "
                            f"{avg_allocation:.0f}% average allocation for the past "
                            f"{self.BURNOUT_WEEKS_THRESHOLD} weeks. "
                            f"Consider redistributing workload to prevent burnout."
                        ),
                        recipient_id=person.data.get('manager_id') or person.id,
                        related_person_id=person.id,
                        context_data={
                            'average_allocation': avg_allocation,
                            'weeks': self.BURNOUT_WEEKS_THRESHOLD
                        },
                        confidence=min(avg_allocation / 100, 1.0),
                        suggested_actions=[
                            {'type': 'rebalance', 'description': 'Redistribute current assignments'},
                            {'type': 'timeoff', 'description': 'Schedule time off'},
                            {'type': 'delegate', 'description': 'Delegate some tasks'}
                        ]
                    )
                    
                    candidates.append(candidate)
        
        self.logger.info(f"Detected {len(candidates)} burnout risks")
        return candidates
    
    async def detect_opportunities(self) -> List[NudgeCandidate]:
        """
        Detect optimization opportunities (underutilized resources, etc.).
        
        Returns:
            List of opportunity nudge candidates
        """
        candidates = []
        
        with self.get_session() as session:
            # Find people with capacity for high-priority tasks
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            for person in people:
                current_allocation = self._calculate_current_allocation(session, person.id)
                
                if current_allocation < self.UNDERUTILIZED_THRESHOLD:
                    available_capacity = 100 - current_allocation
                    
                    # Find high-priority tasks that could use this person
                    available_tasks = self._find_available_high_priority_tasks(session)
                    
                    if available_tasks:
                        candidate = NudgeCandidate(
                            type=NudgeType.OPPORTUNITY,
                            severity=NudgeSeverity.INFO,
                            title=f"Opportunity: {person.data.get('name')} has {available_capacity:.0f}% capacity",
                            description=(
                                f"{person.data.get('name')} is currently at "
                                f"{current_allocation:.0f}% allocation and could take on "
                                f"additional work. {len(available_tasks)} high-priority "
                                f"tasks are available for assignment."
                            ),
                            recipient_id=person.data.get('manager_id') or person.id,
                            related_person_id=person.id,
                            context_data={
                                'available_capacity': available_capacity,
                                'suggested_tasks': [t.id for t in available_tasks[:5]]
                            },
                            confidence=0.7,
                            suggested_actions=[
                                {
                                    'type': 'assign',
                                    'description': f'Assign one of {len(available_tasks)} available tasks'
                                }
                            ]
                        )
                        
                        candidates.append(candidate)
        
        self.logger.info(f"Detected {len(candidates)} opportunities")
        return candidates
    
    async def detect_dependency_bottlenecks(self) -> List[NudgeCandidate]:
        """
        Detect tasks that are blocking many other tasks.
        
        Returns:
            List of bottleneck nudge candidates
        """
        candidates = []
        
        if not self.neo4j:
            self.logger.warning("Neo4j not available, skipping bottleneck detection")
            return candidates
        
        try:
            # Query for tasks blocking many others
            query = """
            MATCH (t:Object {type_id: 'ot_task'})-[r:lt_task_blocks]->(blocked:Object)
            WHERE t.data.status IN ['todo', 'in_progress'] 
              AND blocked.data.status != 'done'
            RETURN t.id as task_id, t.data as task_data,
                   count(blocked) as blocked_count
            HAVING count(blocked) >= 3
            """
            
            results = self.neo4j.execute_read(query)
            
            with self.get_session() as session:
                for result in results:
                    blocked_count = result.get('blocked_count', 0)
                    task_id = result.get('task_id')
                    task_data = result.get('task_data', {})
                    
                    if blocked_count >= 5:
                        severity = NudgeSeverity.CRITICAL
                    elif blocked_count >= 3:
                        severity = NudgeSeverity.WARNING
                    else:
                        continue
                    
                    project_id = task_data.get('project_id')
                    project = self.get_object_by_id(session, project_id) if project_id else None
                    
                    candidate = NudgeCandidate(
                        type=NudgeType.RISK,
                        severity=severity,
                        title=f"Bottleneck: Task blocking {blocked_count} other tasks",
                        description=(
                            f"Task '{task_data.get('title')}' is a critical dependency "
                            f"for {blocked_count} other tasks. Any delay will cascade. "
                            f"Consider prioritizing this task or adding resources."
                        ),
                        recipient_id=project.data.get('pm_id') if project else None,
                        related_project_id=project_id,
                        related_task_id=task_id,
                        context_data={
                            'blocked_count': blocked_count,
                            'task_status': task_data.get('status')
                        },
                        confidence=min(blocked_count / 10, 1.0),
                        suggested_actions=[
                            {'type': 'prioritize', 'description': 'Prioritize this task'},
                            {'type': 'add_resource', 'description': 'Add additional resources'},
                            {'type': 'parallelize', 'description': 'Look for parallelization opportunities'}
                        ]
                    )
                    
                    if candidate.recipient_id:
                        candidates.append(candidate)
        
        except Exception as e:
            self.logger.error(f"Error detecting bottlenecks: {e}")
        
        self.logger.info(f"Detected {len(candidates)} bottlenecks")
        return candidates
    
    def rank_nudges(self, nudges: List[NudgeCandidate]) -> List[NudgeCandidate]:
        """
        Rank nudges by importance using AI scoring.
        
        Uses a weighted combination of:
        - Confidence score (higher = more certain)
        - Severity (critical > warning > info)
        - Entity priority (high-priority projects/tasks)
        - Recency (newer issues)
        
        Args:
            nudges: List of nudge candidates
            
        Returns:
            Sorted list (highest importance first)
        """
        def calculate_importance(nudge: NudgeCandidate) -> float:
            # Base score from confidence
            score = nudge.confidence * 50
            
            # Severity multiplier
            severity_multipliers = {
                NudgeSeverity.CRITICAL: 2.0,
                NudgeSeverity.WARNING: 1.5,
                NudgeSeverity.INFO: 1.0
            }
            score *= severity_multipliers.get(nudge.severity, 1.0)
            
            # Type weighting (risks and conflicts are more urgent)
            type_weights = {
                NudgeType.RISK: 1.3,
                NudgeType.CONFLICT: 1.2,
                NudgeType.SUGGESTION: 1.0,
                NudgeType.OPPORTUNITY: 0.9
            }
            score *= type_weights.get(nudge.type, 1.0)
            
            # Boost for critical project tasks
            if nudge.context_data.get('task_priority') == 'critical':
                score *= 1.5
            
            return score
        
        return sorted(nudges, key=calculate_importance, reverse=True)
    
    def _deduplicate_nudges(
        self,
        nudges: List[NudgeCandidate]
    ) -> List[NudgeCandidate]:
        """
        Remove duplicate or similar nudges.
        
        Uses a combination of:
        - Same recipient + same related entity
        - Similar titles (fuzzy matching)
        - Within time window
        """
        deduplicated = []
        seen_keys = set()
        
        for nudge in nudges:
            # Create a deduplication key
            key_parts = [
                nudge.recipient_id,
                nudge.type.value,
                nudge.related_task_id or nudge.related_person_id or '',
                nudge.title[:30]  # First 30 chars of title
            ]
            key = '|'.join(str(p) for p in key_parts)
            
            if key not in seen_keys:
                seen_keys.add(key)
                deduplicated.append(nudge)
        
        return deduplicated
    
    def _should_create_nudge(
        self,
        session: Session,
        candidate: NudgeCandidate
    ) -> bool:
        """
        Check if a similar nudge already exists (prevent spam).
        """
        # Look for similar recent nudges
        cutoff_time = self.now() - timedelta(hours=self.DEDUP_WINDOW_HOURS)
        
        existing = session.scalars(
            select(ObjectModel).where(
                and_(
                    ObjectModel.type_id == 'ot_nudge',
                    ObjectModel.data['recipient_id'].astext == candidate.recipient_id,
                    ObjectModel.data['related_task_id'].astext == (candidate.related_task_id or ''),
                    ObjectModel.data['type'].astext == candidate.type.value,
                    ObjectModel.created_at >= cutoff_time
                )
            )
        ).first()
        
        return existing is None
    
    def _create_nudge_object(
        self,
        session: Session,
        candidate: NudgeCandidate
    ) -> ObjectModel:
        """Create the nudge object in the database."""
        nudge_data = {
            'type': candidate.type.value,
            'severity': candidate.severity.value,
            'title': candidate.title,
            'description': candidate.description,
            'recipient_id': candidate.recipient_id,
            'related_project_id': candidate.related_project_id,
            'related_person_id': candidate.related_person_id,
            'related_task_id': candidate.related_task_id,
            'context_data': candidate.context_data,
            'ai_confidence': candidate.confidence,
            'status': 'new',
            'created_at': self.now().isoformat()
        }
        
        nudge = ObjectModel(
            id=str(uuid.uuid4()),
            type_id='ot_nudge',
            data=nudge_data,
            status='active'
        )
        
        session.add(nudge)
        
        # Create suggested actions
        for action in candidate.suggested_actions:
            action_data = {
                'nudge_id': nudge.id,
                'action_type': action.get('type', 'custom'),
                'description': action.get('description', ''),
                'is_automatable': action.get('type') in ['reassign', 'extend'],
                'was_executed': False
            }
            
            action_obj = ObjectModel(
                id=str(uuid.uuid4()),
                type_id='ot_nudge_action',
                data=action_data,
                status='active'
            )
            session.add(action_obj)
            
            # Create link between nudge and action
            # (In production, use proper link creation)
        
        return nudge
    
    def _get_task_assignees(
        self,
        session: Session,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """Get people assigned to a task."""
        assignments = self.get_linked_objects(
            session, task_id, link_type_id='lt_task_assigned_to'
        )
        
        assignees = []
        for assignment in assignments:
            # Get person from assignment
            person_links = self.get_linked_objects(
                session, assignment['object'].id,
                link_type_id='lt_assignment_to_person'
            )
            for link in person_links:
                assignees.append({
                    'id': link['object'].id,
                    'name': link['object'].data.get('name')
                })
        
        return assignees
    
    def _get_person_assignments_with_overlap(
        self,
        session: Session,
        person_id: str
    ) -> Dict[str, float]:
        """Get assignments with their date ranges and allocations."""
        # Simplified - returns mock data for now
        # In production, would calculate actual daily allocations
        return {}
    
    def _find_qualified_people(
        self,
        session: Session,
        skill_reqs: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Find people qualified for given skill requirements."""
        qualified = []
        
        # Get all active people
        people = self.get_objects_by_type(session, 'ot_person', status='active')
        
        for person in people:
            # Get person's skills
            person_skills = self.get_linked_objects(
                session, person.id, link_type_id='lt_person_has_skill'
            )
            
            person_skill_map = {
                s['object'].data.get('skill_id'): s['link_data'].get('proficiency_level', 1)
                for s in person_skills
            }
            
            is_qualified = True
            for req in skill_reqs:
                req_skill_id = req['object'].data.get('skill_id')
                req_level = req['object'].data.get('minimum_proficiency', 1)
                
                person_level = person_skill_map.get(req_skill_id, 0)
                if person_level < req_level:
                    is_qualified = False
                    break
            
            if is_qualified:
                qualified.append({
                    'person_id': person.id,
                    'person_name': person.data.get('name')
                })
        
        return qualified
    
    def _calculate_average_allocation(
        self,
        session: Session,
        person_id: str,
        weeks: int
    ) -> float:
        """Calculate average allocation over past weeks."""
        # Simplified - would calculate from actual assignment data
        assignments = self._get_person_assignments(session, person_id)
        
        if not assignments:
            return 0.0
        
        total = sum(a.data.get('allocation_percent', 0) for a in assignments)
        return total / len(assignments) if assignments else 0.0
    
    def _calculate_current_allocation(
        self,
        session: Session,
        person_id: str
    ) -> float:
        """Calculate current allocation percentage."""
        return self._calculate_average_allocation(session, person_id, weeks=1)
    
    def _find_available_high_priority_tasks(
        self,
        session: Session
    ) -> List[ObjectModel]:
        """Find high-priority tasks that are unassigned."""
        tasks = self.get_objects_by_type(session, 'ot_task', status='todo')
        
        available = []
        for task in tasks:
            priority_score = task.data.get('priority_score', 0)
            if priority_score >= self.HIGH_PRIORITY_THRESHOLD:
                # Check if unassigned
                assignments = self.get_linked_objects(
                    session, task.id, link_type_id='lt_task_assigned_to'
                )
                if not assignments:
                    available.append(task)
        
        return available
    
    def _get_person_assignments(
        self,
        session: Session,
        person_id: str
    ) -> List[ObjectModel]:
        """Get all assignments for a person."""
        stmt = select(LinkModel).where(
            and_(
                LinkModel.type_id == 'lt_assignment_to_person',
                LinkModel.target_id == person_id
            )
        )
        links = session.scalars(stmt).all()
        
        assignments = []
        for link in links:
            assignment = self.get_object_by_id(session, link.source_id)
            if assignment and assignment.status != 'deleted':
                assignments.append(assignment)
        
        return assignments
    
    def _count_by_type(self, nudges: List[NudgeCandidate]) -> Dict[str, int]:
        """Count nudges by type."""
        counts = {}
        for nudge in nudges:
            counts[nudge.type.value] = counts.get(nudge.type.value, 0) + 1
        return counts
    
    def _count_by_severity(self, nudges: List[NudgeCandidate]) -> Dict[str, int]:
        """Count nudges by severity."""
        counts = {}
        for nudge in nudges:
            counts[nudge.severity.value] = counts.get(nudge.severity.value, 0) + 1
        return counts
