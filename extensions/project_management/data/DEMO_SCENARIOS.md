# Project Management Extension - Demo Scenarios

This document describes the demo scenarios included in the sample data for testing and demonstrating the AI-powered Project Management system.

---

## Quick Start

### Load All Sample Data
```bash
python extensions/project_management/data/load_sample_data.py
```

### Load Specific Scenario
```bash
# Sick Leave Impact
python extensions/project_management/data/load_sample_data.py --scenario sick_leave

# Scope Change Analysis
python extensions/project_management/data/load_sample_data.py --scenario scope_change

# Sprint Planning
python extensions/project_management/data/load_sample_data.py --scenario sprint_planning

# Skill Matching
python extensions/project_management/data/load_sample_data.py --scenario skill_matching

# Resource Conflict
python extensions/project_management/data/load_sample_data.py --scenario conflict
```

### List Available Scenarios
```bash
python extensions/project_management/data/load_sample_data.py --list-scenarios
```

---

## Scenario 1: Sick Leave Impact

### Overview
Demonstrates real-time replanning when a team member calls in sick.

### Setup
- **Person**: Alice Chen (Senior Developer, Python/Django expert)
- **Current Tasks**: API Integration (in progress), Database Optimization (todo)
- **Leave**: March 16-20 (5 days)

### Demo Steps

1. **View Current State**
   ```bash
   GET /pm/resources/person_dev_alice/utilization
   ```
   - Shows 100% allocation
   - 2 active tasks assigned

2. **Trigger Sick Leave**
   ```bash
   POST /pm/simulate/leave
   {
     "person_id": "person_dev_alice",
     "start_date": "2026-03-16",
     "end_date": "2026-03-18",
     "leave_type": "sick"
   }
   ```

3. **View Impact Analysis**
   ```bash
   GET /pm/simulate/leave?person_id=person_dev_alice&...
   ```
   
   **Expected Results:**
   - Impact level: `medium`
   - Affected tasks: 2
   - Delay projection: 3-5 days
   - Alternative resources: Bob Martinez (90% skill match)

4. **Check Generated Nudges**
   ```bash
   GET /pm/nudges?type=risk
   ```
   
   **Expected Nudge:**
   ```json
   {
     "type": "risk",
     "severity": "warning",
     "title": "Alice Developer is on sick leave",
     "description": "Impact analysis shows 2 tasks affected across Enterprise Platform.",
     "suggested_actions": [
       "Reassign API Integration to Bob Martinez",
       "Extend Database Optimization deadline by 3 days"
     ]
   }
   ```

### Key Features Demonstrated
- Real-time impact analysis
- Skill-based alternative resource suggestion
- Timeline recalculation
- Automated nudge generation

---

## Scenario 2: Scope Change Impact

### Overview
Shows how the system analyzes the impact of adding new tasks to an existing project.

### Setup
- **Project**: Enterprise Platform Migration (cust_techcorp)
- **Current Status**: 50% complete (5 of 10 tasks done)
- **Timeline**: Jan 15 - Jun 30

### Demo Steps

1. **View Current Project Health**
   ```bash
   GET /pm/projects/proj_enterprise_platform/health
   ```
   
   **Expected:**
   - Health score: 85
   - Status: healthy
   - On track for deadline

2. **Simulate Scope Change**
   ```bash
   POST /pm/projects/proj_enterprise_platform/impact
   {
     "added_tasks": [
       {"title": "Additional Feature A", "estimated_hours": 40},
       {"title": "Additional Feature B", "estimated_hours": 24},
       {"title": "Integration Update", "estimated_hours": 16}
     ]
   }
   ```

3. **View Impact Report**
   
   **Expected Results:**
   ```json
   {
     "impact_level": "high",
     "can_commit": false,
     "timeline_impact": {
       "original_end_date": "2026-06-30",
       "new_end_date": "2026-07-20",
       "delay_days": 20
     },
     "resource_impact": {
       "additional_hours": 80,
       "cost_impact": 12000
     },
     "affected_projects": [
       {
         "project_id": "proj_enterprise_platform",
         "resource_conflicts": ["person_dev_alice overallocated"]
       }
     ],
     "recommended_actions": [
       "Add 1 senior developer to project",
       "Negotiate deadline extension",
       "Reduce scope of non-critical features"
     ]
   }
   ```

4. **Compare Scenarios**
   ```bash
   POST /pm/simulate/compare
   {
     "scenarios": [
       {"name": "Original Plan", "tasks": [...]},
       {"name": "With Scope Change", "tasks": [...]},
       {"name": "With Additional Resource", "tasks": [...], "additional_people": 1}
     ]
   }
   ```

### Key Features Demonstrated
- Scope change impact calculation
- Timeline projection
- Cost impact analysis
- Cross-project resource conflict detection
- Scenario comparison

---

## Scenario 3: Sprint Planning

### Overview
Demonstrates AI-assisted sprint planning with optimal task selection.

### Setup
- **Sprint**: Sprint 13 - Late March 2026 (Mar 16-29)
- **Team**: 6 members, 560 hours total capacity
- **Backlog**: 10 available tasks across 3 projects

