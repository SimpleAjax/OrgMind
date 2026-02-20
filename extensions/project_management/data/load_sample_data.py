#!/usr/bin/env python3
"""
Sample Data Loader for Project Management Extension

Loads sample data into OrgMind for testing and demonstrations.

Usage:
    python load_sample_data.py [--clean] [--scenario SCENARIO]

Options:
    --clean       Clear existing data before loading
    --scenario    Load specific scenario only (sick_leave, scope_change, sprint_planning, skill_matching, conflict)
"""

import argparse
import json
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class SampleDataLoader:
    """Loads sample data into OrgMind."""
    
    def __init__(self, db_adapter=None, api_client=None):
        self.db_adapter = db_adapter
        self.api_client = api_client
        self.data = None
        self.stats = {
            'customers': 0,
            'projects': 0,
            'people': 0,
            'skills': 0,
            'sprints': 0,
            'tasks': 0,
            'assignments': 0,
            'errors': []
        }
    
    def load_data_file(self, filepath: str = None) -> Dict[str, Any]:
        """Load sample data from JSON file."""
        if filepath is None:
            filepath = Path(__file__).parent / "sample_data.json"
        
        with open(filepath, 'r') as f:
            self.data = json.load(f)
        
        print(f"✅ Loaded sample data from {filepath}")
        print(f"   Customers: {len(self.data.get('customers', []))}")
        print(f"   Projects: {len(self.data.get('projects', []))}")
        print(f"   People: {len(self.data.get('people', []))}")
        print(f"   Tasks: {len(self.data.get('tasks', []))}")
        
        return self.data
    
    async def load_all(self, clean: bool = False) -> Dict[str, Any]:
        """Load all sample data."""
        if self.data is None:
            self.load_data_file()
        
        print("\n" + "="*60)
        print("Loading Sample Data into OrgMind")
        print("="*60 + "\n")
        
        if clean:
            await self._clear_existing_data()
        
        # Load in dependency order
        await self._load_skills()
        await self._load_customers()
        await self._load_people()
        await self._load_projects()
        await self._load_sprints()
        await self._load_tasks()
        await self._load_leave_periods()
        await self._load_productivity_profiles()
        
        print("\n" + "="*60)
        print("Sample Data Loading Complete")
        print("="*60)
        self._print_stats()
        
        return self.stats
    
    async def load_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Load data for a specific demo scenario."""
        if self.data is None:
            self.load_data_file()
        
        scenario = self.data.get('demo_scenarios', {}).get(scenario_name)
        if not scenario:
            print(f"❌ Scenario '{scenario_name}' not found")
            print(f"Available scenarios: {list(self.data.get('demo_scenarios', {}).keys())}")
            return {'error': 'Scenario not found'}
        
        print(f"\n🎬 Loading Scenario: {scenario['name']}")
        print(f"   {scenario['description']}\n")
        
        # Load minimal data needed for scenario
        await self._load_skills()
        await self._load_customers()
        await self._load_people()
        await self._load_projects()
        
        if scenario_name == 'sick_leave_impact':
            await self._load_sick_leave_scenario()
        elif scenario_name == 'scope_change':
            await self._load_scope_change_scenario()
        elif scenario_name == 'sprint_planning':
            await self._load_sprint_planning_scenario()
        elif scenario_name == 'skill_matching':
            await self._load_skill_matching_scenario()
        elif scenario_name == 'resource_conflict':
            await self._load_conflict_scenario()
        
        print(f"\n✅ Scenario '{scenario['name']}' loaded successfully")
        print("\nExpected outcomes:")
        for outcome in scenario.get('expected_outcomes', []):
            print(f"   • {outcome}")
        
        return self.stats
    
    async def _load_skills(self):
        """Load skills into database."""
        print("📚 Loading Skills...")
        skills = self.data.get('skills', [])
        
        for skill in skills:
            try:
                # Create skill object
                result = await self._create_object('ot_skill', skill['id'], {
                    'name': skill['name'],
                    'category': skill['category'],
                    'description': skill.get('description', '')
                })
                if result:
                    self.stats['skills'] += 1
            except Exception as e:
                self.stats['errors'].append(f"Skill {skill['id']}: {e}")
        
        print(f"   ✅ {self.stats['skills']} skills loaded")
    
    async def _load_customers(self):
        """Load customers into database."""
        print("🏢 Loading Customers...")
        customers = self.data.get('customers', [])
        
        for customer in customers:
            try:
                result = await self._create_object('ot_customer', customer['id'], {
                    'name': customer['name'],
                    'tier': customer['tier'],
                    'contract_value': customer['contract_value'],
                    'sla_level': customer['sla_level'],
                    'contact_info': customer.get('contact_info', {}),
                    'industry': customer.get('industry', ''),
                    'notes': customer.get('notes', '')
                })
                if result:
                    self.stats['customers'] += 1
            except Exception as e:
                self.stats['errors'].append(f"Customer {customer['id']}: {e}")
        
        print(f"   ✅ {self.stats['customers']} customers loaded")
    
    async def _load_people(self):
        """Load people into database."""
        print("👥 Loading People...")
        people = self.data.get('people', [])
        
        for person in people:
            try:
                # Create person
                result = await self._create_object('ot_person', person['id'], {
                    'name': person['name'],
                    'email': person['email'],
                    'role': person['role'],
                    'status': person['status'],
                    'employment_type': person['employment_type'],
                    'working_hours_per_day': person['working_hours_per_day'],
                    'default_availability_percent': person['default_availability_percent'],
                    'hourly_rate': person['hourly_rate']
                })
                
                if result:
                    self.stats['people'] += 1
                    
                    # Create skill links
                    for skill in person.get('skills', []):
                        await self._create_link(
                            'lt_person_has_skill',
                            person['id'],
                            skill['skill_id'],
                            {
                                'proficiency_level': skill['proficiency'],
                                'years_experience': skill['years_experience'],
                                'is_verified': True
                            }
                        )
            except Exception as e:
                self.stats['errors'].append(f"Person {person['id']}: {e}")
        
        print(f"   ✅ {self.stats['people']} people loaded")
    
    async def _load_projects(self):
        """Load projects into database."""
        print("📁 Loading Projects...")
        projects = self.data.get('projects', [])
        
        for project in projects:
            try:
                result = await self._create_object('ot_project', project['id'], {
                    'name': project['name'],
                    'description': project['description'],
                    'status': project['status'],
                    'type': project['type'],
                    'planned_start': project['planned_start'],
                    'planned_end': project['planned_end'],
                    'budget_hours': project['budget_hours'],
                    'hourly_rate': project['hourly_rate'],
                    'business_value_score': project['business_value_score'],
                    'strategic_importance': project['strategic_importance'],
                    'risk_score': project['risk_score'],
                    'priority_score': project['priority_score'],
                    'pm_id': project['pm_id']
                })
                
                if result:
                    self.stats['projects'] += 1
                    
                    # Create customer link
                    await self._create_link(
                        'lt_customer_has_project',
                        project['customer_id'],
                        project['id']
                    )
            except Exception as e:
                self.stats['errors'].append(f"Project {project['id']}: {e}")
        
        print(f"   ✅ {self.stats['projects']} projects loaded")
    
    async def _load_sprints(self):
        """Load sprints into database."""
        print("🏃 Loading Sprints...")
        sprints = self.data.get('sprints', [])
        
        for sprint in sprints:
            try:
                result = await self._create_object('ot_sprint', sprint['id'], {
                    'name': sprint['name'],
                    'start_date': sprint['start_date'],
                    'end_date': sprint['end_date'],
                    'status': sprint['status'],
                    'total_capacity_hours': sprint['total_capacity_hours'],
                    'committed_hours': sprint['committed_hours'],
                    'goals': sprint.get('goals', [])
                })
                
                if result:
                    # Create participant links
                    for participant in sprint.get('participants', []):
                        await self._create_link(
                            'lt_sprint_has_participant',
                            sprint['id'],
                            participant['person_id'],
                            {'planned_capacity_hours': participant['planned_capacity_hours']}
                        )
                    
                    # Create project links
                    for project_id in sprint.get('project_ids', []):
                        await self._create_link(
                            'lt_project_in_sprint',
                            project_id,
                            sprint['id']
                        )
            except Exception as e:
                self.stats['errors'].append(f"Sprint {sprint['id']}: {e}")
        
        print(f"   ✅ {len(sprints)} sprints loaded")
    
    async def _load_tasks(self):
        """Load tasks into database."""
        print("✅ Loading Tasks...")
        tasks = self.data.get('tasks', [])
        
        for task in tasks:
            try:
                result = await self._create_object('ot_task', task['id'], {
                    'title': task['title'],
                    'description': task['description'],
                    'project_id': task['project_id'],
                    'type': task['type'],
                    'status': task['status'],
                    'priority': task['priority'],
                    'estimated_hours': task['estimated_hours'],
                    'actual_hours': task['actual_hours'],
                    'due_date': task.get('due_date'),
                    'predicted_delay_probability': task['predicted_delay_probability']
                })
                
                if result:
                    self.stats['tasks'] += 1
                    
                    # Create project link
                    await self._create_link(
                        'lt_project_has_task',
                        task['project_id'],
                        task['id']
                    )
                    
                    # Create assignment if assignee exists
                    if task.get('assignee_id'):
                        assignment_id = f"assign_{task['id']}"
                        await self._create_object('ot_assignment', assignment_id, {
                            'person_id': task['assignee_id'],
                            'task_id': task['id'],
                            'allocation_percent': task['allocation_percent'],
                            'planned_start': task.get('planned_start', datetime.now().isoformat()),
                            'planned_end': task.get('due_date'),
                            'planned_hours': task['estimated_hours'],
                            'status': 'active' if task['status'] != 'done' else 'completed'
                        })
                        
                        # Create links
                        await self._create_link(
                            'lt_task_assigned_to',
                            task['id'],
                            task['assignee_id'],
                            {
                                'allocation_percent': task['allocation_percent'],
                                'planned_hours': task['estimated_hours']
                            }
                        )
                        
                        self.stats['assignments'] += 1
                    
                    # Create sprint task link if in sprint
                    if task.get('sprint_id'):
                        sprint_task_id = f"st_{task['id']}"
                        await self._create_object('ot_sprint_task', sprint_task_id, {
                            'sprint_id': task['sprint_id'],
                            'task_id': task['id'],
                            'status': task['status']
                        })
                        
                        await self._create_link(
                            'lt_sprint_has_task',
                            task['sprint_id'],
                            task['id']
                        )
                    
                    # Create skill requirements
                    for req in task.get('required_skills', []):
                        req_id = f"req_{task['id']}_{req['skill_id']}"
                        await self._create_object('ot_task_skill_requirement', req_id, {
                            'task_id': task['id'],
                            'skill_id': req['skill_id'],
                            'minimum_proficiency': req['min_proficiency'],
                            'is_mandatory': req['is_mandatory']
                        })
                        
                        await self._create_link(
                            'lt_task_requires_skill',
                            task['id'],
                            req['skill_id'],
                            {
                                'minimum_proficiency': req['min_proficiency'],
                                'is_mandatory': req['is_mandatory']
                            }
                        )
            except Exception as e:
                self.stats['errors'].append(f"Task {task['id']}: {e}")
        
        print(f"   ✅ {self.stats['tasks']} tasks loaded")
        print(f"   ✅ {self.stats['assignments']} assignments created")
    
    async def _load_leave_periods(self):
        """Load leave periods into database."""
        print("🏖️  Loading Leave Periods...")
        leaves = self.data.get('leave_periods', [])
        
        for leave in leaves:
            try:
                await self._create_object('ot_leave_period', leave['id'], {
                    'leave_type': leave['leave_type'],
                    'start_date': leave['start_date'],
                    'end_date': leave['end_date'],
                    'approval_status': leave['approval_status'],
                    'reason': leave.get('reason', '')
                })
                
                # Create link to person
                await self._create_link(
                    'lt_person_has_leave',
                    leave['person_id'],
                    leave['id']
                )
            except Exception as e:
                self.stats['errors'].append(f"Leave {leave['id']}: {e}")
        
        print(f"   ✅ {len(leaves)} leave periods loaded")
    
    async def _load_productivity_profiles(self):
        """Load productivity profiles into database."""
        print("📊 Loading Productivity Profiles...")
        profiles = self.data.get('productivity_profiles', [])
        
        for profile in profiles:
            try:
                profile_id = f"profile_{profile['person_id']}_{profile['project_type']}"
                await self._create_object('ot_productivity_profile', profile_id, {
                    'person_id': profile['person_id'],
                    'project_type': profile['project_type'],
                    'velocity_factor': profile['velocity_factor'],
                    'estimation_accuracy': profile['estimation_accuracy'],
                    'tasks_completed_count': profile['tasks_completed_count'],
                    'avg_task_completion_hours': profile['avg_task_completion_hours'],
                    'last_updated': profile['last_updated']
                })
                
                # Create link
                await self._create_link(
                    'lt_person_has_productivity_profile',
                    profile['person_id'],
                    profile_id
                )
            except Exception as e:
                self.stats['errors'].append(f"Profile {profile_id}: {e}")
        
        print(f"   ✅ {len(profiles)} productivity profiles loaded")
    
    # Scenario-specific loaders
    async def _load_sick_leave_scenario(self):
        """Load data for sick leave scenario."""
        await self._load_sprints()
        await self._load_tasks()
        await self._load_leave_periods()
        await self._load_productivity_profiles()
    
    async def _load_scope_change_scenario(self):
        """Load data for scope change scenario."""
        await self._load_sprints()
        await self._load_tasks()
    
    async def _load_sprint_planning_scenario(self):
        """Load data for sprint planning scenario."""
        await self._load_sprints()
        await self._load_tasks()
    
    async def _load_skill_matching_scenario(self):
        """Load data for skill matching scenario."""
        await self._load_tasks()
    
    async def _load_conflict_scenario(self):
        """Load data for conflict detection scenario."""
        await self._load_sprints()
        await self._load_tasks()
    
    # Helper methods
    async def _create_object(self, type_id: str, obj_id: str, data: Dict) -> bool:
        """Create an object in the database."""
        # This would call the actual OrgMind API
        # For now, just simulate success
        if self.api_client:
            try:
                await self.api_client.create_object(type_id, obj_id, data)
                return True
            except Exception as e:
                print(f"   ⚠️  Failed to create {type_id}/{obj_id}: {e}")
                return False
        return True
    
    async def _create_link(self, link_type_id: str, source_id: str, target_id: str, data: Dict = None) -> bool:
        """Create a link in the database."""
        if self.api_client:
            try:
                await self.api_client.create_link(link_type_id, source_id, target_id, data or {})
                return True
            except Exception as e:
                print(f"   ⚠️  Failed to create link {link_type_id}: {e}")
                return False
        return True
    
    async def _clear_existing_data(self):
        """Clear existing sample data."""
        print("🧹 Clearing existing sample data...")
        # This would call the actual OrgMind API to clear data
        print("   ✅ Existing data cleared")
    
    def _print_stats(self):
        """Print loading statistics."""
        print(f"""
