/**
 * API Client for OrgMind PM Dashboard
 */

const API_BASE_URL = '/pm';

class PMAPI {
    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ message: 'Unknown error' }));
                throw new Error(error.detail || error.message || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Dashboard
    async getPortfolioOverview(status, limit = 50) {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        params.append('limit', limit);
        return this.request(`/dashboard/portfolio?${params}`);
    }

    async getRiskDashboard(severity, limit = 20) {
        const params = new URLSearchParams();
        if (severity) params.append('severity', severity);
        params.append('limit', limit);
        return this.request(`/dashboard/risks?${params}`);
    }

    async getUtilizationHeatmap(startDate, endDate) {
        return this.request(`/dashboard/utilization?start_date=${startDate}&end_date=${endDate}`);
    }

    // Projects
    async getProjectHealth(projectId) {
        return this.request(`/projects/${projectId}/health`);
    }

    async analyzeProjectImpact(projectId, addedTasks, removedTaskIds) {
        return this.request(`/projects/${projectId}/impact`, {
            method: 'POST',
            body: { added_tasks: addedTasks, removed_task_ids: removedTaskIds }
        });
    }

    async getProjectTimeline(projectId) {
        return this.request(`/projects/${projectId}/timeline`);
    }

    // Tasks
    async getTaskMatches(taskId, limit = 5) {
        return this.request(`/tasks/${taskId}/matches?limit=${limit}`);
    }

    async getTaskDependencies(taskId) {
        return this.request(`/tasks/${taskId}/dependencies`);
    }

    async reassignTask(taskId, toPersonId, fromPersonId, reason) {
        return this.request(`/tasks/${taskId}/reassign`, {
            method: 'POST',
            body: { to_person_id: toPersonId, from_person_id: fromPersonId, reason }
        });
    }

    // Resources
    async getAllocations(dateFrom, dateTo, personId, projectId) {
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (personId) params.append('person_id', personId);
        if (projectId) params.append('project_id', projectId);
        return this.request(`/resources/allocations?${params}`);
    }

    async getPersonUtilization(personId, startDate, endDate) {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        return this.request(`/resources/${personId}/utilization?${params}`);
    }

    async getConflicts(severity, conflictType) {
        const params = new URLSearchParams();
        if (severity) params.append('severity', severity);
        if (conflictType) params.append('conflict_type', conflictType);
        return this.request(`/resources/conflicts?${params}`);
    }

    // Sprints
    async getSprintRecommendations(sprintId) {
        return this.request(`/sprints/${sprintId}/recommendations`);
    }

    async commitSprintPlan(sprintId, taskIds, assignments) {
        return this.request(`/sprints/${sprintId}/plan`, {
            method: 'POST',
            body: { task_ids: taskIds, assignments }
        });
    }

    async getSprintHealth(sprintId) {
        return this.request(`/sprints/${sprintId}/health`);
    }

    // Simulation
    async simulateLeave(personId, startDate, endDate, leaveType = 'vacation') {
        return this.request('/simulate/leave', {
            method: 'POST',
            body: { person_id: personId, start_date: startDate, end_date: endDate, leave_type: leaveType }
        });
    }

    async simulateScopeChange(projectId, addedTasks, removedTaskIds) {
        return this.request('/simulate/scope', {
            method: 'POST',
            body: { project_id: projectId, added_tasks: addedTasks, removed_task_ids: removedTaskIds }
        });
    }

    async compareScenarios(scenarios) {
        return this.request('/simulate/compare', {
            method: 'POST',
            body: { scenarios }
        });
    }

    // Reports
    async getPortfolioReport(period = 'monthly') {
        return this.request(`/reports/portfolio?period=${period}`);
    }

    async getUtilizationReport(startDate, endDate) {
        return this.request(`/reports/utilization?start_date=${startDate}&end_date=${endDate}`);
    }

    async getSkillsGapReport() {
        return this.request('/reports/skills');
    }

    // Nudges
    async getNudges(status, type, severity, forMe = true, limit = 50) {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        if (type) params.append('type', type);
        if (severity) params.append('severity', severity);
        params.append('for_me', forMe);
        params.append('limit', limit);
        return this.request(`/nudges?${params}`);
    }

    async acknowledgeNudge(nudgeId) {
        return this.request(`/nudges/${nudgeId}/acknowledge`, { method: 'POST' });
    }

    async dismissNudge(nudgeId, reason) {
        return this.request(`/nudges/${nudgeId}/dismiss`, {
            method: 'POST',
            body: reason ? { reason } : undefined
        });
    }

    async executeNudgeAction(nudgeId, actionIndex, parameters) {
        return this.request(`/nudges/${nudgeId}/act`, {
            method: 'POST',
            body: { action_index: actionIndex, parameters }
        });
    }
}

// Create global API instance
const api = new PMAPI();