### Demo Steps

1. **View Sprint Capacity**
   ```bash
   GET /pm/sprints/sprint_next/recommendations
   ```

2. **Generate AI Recommendations**
   
   **Expected Results:**
   ```json
   {
     "sprint_id": "sprint_next",
     "total_capacity_hours": 560,
     "recommended_commitment_hours": 476,
     "utilization_target": 0.85,
     "recommended_tasks": [
       {
         "task_id": "task_ml_model",
         "title": "Train Recommendation Model",
         "value_score": 85,
         "effort_score": 64,
         "fit_score": 92,
         "recommended_assignee": "person_dev_david"
       },
       {
         "task_id": "task_payment_gateway",
         "title": "Payment Gateway Integration",
         "value_score": 90,
         "effort_score": 40,
         "fit_score": 88,
         "recommended_assignee": "person_dev_alice"
       }
       // ... more tasks
     ],
     "person_allocations": {
       "person_dev_alice": {
         "allocated_hours": 72,
         "task_count": 2,
         "utilization": 90
       }
       // ... other team members
     },
     "overall_risk_score": 35,
     "risk_factors": [
       "ML model task has 40% delay probability",
       "New project ramp-up time"
     ],
     "recommendation_reasoning": "Selected 8 tasks totaling 476 hours. Prioritized high-value items from Enterprise Platform and E-commerce projects. Sprint risk is moderate due to ML task uncertainty."
   }
   ```

3. **Check Sprint Health**
   ```bash
   GET /pm/sprints/sprint_next/health
   ```
   
   **Expected:**
   - Status: `good`
   - Health score: 78
   - Predicted completion: 95%

4. **Commit Sprint Plan**
   ```bash
   POST /pm/sprints/sprint_next/plan
   {
     "task_ids": ["task_ml_model", "task_payment_gateway", ...],
     "commit": true
   }
   ```

### Key Features Demonstrated
- AI task selection based on value and capacity
- Skill-based assignment recommendations
- Load balancing across team
- Risk assessment
- Capacity optimization

---

## Scenario 4: Skill Matching

### Overview
Shows how the system matches tasks to people based on required skills.

### Setup
- **Task**: Payment Gateway Integration (proj_ecommerce)
- **Required Skills**: Python (level 4, mandatory)
- **Team**: Alice (Python expert), Bob (Frontend), Carol (Junior)

### Demo Steps

1. **View Task Requirements**
   ```bash
   GET /pm/tasks/task_payment_gateway
   ```
   
   **Requirements:**
   - Python: Level 4 (mandatory)
   - Django: Level 3 (preferred)

2. **Get Skill Matches**
   ```bash
   GET /pm/tasks/task_payment_gateway/matches
   ```
   
   **Expected Results:**
   ```json
   {
     "task_id": "task_payment_gateway",
     "matches": [
       {
         "person_id": "person_dev_alice",
         "person_name": "Alice Chen",
         "match_score": 95,
         "is_full_match": true,
         "matching_skills": [
           {"skill": "Python", "required": 4, "has": 5},
           {"skill": "Django", "required": 3, "has": 5}
         ],
         "availability": 20
       },
       {
         "person_id": "person_dev_david",
         "person_name": "David Kim",
         "match_score": 75,
         "is_full_match": true,
         "matching_skills": [
           {"skill": "Python", "required": 4, "has": 5}
         ],
         "availability": 15
       },
       {
         "person_id": "person_dev_carol",
         "person_name": "Carol Thompson",
         "match_score": 35,
         "is_full_match": false,
         "matching_skills": [],
         "below_required": [
           {"skill": "Python", "required": 4, "has": 3}
         ],
         "availability": 30
       }
     ],
     "has_perfect_match": true,
     "skill_gaps": ["No qualified person available with 80%+ availability"]
   }
   ```

3. **Identify Organization Skill Gaps**
   ```bash
   GET /pm/reports/skills
   ```
   
   **Expected:**
   - Python experts: 2 (Alice, David)
   - React experts: 2 (Bob, Carol)
   - ML experts: 1 (David)
   - Gap: Elasticsearch (required by task_search_implementation)

4. **View Training Suggestions**
   ```bash
   GET /pm/person/person_dev_carol/skill-development
   ```
   
   **Expected Suggestions:**
   - Complete Python Advanced course (3 weeks)
   - Shadow Alice on API integration (1 week)
   - Recommended for: Payment Gateway task in future

### Key Features Demonstrated
- Skill requirement parsing
- Match scoring algorithm
- Full vs partial matching
- Availability consideration
- Organization-wide skill gap analysis
- Training recommendations

---

## Scenario 5: Resource Conflict Detection

### Overview
Demonstrates continuous monitoring for resource conflicts.

### Setup
- **Person**: Bob Martinez
- **Current Allocation**: 75% on Mobile UI (48 hours)
- **Additional Assignment**: Auth Flow (50% on 8 hours/day)

### Demo Steps

