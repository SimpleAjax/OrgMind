"""
Conflict Detector Scheduler

Continuous monitoring for resource conflicts and scheduling issues.

Conflict Types:
- Overallocation (> 100% on any day)
- Double-booking (same person, overlapping tasks)
- Skill mismatch (assigned person lacks required skills)
- Sprint overcommitment (> 85% capacity)

Usage:
    detector = ConflictDetector(db_adapter)
    
    # Detect all conflicts
    conflicts = await detector.detect_conflicts()
    
    # Check specific assignment
    conflicts = await detector.check_assignment_conflicts(assignment_id)
    
    # Validate sprint capacity
    issues = await detector.validate_sprint_capacity(sprint_id)
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from sqlalchemy import select, and_, or_

from .base import SchedulerBase, ObjectModel, Session

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of conflicts."""
    OVERALLOCATION = "overallocation"
    DOUBLE_BOOKING = "double_booking"
    SKILL_MISMATCH = "skill_mismatch"
    SPRINT_OVERCOMMITMENT = "sprint_overcommitment"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    SCHEDULING_CONFLICT = "scheduling_conflict"


class ConflictSeverity(str, Enum):
    """Severity levels for conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Conflict:
    """Represents a detected conflict."""
    conflict_type: ConflictType
    severity: ConflictSeverity
    
    # Affected entities
    person_id: Optional[str]
    person_name: Optional[str]
    task_id: Optional[str]
    task_title: Optional[str]
    sprint_id: Optional[str]
    sprint_name: Optional[str]
    
    # Details
    description: str
    date_range: Optional[Dict[str, str]] = None
    allocation_percentage: Optional[float] = None
    
    # Suggested resolution
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ConflictSummary:
    """Summary of conflict detection run."""
    total_conflicts: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    critical_issues: List[Conflict]
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ConflictDetector(SchedulerBase):
    """
    Detects resource conflicts and scheduling issues.
    
    Runs continuously to identify:
    - People allocated > 100%
    - Overlapping task assignments
    - Skill mismatches
    - Sprint overcommitments
    """
    
    # Thresholds
    OVERALLOCATION_THRESHOLD = 100.0
    SPRINT_OVERCOMMITMENT_THRESHOLD = 85.0
    WARNING_ALLOCATION = 90.0
    
    def __init__(self, db_adapter=None, neo4j_adapter=None):
        super().__init__(db_adapter, neo4j_adapter)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def run(self) -> ConflictSummary:
        """
        Run full conflict detection.
        
        Returns:
            ConflictSummary with all detected issues
        """
        return await self.detect_conflicts()
    
    async def detect_conflicts(
        self,
        date_range: Optional[Dict[str, str]] = None
    ) -> ConflictSummary:
        """
        Detect all types of conflicts.
        
        Args:
            date_range: Optional date range to check {'start': '...', 'end': '...'}
            
        Returns:
            ConflictSummary with all detected conflicts
        """
        self.logger.info("Running conflict detection")
        
        all_conflicts = []
        
        # Detect various conflict types
        all_conflicts.extend(await self.detect_overallocations(date_range))
        all_conflicts.extend(await self.detect_double_bookings(date_range))
        all_conflicts.extend(await self.detect_skill_mismatches())
        all_conflicts.extend(await self.detect_sprint_overcommitments())
        all_conflicts.extend(await self.detect_scheduling_conflicts(date_range))
        
        # Categorize
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        critical_issues = []
        
        for conflict in all_conflicts:
            by_type[conflict.conflict_type.value] += 1
            by_severity[conflict.severity.value] += 1
            
            if conflict.severity == ConflictSeverity.CRITICAL:
                critical_issues.append(conflict)
        
        self.logger.info(
            f"Conflict detection complete: {len(all_conflicts)} conflicts found, "
            f"{len(critical_issues)} critical"
        )
        
        return ConflictSummary(
            total_conflicts=len(all_conflicts),
            by_type=dict(by_type),
            by_severity=dict(by_severity),
            critical_issues=critical_issues
        )
    
    async def detect_overallocations(
        self,
        date_range: Optional[Dict[str, str]] = None
    ) -> List[Conflict]:
        """
        Detect people with allocation > 100%.
        
        Args:
            date_range: Optional date range to check
            
        Returns:
            List of overallocation conflicts
        """
        conflicts = []
        
        with self.get_session() as session:
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            for person in people:
                # Get all active assignments
                assignments = self._get_person_assignments(session, person.id)
                
                if not assignments:
                    continue
                
                # Calculate daily allocations
                daily_allocations = self._calculate_daily_allocations(
                    session, assignments, date_range
                )
                
                for date_str, allocation in daily_allocations.items():
                    if allocation > self.OVERALLOCATION_THRESHOLD:
                        excess = allocation - 100
                        
                        if allocation > 120:
                            severity = ConflictSeverity.CRITICAL
                        elif allocation > 110:
                            severity = ConflictSeverity.HIGH
                        elif allocation > 105:
                            severity = ConflictSeverity.MEDIUM
                        else:
                            severity = ConflictSeverity.LOW
                        
                        conflicts.append(Conflict(
                            conflict_type=ConflictType.OVERALLOCATION,
                            severity=severity,
                            person_id=person.id,
                            person_name=person.data.get('name'),
                            task_id=None,
                            task_title=None,
                            sprint_id=None,
                            sprint_name=None,
                            description=(
                                f"{person.data.get('name')} is overallocated at "
                                f"{allocation:.0f}% on {date_str} "
                                f"({excess:.0f}% over capacity)"
                            ),
                            date_range={'start': date_str, 'end': date_str},
                            allocation_percentage=allocation,
                            suggested_actions=[
                                {
                                    'type': 'reduce_allocation',
                                    'description': f'Reduce allocation by {excess:.0f}%'
                                },
                                {
                                    'type': 'extend_timeline',
                                    'description': 'Extend task timelines to spread work'
                                },
                                {
                                    'type': 'reassign',
                                    'description': 'Reassign some tasks to other team members'
                                }
                            ]
                        ))
                    elif allocation > self.WARNING_ALLOCATION:
                        # Warning level
                        conflicts.append(Conflict(
                            conflict_type=ConflictType.OVERALLOCATION,
                            severity=ConflictSeverity.LOW,
                            person_id=person.id,
                            person_name=person.data.get('name'),
                            task_id=None,
                            task_title=None,
                            sprint_id=None,
                            sprint_name=None,
                            description=(
                                f"{person.data.get('name')} is at {allocation:.0f}% allocation "
                                f"on {date_str} - approaching capacity limit"
                            ),
                            date_range={'start': date_str, 'end': date_str},
                            allocation_percentage=allocation,
                            suggested_actions=[
                                {
                                    'type': 'monitor',
                                    'description': 'Monitor workload - avoid additional assignments'
                                }
                            ]
                        ))
        
        self.logger.info(f"Detected {len(conflicts)} overallocations")
        return conflicts
    
    async def detect_double_bookings(
        self,
        date_range: Optional[Dict[str, str]] = None
    ) -> List[Conflict]:
        """
        Detect overlapping task assignments for same person.
        
        Args:
            date_range: Optional date range to check
            
        Returns:
            List of double-booking conflicts
        """
        conflicts = []
        
        with self.get_session() as session:
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            for person in people:
                assignments = self._get_person_assignments(session, person.id)
                
                # Check each pair of assignments for overlap
                for i, assign1 in enumerate(assignments):
                    for assign2 in assignments[i+1:]:
                        overlap = self._get_assignment_overlap(assign1, assign2)
                        
                        if overlap:
                            task1 = self.get_object_by_id(
                                session, assign1.data.get('task_id')
                            )
                            task2 = self.get_object_by_id(
                                session, assign2.data.get('task_id')
                            )
                            
                            total_allocation = (
                                assign1.data.get('allocation_percent', 0) +
                                assign2.data.get('allocation_percent', 0)
                            )
                            
                            if total_allocation > 100:
                                conflicts.append(Conflict(
                                    conflict_type=ConflictType.DOUBLE_BOOKING,
                                    severity=ConflictSeverity.HIGH,
                                    person_id=person.id,
                                    person_name=person.data.get('name'),
                                    task_id=assign1.data.get('task_id'),
                                    task_title=task1.data.get('title') if task1 else 'Unknown',
                                    sprint_id=None,
                                    sprint_name=None,
                                    description=(
                                        f"{person.data.get('name')} has overlapping assignments: "
                                        f"'{task1.data.get('title') if task1 else 'Unknown'}' and "
                                        f"'{task2.data.get('title') if task2 else 'Unknown'}' "
                                        f"({overlap['start']} to {overlap['end']})"
                                    ),
                                    date_range=overlap,
                                    allocation_percentage=total_allocation,
                                    suggested_actions=[
                                        {
                                            'type': 'stagger',
                                            'description': 'Stagger task start dates'
                                        },
                                        {
                                            'type': 'reassign_one',
                                            'description': 'Reassign one task to another person'
                                        }
                                    ]
                                ))
        
        self.logger.info(f"Detected {len(conflicts)} double bookings")
        return conflicts
    
    async def detect_skill_mismatches(self) -> List[Conflict]:
        """
        Detect tasks where assigned person lacks required skills.
        
        Returns:
            List of skill mismatch conflicts
        """
        conflicts = []
        
        with self.get_session() as session:
            # Get all active assignments
            stmt = select(ObjectModel).where(
                and_(
                    ObjectModel.type_id == 'ot_assignment',
                    ObjectModel.status == 'active'
                )
            )
            assignments = session.scalars(stmt).all()
            
            for assignment in assignments:
                task_id = assignment.data.get('task_id')
                person_id = assignment.data.get('person_id')
                
                if not task_id or not person_id:
                    continue
                
                task = self.get_object_by_id(session, task_id)
                person = self.get_object_by_id(session, person_id)
                
                if not task or not person:
                    continue
                
                # Get skill requirements
                skill_reqs = self.get_linked_objects(
                    session, task_id, link_type_id='lt_task_requires_skill'
                )
                
                if not skill_reqs:
                    continue
                
                # Get person's skills
                person_skills = self.get_linked_objects(
                    session, person_id, link_type_id='lt_person_has_skill'
                )
                
                person_skill_map = {
                    ps['object'].data.get('skill_id'): ps['link_data'].get('proficiency_level', 0)
                    for ps in person_skills
                }
                
                # Check each requirement
                missing_mandatory = []
                below_required = []
                
                for req in skill_reqs:
                    req_obj = req['object']
                    skill_id = req_obj.data.get('skill_id')
                    required_level = req_obj.data.get('minimum_proficiency', 1)
                    is_mandatory = req_obj.data.get('is_mandatory', True)
                    
                    person_level = person_skill_map.get(skill_id, 0)
                    
                    skill = self.get_object_by_id(session, skill_id)
                    skill_name = skill.data.get('name', 'Unknown') if skill else 'Unknown'
                    
                    if person_level < required_level:
                        if is_mandatory:
                            missing_mandatory.append({
                                'skill_id': skill_id,
                                'skill_name': skill_name,
                                'required': required_level,
                                'actual': person_level
                            })
                        else:
                            below_required.append({
                                'skill_id': skill_id,
                                'skill_name': skill_name,
                                'required': required_level,
                                'actual': person_level
                            })
                
                # Report conflicts
                if missing_mandatory:
                    conflicts.append(Conflict(
                        conflict_type=ConflictType.SKILL_MISMATCH,
                        severity=ConflictSeverity.HIGH,
                        person_id=person_id,
                        person_name=person.data.get('name'),
                        task_id=task_id,
                        task_title=task.data.get('title'),
                        sprint_id=None,
                        sprint_name=None,
                        description=(
                            f"{person.data.get('name')} lacks mandatory skills for "
                            f"'{task.data.get('title')}': "
                            f"{', '.join(s['skill_name'] for s in missing_mandatory)}"
                        ),
                        suggested_actions=[
                            {
                                'type': 'reassign',
                                'description': 'Reassign to person with required skills'
                            },
                            {
                                'type': 'pair',
                                'description': 'Pair with mentor who has required skills'
                            },
                            {
                                'type': 'train',
                                'description': f"Provide training before task starts"
                            }
                        ]
                    ))
                elif below_required:
                    conflicts.append(Conflict(
                        conflict_type=ConflictType.SKILL_MISMATCH,
                        severity=ConflictSeverity.LOW,
                        person_id=person_id,
                        person_name=person.data.get('name'),
                        task_id=task_id,
                        task_title=task.data.get('title'),
                        sprint_id=None,
                        sprint_name=None,
                        description=(
                            f"{person.data.get('name')} has preferred skills below "
                            f"recommended level for '{task.data.get('title')}': "
                            f"{', '.join(s['skill_name'] for s in below_required)}"
                        ),
                        suggested_actions=[
                            {
                                'type': 'monitor',
                                'description': 'Monitor progress and provide support as needed'
                            }
                        ]
                    ))
        
        self.logger.info(f"Detected {len(conflicts)} skill mismatches")
        return conflicts
    
    async def detect_sprint_overcommitments(self) -> List[Conflict]:
        """
        Detect sprints committed beyond 85% capacity.
        
        Returns:
            List of sprint overcommitment conflicts
        """
        conflicts = []
        
        with self.get_session() as session:
            # Get active sprints
            sprints = self.get_objects_by_type(
                session, 'ot_sprint', status='active'
            )
            
            for sprint in sprints:
                sprint_id = sprint.id
                
                # Calculate committed hours
                sprint_tasks = self._get_sprint_tasks(session, sprint_id)
                committed_hours = sum(
                    t.data.get('estimated_hours', 0) for t in sprint_tasks
                )
                
                # Calculate capacity
                participants = self._get_sprint_participants(session, sprint_id)
                total_capacity = sum(
                    p.get('planned_capacity_hours', 80) for p in participants
                )
                
                if total_capacity > 0:
                    commitment_ratio = (committed_hours / total_capacity) * 100
                    
                    if commitment_ratio > self.SPRINT_OVERCOMMITMENT_THRESHOLD:
                        excess = commitment_ratio - 100 if commitment_ratio > 100 else 0
                        
                        if commitment_ratio > 100:
                            severity = ConflictSeverity.CRITICAL
                        elif commitment_ratio > 95:
                            severity = ConflictSeverity.HIGH
                        elif commitment_ratio > 90:
                            severity = ConflictSeverity.MEDIUM
                        else:
                            severity = ConflictSeverity.LOW
                        
                        conflicts.append(Conflict(
                            conflict_type=ConflictType.SPRINT_OVERCOMMITMENT,
                            severity=severity,
                            person_id=None,
                            person_name=None,
                            task_id=None,
                            task_title=None,
                            sprint_id=sprint_id,
                            sprint_name=sprint.data.get('name', 'Unknown Sprint'),
                            description=(
                                f"Sprint '{sprint.data.get('name')}' is overcommitted at "
                                f"{commitment_ratio:.0f}% capacity "
                                f"({committed_hours:.0f}h / {total_capacity:.0f}h). "
                                f"{'Exceeds capacity by ' + f'{excess:.0f}%' if excess else ''}"
                            ),
                            allocation_percentage=commitment_ratio,
                            suggested_actions=[
                                {
                                    'type': 'remove_tasks',
                                    'description': f'Remove {len(sprint_tasks) // 5} lowest priority tasks'
                                },
                                {
                                    'type': 'reduce_scope',
                                    'description': 'Reduce scope of large tasks'
                                },
                                {
                                    'type': 'add_capacity',
                                    'description': 'Add team member to sprint'
                                }
                            ]
                        ))
        
        self.logger.info(f"Detected {len(conflicts)} sprint overcommitments")
        return conflicts
    
    async def detect_scheduling_conflicts(
        self,
        date_range: Optional[Dict[str, str]] = None
    ) -> List[Conflict]:
        """
        Detect general scheduling conflicts (dependencies, deadlines).
        
        Args:
            date_range: Optional date range
            
        Returns:
            List of scheduling conflicts
        """
        conflicts = []
        
        with self.get_session() as session:
            # Find tasks with impossible deadlines
            tasks = self.get_objects_by_type(session, 'ot_task', limit=500)
            
            now = self.now()
            
            for task in tasks:
                due_date = task.data.get('due_date')
                earliest_start = task.data.get('earliest_start')
                
                if due_date and earliest_start:
                    if isinstance(due_date, str):
                        due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    if isinstance(earliest_start, str):
                        earliest_start = datetime.fromisoformat(earliest_start.replace('Z', '+00:00'))
                    
                    # Check if there's enough time between earliest start and due date
                    estimated_hours = task.data.get('estimated_hours', 8)
                    estimated_days = estimated_hours / 8  # 8 hours per day
                    
                    available_days = (due_date - max(earliest_start, now)).days
                    
                    if available_days < estimated_days * 0.5:  # Less than half the time needed
                        conflicts.append(Conflict(
                            conflict_type=ConflictType.SCHEDULING_CONFLICT,
                            severity=ConflictSeverity.HIGH,
                            person_id=None,
                            person_name=None,
                            task_id=task.id,
                            task_title=task.data.get('title'),
                            sprint_id=None,
                            sprint_name=None,
                            description=(
                                f"Task '{task.data.get('title')}' has insufficient time: "
                                f"{available_days} days available but {estimated_days:.1f} days needed"
                            ),
                            date_range={'start': earliest_start.isoformat(), 'end': due_date.isoformat()},
                            suggested_actions=[
                                {
                                    'type': 'extend_deadline',
                                    'description': 'Extend task deadline'
                                },
                                {
                                    'type': 'add_resources',
                                    'description': 'Add parallel resources to task'
                                },
                                {
                                    'type': 'reduce_scope',
                                    'description': 'Reduce task scope'
                                }
                            ]
                        ))
        
        self.logger.info(f"Detected {len(conflicts)} scheduling conflicts")
        return conflicts
    
    async def check_assignment_conflicts(
        self,
        assignment_id: str
    ) -> List[Conflict]:
        """
        Check conflicts for a specific assignment.
        
        Args:
            assignment_id: Assignment to check
            
        Returns:
            List of conflicts for this assignment
        """
        with self.get_session() as session:
            assignment = self.get_object_by_id(session, assignment_id)
            if not assignment:
                raise ValueError(f"Assignment {assignment_id} not found")
            
            person_id = assignment.data.get('person_id')
            task_id = assignment.data.get('task_id')
            
            if not person_id or not task_id:
                return []
            
            conflicts = []
            
            # Check overallocation
            person = self.get_object_by_id(session, person_id)
            if person:
                assignments = self._get_person_assignments(session, person_id)
                daily_allocs = self._calculate_daily_allocations(session, assignments)
                
                for date_str, alloc in daily_allocs.items():
                    if alloc > self.OVERALLOCATION_THRESHOLD:
                        conflicts.append(Conflict(
                            conflict_type=ConflictType.OVERALLOCATION,
                            severity=ConflictSeverity.HIGH,
                            person_id=person_id,
                            person_name=person.data.get('name'),
                            task_id=task_id,
                            task_title=None,
                            sprint_id=None,
                            sprint_name=None,
                            description=f"Overallocation detected for {person.data.get('name')}",
                            date_range={'start': date_str, 'end': date_str},
                            allocation_percentage=alloc
                        ))
            
            # Check skill mismatch
            task = self.get_object_by_id(session, task_id)
            if task:
                skill_reqs = self.get_linked_objects(
                    session, task_id, link_type_id='lt_task_requires_skill'
                )
                
                if skill_reqs:
                    person_skills = self.get_linked_objects(
                        session, person_id, link_type_id='lt_person_has_skill'
                    )
                    
                    person_skill_map = {
                        ps['object'].data.get('skill_id'): ps['link_data'].get('proficiency_level', 0)
                        for ps in person_skills
                    }
                    
                    for req in skill_reqs:
                        req_obj = req['object']
                        skill_id = req_obj.data.get('skill_id')
                        required_level = req_obj.data.get('minimum_proficiency', 1)
                        
                        person_level = person_skill_map.get(skill_id, 0)
                        
                        if person_level < required_level:
                            conflicts.append(Conflict(
                                conflict_type=ConflictType.SKILL_MISMATCH,
                                severity=ConflictSeverity.MEDIUM,
                                person_id=person_id,
                                person_name=person.data.get('name') if person else None,
                                task_id=task_id,
                                task_title=task.data.get('title') if task else None,
                                sprint_id=None,
                                sprint_name=None,
                                description=f"Skill mismatch for assignment"
                            ))
            
            return conflicts
    
    async def validate_sprint_capacity(self, sprint_id: str) -> Dict[str, Any]:
        """
        Validate sprint capacity and return detailed report.
        
        Args:
            sprint_id: Sprint to validate
            
        Returns:
            Validation report
        """
        with self.get_session() as session:
            sprint = self.get_object_by_id(session, sprint_id)
            if not sprint:
                raise ValueError(f"Sprint {sprint_id} not found")
            
            # Get participants and their allocations
            participants = self._get_sprint_participants(session, sprint_id)
            sprint_tasks = self._get_sprint_tasks(session, sprint_id)
            
            total_capacity = sum(p.get('planned_capacity_hours', 80) for p in participants)
            committed_hours = sum(t.data.get('estimated_hours', 0) for t in sprint_tasks)
            
            # Check each person's load
            person_loads = []
            for participant in participants:
                person_hours = self._calculate_person_sprint_hours(
                    session, participant['id'], sprint_tasks
                )
                utilization = (person_hours / participant.get('planned_capacity_hours', 80)) * 100
                
                person_loads.append({
                    'person_id': participant['id'],
                    'person_name': participant['name'],
                    'allocated_hours': person_hours,
                    'capacity_hours': participant.get('planned_capacity_hours', 80),
                    'utilization': round(utilization, 2),
                    'status': 'overallocated' if utilization > 100 else 'ok'
                })
            
            overallocation_count = sum(1 for p in person_loads if p['status'] == 'overallocated')
            
            commitment_ratio = (committed_hours / total_capacity * 100) if total_capacity > 0 else 0
            
            return {
                'sprint_id': sprint_id,
                'sprint_name': sprint.data.get('name'),
                'total_capacity_hours': total_capacity,
                'committed_hours': committed_hours,
                'commitment_ratio': round(commitment_ratio, 2),
                'is_overcommitted': commitment_ratio > self.SPRINT_OVERCOMMITMENT_THRESHOLD,
                'participant_loads': person_loads,
                'overallocation_count': overallocation_count,
                'recommendations': self._generate_capacity_recommendations(
                    commitment_ratio, overallocation_count, person_loads
                )
            }
    
    def _get_person_assignments(
        self,
        session: Session,
        person_id: str
    ) -> List[ObjectModel]:
        """Get all active assignments for a person."""
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['person_id'].astext == person_id,
                ObjectModel.status == 'active'
            )
        )
        return list(session.scalars(stmt).all())
    
    def _calculate_daily_allocations(
        self,
        session: Session,
        assignments: List[ObjectModel],
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Calculate daily allocation percentages."""
        daily_allocations = defaultdict(float)
        
        for assignment in assignments:
            start = assignment.data.get('planned_start')
            end = assignment.data.get('planned_end')
            allocation = assignment.data.get('allocation_percent', 100)
            
            if not start or not end:
                continue
            
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace('Z', '+00:00'))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Filter by date range if specified
            if date_range:
                range_start = datetime.fromisoformat(date_range['start'])
                range_end = datetime.fromisoformat(date_range['end'])
                
                if end < range_start or start > range_end:
                    continue
            
            # Add allocation for each day
            current = start
            while current <= end:
                date_str = current.strftime('%Y-%m-%d')
                daily_allocations[date_str] += allocation
                current += timedelta(days=1)
        
        return dict(daily_allocations)
    
    def _get_assignment_overlap(
        self,
        assign1: ObjectModel,
        assign2: ObjectModel
    ) -> Optional[Dict[str, str]]:
        """Get overlap period between two assignments."""
        start1 = assign1.data.get('planned_start')
        end1 = assign1.data.get('planned_end')
        start2 = assign2.data.get('planned_start')
        end2 = assign2.data.get('planned_end')
        
        if not all([start1, end1, start2, end2]):
            return None
        
        if isinstance(start1, str):
            start1 = datetime.fromisoformat(start1.replace('Z', '+00:00'))
        if isinstance(end1, str):
            end1 = datetime.fromisoformat(end1.replace('Z', '+00:00'))
        if isinstance(start2, str):
            start2 = datetime.fromisoformat(start2.replace('Z', '+00:00'))
        if isinstance(end2, str):
            end2 = datetime.fromisoformat(end2.replace('Z', '+00:00'))
        
        # Check overlap
        if start1 <= end2 and start2 <= end1:
            return {
                'start': max(start1, start2).isoformat(),
                'end': min(end1, end2).isoformat()
            }
        
        return None
    
    def _get_sprint_participants(
        self,
        session: Session,
        sprint_id: str
    ) -> List[Dict[str, Any]]:
        """Get sprint participants."""
        links = self.get_linked_objects(
            session, sprint_id, link_type_id='lt_sprint_has_participant'
        )
        
        participants = []
        for link in links:
            person = link['object']
            participants.append({
                'id': person.id,
                'name': person.data.get('name', 'Unknown'),
                'role': person.data.get('role', 'developer'),
                'planned_capacity_hours': link['link_data'].get('planned_capacity_hours', 80)
            })
        
        return participants
    
    def _get_sprint_tasks(
        self,
        session: Session,
        sprint_id: str
    ) -> List[ObjectModel]:
        """Get tasks in a sprint."""
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_sprint_task',
                ObjectModel.data['sprint_id'].astext == sprint_id,
                ObjectModel.status != 'deleted'
            )
        )
        sprint_task_links = session.scalars(stmt).all()
        
        tasks = []
        for link in sprint_task_links:
            task_id = link.data.get('task_id')
            if task_id:
                task = self.get_object_by_id(session, task_id)
                if task:
                    tasks.append(task)
        
        return tasks
    
    def _calculate_person_sprint_hours(
        self,
        session: Session,
        person_id: str,
        sprint_tasks: List[ObjectModel]
    ) -> float:
        """Calculate hours assigned to a person from sprint tasks."""
        task_ids = {t.id for t in sprint_tasks}
        
        # Get assignments for this person
        assignments = self._get_person_assignments(session, person_id)
        
        total_hours = 0
        for assignment in assignments:
            task_id = assignment.data.get('task_id')
            if task_id in task_ids:
                total_hours += assignment.data.get('planned_hours', 0)
        
        return total_hours
    
    def _generate_capacity_recommendations(
        self,
        commitment_ratio: float,
        overallocation_count: int,
        person_loads: List[Dict]
    ) -> List[str]:
        """Generate recommendations based on capacity analysis."""
        recommendations = []
        
        if commitment_ratio > 100:
            recommendations.append(
                f"Sprint is overcommitted by {commitment_ratio - 100:.0f}%. "
                f"Remove {int((commitment_ratio - 100) / 100 * sum(p['allocated_hours'] for p in person_loads) / 8)} tasks."
            )
        elif commitment_ratio > 85:
            recommendations.append(
                f"Sprint is at {commitment_ratio:.0f}% capacity. "
                "Monitor closely and avoid scope creep."
            )
        elif commitment_ratio < 60:
            recommendations.append(
                f"Sprint is only at {commitment_ratio:.0f}% capacity. "
                "Consider adding more tasks or bringing forward work from future sprints."
            )
        
        if overallocation_count > 0:
            overloaded = [p for p in person_loads if p['status'] == 'overallocated']
            recommendations.append(
                f"{overallocation_count} team members are overallocated: "
                f"{', '.join(p['person_name'] for p in overloaded)}. "
                f"Rebalance workload immediately."
            )
        
        return recommendations