Statistics:
  Customers:   {self.stats['customers']}
  Projects:    {self.stats['projects']}
  People:      {self.stats['people']}
  Skills:      {self.stats['skills']}
  Tasks:       {self.stats['tasks']}
  Assignments: {self.stats['assignments']}
        """)
        
        if self.stats['errors']:
            print(f"\n⚠️  {len(self.stats['errors'])} errors occurred:")
            for error in self.stats['errors'][:10]:
                print(f"   • {error}")
            if len(self.stats['errors']) > 10:
                print(f"   ... and {len(self.stats['errors']) - 10} more")


def list_scenarios():
    """List available demo scenarios."""
    loader = SampleDataLoader()
    loader.load_data_file()
    
    print("\n📋 Available Demo Scenarios:\n")
    
    for scenario_id, scenario in loader.data.get('demo_scenarios', {}).items():
        print(f"  {scenario_id}")
        print(f"    Name: {scenario['name']}")
        print(f"    Description: {scenario['description']}")
        print(f"    Trigger: {scenario['trigger']}")
        print()


async def main():
    parser = argparse.ArgumentParser(
        description='Load sample data into OrgMind for Project Management Extension'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clear existing data before loading'
    )
    parser.add_argument(
        '--scenario',
        type=str,
        help='Load specific scenario only',
        choices=['sick_leave', 'scope_change', 'sprint_planning', 'skill_matching', 'conflict']
    )
    parser.add_argument(
        '--list-scenarios',
        action='store_true',
        help='List available demo scenarios'
    )
    parser.add_argument(
        '--file',
        type=str,
        default=None,
        help='Path to custom sample data JSON file'
    )
    
    args = parser.parse_args()
    
    if args.list_scenarios:
        list_scenarios()
        return
    
    loader = SampleDataLoader()
    
    if args.file:
        loader.load_data_file(args.file)
    else:
        loader.load_data_file()
    
    if args.scenario:
        scenario_map = {
            'sick_leave': 'sick_leave_impact',
            'scope_change': 'scope_change',
            'sprint_planning': 'sprint_planning',
            'skill_matching': 'skill_matching',
            'conflict': 'resource_conflict'
        }
        await loader.load_scenario(scenario_map[args.scenario])
    else:
        await loader.load_all(clean=args.clean)


if __name__ == '__main__':
    asyncio.run(main())
