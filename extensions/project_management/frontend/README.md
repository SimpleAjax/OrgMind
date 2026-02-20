# Project Management Dashboard

A web dashboard for project managers to view and interact with the AI-powered project management system.

## Structure

```
frontend/
├── index.html          # Main dashboard
├── css/
│   └── styles.css      # Dashboard styles
├── js/
│   ├── api.js          # API client
│   ├── dashboard.js    # Dashboard logic
│   └── components.js   # Reusable components
└── README.md
```

## Pages

1. **Portfolio Dashboard** - All projects, health indicators
2. **Project Detail** - Tasks, timeline, team
3. **Resource View** - People, allocations, utilization
4. **Sprint Planning** - AI recommendations
5. **Nudges Inbox** - Alerts and actions
6. **Reports** - Portfolio, utilization, skills

## Integration

The dashboard is a static HTML/JS application that can be:
1. Served standalone
2. Integrated into the main OrgMind frontend
3. Deployed as a separate container

## API Endpoints Used

- `GET /pm/dashboard/portfolio` - Portfolio overview
- `GET /pm/dashboard/risks` - At-risk items
- `GET /pm/projects/{id}/health` - Project health
- `GET /pm/sprints/{id}/recommendations` - AI recommendations
- `GET /pm/nudges` - List nudges
- etc.

## Setup

```bash
# Serve locally
cd frontend
python -m http.server 8080

# Access at http://localhost:8080
```

## Docker Deployment

```bash
docker build -t orgmind-pm-dashboard .
docker run -p 8080:80 orgmind-pm-dashboard
```
