/**
 * Dashboard Logic for PM Dashboard
 */

// State
let currentPage = 'portfolio';
let projectsData = [];
let nudgesData = [];

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initializeNavigation();
    initializeDates();
    loadPortfolioData();
    loadNudgesCount();
});

// Navigation
function initializeNavigation() {
    const navLinks = document.querySelectorAll('.nav-links a');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            navigateToPage(page);
        });
    });
    
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        refreshCurrentPage();
    });
}

function navigateToPage(page) {
    // Update nav
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.classList.remove('active');
        if (link.dataset.page === page) {
            link.classList.add('active');
        }
    });
    
    // Update page title
    const titles = {
        'portfolio': 'Portfolio Dashboard',
        'projects': 'Projects',
        'resources': 'Resources',
        'sprints': 'Sprints',
        'nudges': 'Nudges',
        'reports': 'Reports'
    };
    document.getElementById('page-title').textContent = titles[page] || page;
    
    // Show/hide pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`${page}-page`).classList.add('active');
    
    currentPage = page;
    
    // Load page data
    refreshCurrentPage();
}

function refreshCurrentPage() {
    switch(currentPage) {
        case 'portfolio':
            loadPortfolioData();
            break;
        case 'projects':
            loadProjects();
            break;
        case 'resources':
            loadUtilization();
            break;
        case 'sprints':
            loadSprints();
            break;
        case 'nudges':
            loadNudges();
            break;
    }
}

// Initialize date inputs
function initializeDates() {
    const today = new Date();
    const thirtyDaysLater = new Date(today.getTime() + (30 * 24 * 60 * 60 * 1000));
    
    const startInput = document.getElementById('util-start-date');
    const endInput = document.getElementById('util-end-date');
    
    if (startInput) startInput.valueAsDate = today;
    if (endInput) endInput.valueAsDate = thirtyDaysLater;
}

// Portfolio Page
async function loadPortfolioData() {
    showLoading();
    
    try {
        const data = await api.getPortfolioOverview();
        
        // Update metrics
        document.getElementById('total-projects').textContent = data.summary.total_projects;
        document.getElementById('at-risk-count').textContent = data.summary.at_risk_count;
        document.getElementById('healthy-count').textContent = data.summary.healthy_count;
        document.getElementById('overdue-count').textContent = data.summary.overdue_count;
        
        // Update projects table
        const tbody = document.querySelector('#projects-table tbody');
        tbody.innerHTML = '';
        
        data.projects.forEach(project => {
            tbody.appendChild(createProjectRow(project));
        });
        
    } catch (error) {
        showError('Failed to load portfolio data');
    } finally {
        hideLoading();
    }
}

// Projects Page
async function loadProjects() {
    showLoading();
    
    try {
        const data = await api.getPortfolioOverview();
        projectsData = data.projects;
        
        const grid = document.getElementById('projects-grid');
        grid.innerHTML = '';
        
        projectsData.forEach(project => {
            const card = createCard(project.name, `
                <p>Status: ${project.status}</p>
                <p>Health: ${project.health_status || 'Unknown'}</p>
                <p>Priority: ${Math.round(project.priority_score || 0)}</p>
            `);
            grid.appendChild(card);
        });
        
    } catch (error) {
        showError('Failed to load projects');
    } finally {
        hideLoading();
    }
}

// Resources Page
async function loadUtilization() {
    showLoading();
    
    try {
        const startDate = document.getElementById('util-start-date').value;
        const endDate = document.getElementById('util-end-date').value;
        
        const data = await api.getUtilizationHeatmap(startDate, endDate);
        
        const container = document.getElementById('utilization-heatmap');
        container.innerHTML = '';
        
        // Simple list view for now
        data.utilization.forEach(u => {
            const row = document.createElement('div');
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.padding = '12px';
            row.style.borderBottom = '1px solid var(--border-color)';
            
            const name = document.createElement('div');
            name.style.width = '150px';
            name.textContent = u.person_name;
            
            const bar = createUtilizationBar(u.average_utilization);
            bar.style.flex = '1';
            bar.style.marginLeft = '16px';
            
            row.appendChild(name);
            row.appendChild(bar);
            container.appendChild(row);
        });
        
    } catch (error) {
        showError('Failed to load utilization data');
    } finally {
        hideLoading();
    }
}