1. **View Current Allocations**
   ```bash
   GET /pm/resources/person_dev_bob/utilization
   ```
   
   **Current:**
   - Total allocation: 75%
   - Status: optimal

2. **Trigger Overallocation**
   ```bash
   POST /pm/tasks/task_auth_flow/reassign
   {
     "to_person_id": "person_dev_bob",
     "allocation_percent": 50
   }
   ```

3. **Detect Conflicts**
   ```bash
   GET /pm/resources/conflicts
   ```
   
   **Expected Results:**
   ```json
   {
     "total_conflicts": 1,
     "critical_issues": [
       {
         "conflict_type": "overallocation",
         "severity": "high",
         "person_id": "person_dev_bob",
         "person_name": "Bob Martinez",
         "description": "Bob Martinez is overallocated at 125% on 2026-03-05 (25% over capacity)",
         "date_range": {"start": "2026-03-05", "end": "2026-03-12"},
         "allocation_percentage": 125,
         "suggested_actions": [
           {
             "type": "reduce_allocation",
             "description": "Reduce allocation by 25%"
           },
           {
             "type": "extend_timeline",
             "description": "Extend task timelines to spread work"
           },
           {
             "type": "reassign",
             "description": "Reassign Authentication Flow to Carol Thompson"
           }
         ]
       }
     ]
   }
   ```

4. **View Generated Nudge**
   ```bash
   GET /pm/nudges?type=conflict
   ```
   
   **Expected Nudge:**
   ```json
   {
     "type": "conflict",
     "severity": "warning",
     "title": "Resource Conflict: Bob Martinez Overallocated",
     "description": "Bob is allocated 125% from Mar 5-12. Auth Flow assignment creates conflict.",
     "suggested_action": "Reassign Authentication Flow to Carol or extend timeline"
   }
   ```

5. **Resolve Conflict**
   ```bash
   POST /pm/tasks/task_auth_flow/reassign
   {
     "to_person_id": "person_dev_carol",
     "allocation_percent": 25
   }
   ```

### Key Features Demonstrated
- Real-time conflict detection
- Overallocation alerts
- Double-booking detection
- Actionable recommendations
- Automatic nudge generation
- Conflict resolution tracking

---

## Data Model Reference

### Customers
| ID | Name | Tier | Contract Value |
|----|------|------|----------------|
| cust_techcorp | TechCorp Industries | tier_1 | $750,000 |
| cust_innovate | Innovate Solutions LLC | tier_2 | $350,000 |
| cust_startup | NextGen Startup | tier_3 | $75,000 |

### Team Members
| ID | Name | Role | Key Skills |
|----|------|------|------------|
| person_dev_alice | Alice Chen | Senior Developer | Python, Django, PostgreSQL |
| person_dev_bob | Bob Martinez | Senior Developer | React, TypeScript |
| person_dev_carol | Carol Thompson | Developer | React, CSS |
| person_dev_david | David Kim | ML Engineer | Python, TensorFlow |
| person_qa_emma | Emma Wilson | QA Engineer | Selenium, Testing |
| person_design_frank | Frank Johnson | UX Designer | Figma, UX Design |

### Projects
| ID | Name | Customer | Status | Budget |
|----|------|----------|--------|--------|
| proj_enterprise_platform | Enterprise Platform Migration | TechCorp | Active | $180,000 |
| proj_mobile_app | Mobile Banking App | Innovate | Active | $100,000 |
| proj_analytics_dashboard | Analytics Dashboard | Startup | Active | $32,000 |
| proj_ecommerce | E-commerce Platform | TechCorp | Planning | $134,400 |
| proj_ai_integration | AI Recommendation Engine | Innovate | Active | $64,800 |

---

## Tips for Demo Presentations

### Before the Demo
1. Load the appropriate scenario data
2. Verify all systems are running
3. Clear browser cache
4. Have the dashboard open

### During the Demo
1. Start with the Portfolio Dashboard view
2. Show current state before making changes
3. Make changes and immediately show impact
4. Highlight AI-generated recommendations
5. Acknowledge nudges to show workflow

### Key Talking Points
- **Speed**: "Impact analysis completes in under 5 seconds"
- **Intelligence**: "AI ranks alternatives by skill match and availability"
- **Proactive**: "System detects issues before they become critical"
- **Data-Driven**: "Decisions backed by historical velocity data"

---

## Troubleshooting

### Data Not Loading
```bash
# Check if OrgMind API is accessible
curl http://localhost:8000/health

# Verify data file exists
ls extensions/project_management/data/sample_data.json

# Load with verbose output
python load_sample_data.py --clean -v
```

### Nudges Not Generating
- Check if triggers are enabled in OrgMind
- Verify scheduler is running
- Check nudge generation logs

### Calculations Seem Off
- Verify productivity profiles are loaded
- Check task dependencies are correctly set
- Ensure leave periods are in the future

---

## Next Steps

After running these demos, explore:
1. Custom reports with the Report Builder
2. What-if scenario comparisons
3. Historical velocity trends
4. Team capacity planning
5. Integration with external calendars
