"""
Velocity Calculator Scheduler

Tracks individual productivity and estimation accuracy across project types.

Metrics Tracked:
- Velocity factor (actual vs estimated hours)
- Estimation accuracy ratio
- Completion rate by project type
- Trend analysis over time

Usage:
    calculator = VelocityCalculator(db_adapter)
    
    # Update all productivity profiles
    await calculator.update_productivity_profiles()
    
    # Get person's velocity
    velocity = await calculator.calculate_person_velocity(person_id, project_type)
    
    # Update on task completion
    await calculator.update_task_velocity(task_id)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, stdev
import uuid

from sqlalchemy import select, and_, func

from .base import SchedulerBase, ObjectModel, Session

logger = logging.getLogger(__name__)


@dataclass
class VelocityMetrics:
    """Velocity metrics for a person."""
    person_id: str
    person_name: str
    project_type: str
    
    # Core metrics
    velocity_factor: float  # 1.0 = average, >1 = faster, <1 = slower
    estimation_accuracy: float  # 1.0 = perfect estimates
    
    # Sample statistics
    tasks_completed: int
    total_estimated_hours: float
    total_actual_hours: float
    
    # Trend
    avg_completion_time_days: float
    on_time_delivery_rate: float  # percentage
    
    # Quality indicators
    rework_rate: float  # percentage of tasks with rework
    
    # Confidence
    confidence_level: str  # 'high', 'medium', 'low' based on sample size
    last_updated: str


@dataclass
class TaskVelocityRecord:
    """Velocity record for a single completed task."""
    task_id: str
    task_title: str
    project_id: str
    project_type: str
    
    estimated_hours: float
    actual_hours: float
    variance_ratio: float  # actual / estimated
    
    started_at: Optional[datetime]
    completed_at: datetime
    completion_days: float
    
    assignee_id: str


class VelocityCalculator(SchedulerBase):
    """
    Calculates productivity velocity and estimation accuracy.
    
    Tracks metrics per person per project type to enable
    accurate future predictions and workload planning.
    """
    
    # Minimum sample sizes for confidence levels
    MIN_HIGH_CONFIDENCE = 10
    MIN_MEDIUM_CONFIDENCE = 5
    
    # Outlier thresholds (standard deviations)
    OUTLIER_STD_DEV = 2.5
    
    # Smoothing factor for velocity updates (exponential moving average)
    VELOCITY_SMOOTHING = 0.3  # 30% new data, 70% historical
    
    def __init__(self, db_adapter=None, neo4j_adapter=None):
        super().__init__(db_adapter, neo4j_adapter)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def run(
        self,
        min_sample_size: int = 5
    ) -> Dict[str, Any]:
        """
        Run velocity calculation for all people.
        
        Args:
            min_sample_size: Minimum completed tasks to include person
            
        Returns:
            Summary of updates
        """
        return await self.update_productivity_profiles(min_sample_size)
    
    async def update_productivity_profiles(
        self,
        min_sample_size: int = 5
    ) -> Dict[str, Any]:
        """
        Update productivity profiles for all people.
        
        Args:
            min_sample_size: Minimum completed tasks to include
            
        Returns:
            Summary of updates
        """
        self.logger.info(f"Updating productivity profiles (min_sample={min_sample_size})")
        
        with self.get_session() as session:
            # Get all active people
            people = self.get_objects_by_type(session, 'ot_person', status='active')
            
            updated_count = 0
            skipped_count = 0
            errors = []
            
            for person in people:
                try:
                    # Get completed tasks for this person
                    completed_tasks = self._get_completed_tasks(session, person.id)
                    
                    if len(completed_tasks) < min_sample_size:
                        skipped_count += 1
                        continue
                    
                    # Group by project type
                    by_project_type = self._group_tasks_by_project_type(
                        session, completed_tasks
                    )
                    
                    for project_type, tasks in by_project_type.items():
                        metrics = self._calculate_velocity_metrics(
                            person, project_type, tasks
                        )
                        
                        self._update_productivity_profile(session, metrics)
                    
                    updated_count += 1
                    
                except Exception as e:
                    self.logger.error(
                        f"Error updating profile for {person.id}: {e}"
                    )
                    errors.append({'person_id': person.id, 'error': str(e)})
            
            session.commit()
            
            self.logger.info(
                f"Profile update complete: {updated_count} updated, "
                f"{skipped_count} skipped (insufficient data)"
            )
            
            return {
                'updated': updated_count,
                'skipped': skipped_count,
                'errors': errors
            }
    
    async def calculate_person_velocity(
        self,
        person_id: str,
        project_type: Optional[str] = None
    ) -> Optional[VelocityMetrics]:
        """
        Calculate velocity metrics for a specific person.
        
        Args:
            person_id: Person to calculate for
            project_type: Optional filter by project type
            
        Returns:
            VelocityMetrics or None if insufficient data
        """
        with self.get_session() as session:
            person = self.get_object_by_id(session, person_id)
            if not person:
                raise ValueError(f"Person {person_id} not found")
            
            completed_tasks = self._get_completed_tasks(session, person_id)
            
            if not completed_tasks:
                return None
            
            # Filter by project type if specified
            if project_type:
                filtered_tasks = []
                for task in completed_tasks:
                    task_project_type = self._get_task_project_type(
                        session, task.task_id
                    )
                    if task_project_type == project_type:
                        filtered_tasks.append(task)
                completed_tasks = filtered_tasks
            
            if not completed_tasks:
                return None
            
            # Use the most common project type if not specified
            if not project_type:
                project_types = [t.project_type for t in completed_tasks]
                project_type = max(set(project_types), key=project_types.count)
            
            return self._calculate_velocity_metrics(
                person, project_type, completed_tasks
            )
    
    async def update_task_velocity(self, task_id: str) -> Optional[VelocityMetrics]:
        """
        Update velocity tracking when a task is completed.
        
        Args:
            task_id: Completed task ID
            
        Returns:
            Updated velocity metrics for the assignee
        """
        with self.get_session() as session:
            task = self.get_object_by_id(session, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            if task.data.get('status') != 'done':
                self.logger.warning(f"Task {task_id} is not marked as done")
                return None
            
            # Get assignees
            assignees = self._get_task_assignees(session, task_id)
            
            if not assignees:
                self.logger.warning(f"Task {task_id} has no assignees")
                return None
            
            # Update velocity for each assignee
            for assignee_id in assignees:
                # Get all completed tasks for this person
                completed_tasks = self._get_completed_tasks(session, assignee_id)
                
                if len(completed_tasks) >= self.MIN_MEDIUM_CONFIDENCE:
                    # Get project type
                    project_type = self._get_task_project_type(session, task_id)
                    
                    # Filter tasks by project type
                    type_tasks = [
                        t for t in completed_tasks
                        if t.project_type == project_type
                    ]
                    
                    if len(type_tasks) >= self.MIN_MEDIUM_CONFIDENCE:
                        person = self.get_object_by_id(session, assignee_id)
                        metrics = self._calculate_velocity_metrics(
                            person, project_type, type_tasks
                        )
                        self._update_productivity_profile(session, metrics)
            
            session.commit()
            
            # Return metrics for first assignee
            return await self.calculate_person_velocity(assignees[0])
    
    async def get_velocity_trends(
        self,
        person_id: str,
        project_type: Optional[str] = None,
        weeks: int = 12
    ) -> Dict[str, Any]:
        """
        Get historical velocity trends for a person.
        
        Args:
            person_id: Person to analyze
            project_type: Optional filter
            weeks: Number of weeks to analyze
            
        Returns:
            Trend data
        """
        with self.get_session() as session:
            person = self.get_object_by_id(session, person_id)
            if not person:
                raise ValueError(f"Person {person_id} not found")
            
            # Get completed tasks within timeframe
            cutoff_date = self.now() - timedelta(weeks=weeks)
            
            completed_tasks = self._get_completed_tasks(
                session, person_id, since=cutoff_date
            )
            
            if not completed_tasks:
                return {
                    'person_id': person_id,
                    'weeks_analyzed': weeks,
                    'tasks_count': 0,
                    'trend': 'insufficient_data'
                }
            
            # Filter by project type
            if project_type:
                completed_tasks = [
                    t for t in completed_tasks
                    if t.project_type == project_type
                ]
            
            # Group by week
            weekly_data = {}
            for task in completed_tasks:
                week_key = task.completed_at.strftime('%Y-W%U')
                if week_key not in weekly_data:
                    weekly_data[week_key] = {
                        'tasks': 0,
                        'estimated_hours': 0,
                        'actual_hours': 0
                    }
                weekly_data[week_key]['tasks'] += 1
                weekly_data[week_key]['estimated_hours'] += task.estimated_hours
                weekly_data[week_key]['actual_hours'] += task.actual_hours
            
            # Calculate weekly velocity factors
            weekly_velocity = []
            for week, data in sorted(weekly_data.items()):
                if data['actual_hours'] > 0:
                    velocity = data['estimated_hours'] / data['actual_hours']
                    weekly_velocity.append({
                        'week': week,
                        'velocity_factor': round(velocity, 2),
                        'tasks': data['tasks']
                    })
            
            # Determine trend
            if len(weekly_velocity) >= 3:
                recent = mean([w['velocity_factor'] for w in weekly_velocity[-3:]])
                older = mean([w['velocity_factor'] for w in weekly_velocity[:3]])
                
                if recent > older * 1.1:
                    trend = 'improving'
                elif recent < older * 0.9:
                    trend = 'declining'
                else:
                    trend = 'stable'
            else:
                trend = 'insufficient_data'
            
            return {
                'person_id': person_id,
                'person_name': person.data.get('name'),
                'project_type': project_type or 'all',
                'weeks_analyzed': weeks,
                'tasks_count': len(completed_tasks),
                'weekly_velocity': weekly_velocity,
                'trend': trend,
                'current_velocity': weekly_velocity[-1]['velocity_factor'] if weekly_velocity else None
            }
    
    def _get_completed_tasks(
        self,
        session: Session,
        person_id: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[TaskVelocityRecord]:
        """Get completed tasks for a person."""
        # Get assignments for this person
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_assignment',
                ObjectModel.data['person_id'].astext == person_id,
                ObjectModel.status == 'active'
            )
        )
        assignments = session.scalars(stmt).all()
        
        completed_tasks = []
        
        for assignment in assignments:
            task_id = assignment.data.get('task_id')
            if not task_id:
                continue
            
            task = self.get_object_by_id(session, task_id)
            if not task or task.data.get('status') != 'done':
                continue
            
            # Check date filter
            completed_at = task.data.get('actual_end')
            if not completed_at:
                completed_at = assignment.data.get('actual_end')
            
            if completed_at:
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                
                if since and completed_at < since:
                    continue
            else:
                continue
            
            # Get project info
            project_id = task.data.get('project_id')
            project_type = self._get_task_project_type(session, task_id)
            
            # Calculate completion time
            started_at = assignment.data.get('actual_start')
            if started_at and isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            
            completion_days = 0
            if started_at:
                completion_days = (completed_at - started_at).days
            
            estimated = task.data.get('estimated_hours', 0)
            actual = assignment.data.get('actual_hours', estimated)
            
            record = TaskVelocityRecord(
                task_id=task_id,
                task_title=task.data.get('title', 'Unknown'),
                project_id=project_id,
                project_type=project_type,
                estimated_hours=estimated,
                actual_hours=actual,
                variance_ratio=actual / estimated if estimated > 0 else 1.0,
                started_at=started_at,
                completed_at=completed_at,
                completion_days=completion_days,
                assignee_id=person_id
            )
            
            completed_tasks.append(record)
        
        # Sort by completion date (newest first)
        completed_tasks.sort(key=lambda x: x.completed_at, reverse=True)
        
        return completed_tasks[:limit]
    
    def _group_tasks_by_project_type(
        self,
        session: Session,
        tasks: List[TaskVelocityRecord]
    ) -> Dict[str, List[TaskVelocityRecord]]:
        """Group tasks by project type."""
        grouped = {}
        for task in tasks:
            pt = task.project_type or 'unknown'
            if pt not in grouped:
                grouped[pt] = []
            grouped[pt].append(task)
        return grouped
    
    def _calculate_velocity_metrics(
        self,
        person: ObjectModel,
        project_type: str,
        tasks: List[TaskVelocityRecord]
    ) -> VelocityMetrics:
        """Calculate velocity metrics from completed tasks."""
        if not tasks:
            raise ValueError("No tasks provided for velocity calculation")
        
        # Remove outliers
        variance_ratios = [t.variance_ratio for t in tasks]
        filtered_tasks = self._remove_outliers(tasks, variance_ratios)
        
        if not filtered_tasks:
            filtered_tasks = tasks  # Use all if filtering removes everything
        
        # Calculate core metrics
        total_estimated = sum(t.estimated_hours for t in filtered_tasks)
        total_actual = sum(t.actual_hours for t in filtered_tasks)
        
        # Velocity factor: how much work they complete vs estimate
        # > 1 means faster than estimated, < 1 means slower
        velocity_factor = total_estimated / total_actual if total_actual > 0 else 1.0
        
        # Estimation accuracy: how close estimates were to actual
        # 1.0 = perfect, > 1 = underestimated, < 1 = overestimated
        estimation_accuracy = total_actual / total_estimated if total_estimated > 0 else 1.0
        
        # Average completion time
        completion_times = [
            t.completion_days for t in filtered_tasks
            if t.completion_days > 0
        ]
        avg_completion_time = mean(completion_times) if completion_times else 0
        
        # On-time delivery rate
        on_time_count = sum(
            1 for t in filtered_tasks
            if t.actual_hours <= t.estimated_hours * 1.1  # Within 10% is on time
        )
        on_time_rate = (on_time_count / len(filtered_tasks)) * 100 if filtered_tasks else 0
        
        # Rework rate (simplified - would track from task history)
        rework_rate = 0.0
        
        # Confidence level based on sample size
        if len(filtered_tasks) >= self.MIN_HIGH_CONFIDENCE:
            confidence = 'high'
        elif len(filtered_tasks) >= self.MIN_MEDIUM_CONFIDENCE:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return VelocityMetrics(
            person_id=person.id,
            person_name=person.data.get('name', 'Unknown'),
            project_type=project_type,
            velocity_factor=round(velocity_factor, 2),
            estimation_accuracy=round(estimation_accuracy, 2),
            tasks_completed=len(filtered_tasks),
            total_estimated_hours=round(total_estimated, 2),
            total_actual_hours=round(total_actual, 2),
            avg_completion_time_days=round(avg_completion_time, 2),
            on_time_delivery_rate=round(on_time_rate, 2),
            rework_rate=round(rework_rate, 2),
            confidence_level=confidence,
            last_updated=self.now().isoformat()
        )
    
    def _remove_outliers(
        self,
        tasks: List[TaskVelocityRecord],
        values: List[float]
    ) -> List[TaskVelocityRecord]:
        """Remove statistical outliers from task list."""
        if len(values) < 5:
            return tasks
        
        try:
            avg = mean(values)
            std = stdev(values)
            
            threshold = self.OUTLIER_STD_DEV * std
            
            filtered = [
                task for task, value in zip(tasks, values)
                if abs(value - avg) <= threshold
            ]
            
            return filtered if len(filtered) >= self.MIN_MEDIUM_CONFIDENCE else tasks
            
        except Exception:
            return tasks
    
    def _update_productivity_profile(
        self,
        session: Session,
        metrics: VelocityMetrics
    ):
        """Update or create productivity profile in database."""
        # Check if profile exists
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == 'ot_productivity_profile',
                ObjectModel.data['person_id'].astext == metrics.person_id,
                ObjectModel.data['project_type'].astext == metrics.project_type
            )
        )
        existing = session.scalars(stmt).first()
        
        if existing:
            # Update existing profile with smoothing
            old_velocity = existing.data.get('velocity_factor', 1.0)
            new_velocity = (
                self.VELOCITY_SMOOTHING * metrics.velocity_factor +
                (1 - self.VELOCITY_SMOOTHING) * old_velocity
            )
            
            old_accuracy = existing.data.get('estimation_accuracy', 1.0)
            new_accuracy = (
                self.VELOCITY_SMOOTHING * metrics.estimation_accuracy +
                (1 - self.VELOCITY_SMOOTHING) * old_accuracy
            )
            
            existing.data = {
                **existing.data,
                'velocity_factor': round(new_velocity, 2),
                'estimation_accuracy': round(new_accuracy, 2),
                'tasks_completed_count': metrics.tasks_completed,
                'avg_task_completion_hours': metrics.avg_completion_time_days * 8,
                'last_updated': metrics.last_updated
            }
            existing.version += 1
        else:
            # Create new profile
            profile = ObjectModel(
                id=str(uuid.uuid4()),
                type_id='ot_productivity_profile',
                data={
                    'person_id': metrics.person_id,
                    'project_type': metrics.project_type,
                    'velocity_factor': metrics.velocity_factor,
                    'estimation_accuracy': metrics.estimation_accuracy,
                    'tasks_completed_count': metrics.tasks_completed,
                    'avg_task_completion_hours': metrics.avg_completion_time_days * 8,
                    'last_updated': metrics.last_updated
                },
                status='active'
            )
            session.add(profile)
    
    def _get_task_project_type(
        self,
        session: Session,
        task_id: str
    ) -> str:
        """Get project type for a task."""
        task = self.get_object_by_id(session, task_id)
        if not task:
            return 'unknown'
        
        project_id = task.data.get('project_id')
        if not project_id:
            return 'unknown'
        
        project = self.get_object_by_id(session, project_id)
        if not project:
            return 'unknown'
        
        return project.data.get('type', 'time_material')
    
    def _get_task_assignees(
        self,
        session: Session,
        task_id: str
    ) -> List[str]:
        """Get person IDs assigned to a task."""
        assignments = self.get_linked_objects(
            session, task_id, link_type_id='lt_task_assigned_to'
        )
        
        assignees = []
        for assignment in assignments:
            person_links = self.get_linked_objects(
                session, assignment['object'].id,
                link_type_id='lt_assignment_to_person'
            )
            for link in person_links:
                assignees.append(link['object'].id)
        
        return assignees