// Sprints Page
async function loadSprints() {
    showLoading();
    
    try {
        // For demo, we'll use placeholder data
        // In real implementation, fetch from API
        const sprints = [
            { id: 'sprint_1', name: 'Sprint 1 - Feb 2026', status: 'active', start_date: '2026-02-01', end_date: '2026-02-14' },
            { id: 'sprint_2', name: 'Sprint 2 - Feb/Mar 2026', status: 'planning', start_date: '2026-02-15', end_date: '2026-02-28' }
        ];
        
        const container = document.getElementById('sprints-list');
        container.innerHTML = '';
        
        sprints.forEach(sprint => {
            container.appendChild(createSprintCard(sprint));
        });
        
    } catch (error) {
        showError('Failed to load sprints');
    } finally {
        hideLoading();
    }
}

async function loadSprintRecommendations(sprintId) {
    showLoading();
    
    try {
        const data = await api.getSprintRecommendations(sprintId);
        
        const container = document.getElementById('sprint-recommendations');
        container.style.display = 'block';
        
        const content = document.getElementById('recommendations-content');
        content.innerHTML = `
            <p><strong>Recommended Tasks:</strong> ${data.task_count}</p>
            <p><strong>Total Value Score:</strong> ${Math.round(data.total_value_score)}</p>
            <p><strong>Risk Level:</strong> ${data.risk_assessment.risk_level}</p>
            <p><strong>Reasoning:</strong> ${data.reasoning}</p>
        `;
        
    } catch (error) {
        showError('Failed to load recommendations');
    } finally {
        hideLoading();
    }
}

async function loadSprintHealth(sprintId) {
    try {
        const data = await api.getSprintHealth(sprintId);
        alert(`Sprint Health: ${data.status}\nScore: ${data.health_score}\nCompletion: ${data.progress.completion_percentage}%`);
    } catch (error) {
        showError('Failed to load sprint health');
    }
}

// Nudges Page
async function loadNudges() {
    showLoading();
    
    try {
        const data = await api.getNudges();
        nudgesData = data.nudges;
        
        const container = document.getElementById('nudges-list');
        container.innerHTML = '';
        
        nudgesData.forEach(nudge => {
            container.appendChild(createNudgeItem(nudge));
        });
        
    } catch (error) {
        showError('Failed to load nudges');
    } finally {
        hideLoading();
    }
}

async function loadNudgesCount() {
    try {
        const data = await api.getNudges(status = 'new', limit = 1);
        const count = data.by_status.new || 0;
        document.getElementById('nudge-count').textContent = count;
    } catch (error) {
        console.error('Failed to load nudges count', error);
    }
}

// Nudge Actions
async function handleAcknowledgeNudge(nudgeId) {
    try {
        await api.acknowledgeNudge(nudgeId);
        showSuccess('Nudge acknowledged');
        loadNudges();
        loadNudgesCount();
    } catch (error) {
        showError('Failed to acknowledge nudge');
    }
}

async function handleDismissNudge(nudgeId) {
    try {
        await api.dismissNudge(nudgeId);
        showSuccess('Nudge dismissed');
        loadNudges();
        loadNudgesCount();
    } catch (error) {
        showError('Failed to dismiss nudge');
    }
}

async function handleNudgeAction(nudgeId) {
    try {
        await api.executeNudgeAction(nudgeId, 0);
        showSuccess('Action executed');
        loadNudges();
        loadNudgesCount();
    } catch (error) {
        showError('Failed to execute action');
    }
}

// Reports
async function generateReport(type) {
    showLoading();
    
    try {
        let data;
        
        switch(type) {
            case 'portfolio':
                data = await api.getPortfolioReport();
                break;
            case 'utilization':
                const start = document.getElementById('util-start-date').value;
                const end = document.getElementById('util-end-date').value;
                data = await api.getUtilizationReport(start, end);
                break;
            case 'skills':
                data = await api.getSkillsGapReport();
                break;
        }
        
        const output = document.getElementById('report-output');
        output.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        
    } catch (error) {
        showError('Failed to generate report');
    } finally {
        hideLoading();
    }
}

// Nudge filter buttons
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('btn-filter')) {
        document.querySelectorAll('.btn-filter').forEach(btn => btn.classList.remove('active'));
        e.target.classList.add('active');
        
        const filter = e.target.dataset.filter;
        // Filter nudges
        const nudges = document.querySelectorAll('.nudge-item');
        nudges.forEach(nudge => {
            if (filter === 'all' || nudge.classList.contains(filter)) {
                nudge.style.display = 'block';
            } else {
                nudge.style.display = 'none';
            }
        });
    }
});
