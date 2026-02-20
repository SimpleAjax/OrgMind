/**
 * Reusable UI Components for PM Dashboard
 */

// Create a status badge
function createStatusBadge(status) {
    const badge = document.createElement('span');
    badge.className = `badge-status ${status}`;
    badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    return badge;
}

// Create a card element
function createCard(title, content, options = {}) {
    const card = document.createElement('div');
    card.className = `card ${options.className || ''}`;
    
    if (title) {
        const heading = document.createElement('h3');
        heading.textContent = title;
        card.appendChild(heading);
    }
    
    if (typeof content === 'string') {
        const div = document.createElement('div');
        div.innerHTML = content;
        card.appendChild(div);
    } else if (content instanceof Node) {
        card.appendChild(content);
    }
    
    return card;
}

// Create a metric card
function createMetricCard(title, value, status = 'default') {
    const card = document.createElement('div');
    card.className = `card metric-card ${status}`;
    
    const heading = document.createElement('h3');
    heading.textContent = title;
    
    const metric = document.createElement('div');
    metric.className = 'metric';
    metric.textContent = value;
    
    card.appendChild(heading);
    card.appendChild(metric);
    
    return card;
}

// Create a nudge item
function createNudgeItem(nudge) {
    const item = document.createElement('div');
    item.className = `nudge-item ${nudge.severity}`;
    item.dataset.id = nudge.id;
    
    const header = document.createElement('div');
    header.className = 'nudge-header';
    
    const title = document.createElement('span');
    title.className = 'nudge-title';
    title.textContent = nudge.title;
    
    const severity = document.createElement('span');
    severity.className = `badge-status ${nudge.severity}`;
    severity.textContent = nudge.severity;
    
    header.appendChild(title);
    header.appendChild(severity);
    
    const description = document.createElement('p');
    description.textContent = nudge.description;
    
    const actions = document.createElement('div');
    actions.className = 'nudge-actions';
    
    const ackBtn = document.createElement('button');
    ackBtn.className = 'btn btn-secondary';
    ackBtn.textContent = 'Acknowledge';
    ackBtn.onclick = () => handleAcknowledgeNudge(nudge.id);
    
    const actBtn = document.createElement('button');
    actBtn.className = 'btn btn-primary';
    actBtn.textContent = 'Take Action';
    actBtn.onclick = () => handleNudgeAction(nudge.id);
    
    const dismissBtn = document.createElement('button');
    dismissBtn.className = 'btn btn-secondary';
    dismissBtn.textContent = 'Dismiss';
    dismissBtn.onclick = () => handleDismissNudge(nudge.id);
    
    actions.appendChild(ackBtn);
    actions.appendChild(actBtn);
    actions.appendChild(dismissBtn);
    
    item.appendChild(header);
    item.appendChild(description);
    item.appendChild(actions);
    
    return item;
}

// Create a project row for the table
function createProjectRow(project) {
    const tr = document.createElement('tr');
    
    const nameCell = document.createElement('td');
    nameCell.innerHTML = `<strong>${project.name}</strong>`;
    
    const statusCell = document.createElement('td');
    statusCell.textContent = project.status || 'Unknown';
    
    const healthCell = document.createElement('td');
    healthCell.appendChild(createStatusBadge(project.health_status || 'green'));
    
    const priorityCell = document.createElement('td');
    priorityCell.textContent = project.priority_score ? Math.round(project.priority_score) : '-';
    
    const progressCell = document.createElement('td');
    // Would calculate actual progress
    progressCell.textContent = '-';
    
    tr.appendChild(nameCell);
    tr.appendChild(statusCell);
    tr.appendChild(healthCell);
    tr.appendChild(priorityCell);
    tr.appendChild(progressCell);
    
    return tr;
}

// Create a sprint card
function createSprintCard(sprint) {
    const card = document.createElement('div');
    card.className = 'card';
    
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.marginBottom = '12px';
    
    const title = document.createElement('h4');
    title.textContent = sprint.name;
    title.style.margin = '0';
    
    const status = document.createElement('span');
    status.className = `badge-status ${sprint.status || 'active'}`;
    status.textContent = sprint.status || 'Active';
    
    header.appendChild(title);
    header.appendChild(status);
    
    const dates = document.createElement('p');
    dates.style.color = 'var(--text-secondary)';
    dates.style.fontSize = '0.875rem';
    dates.textContent = `${formatDate(sprint.start_date)} - ${formatDate(sprint.end_date)}`;
    
    const actions = document.createElement('div');
    actions.style.marginTop = '12px';
    
    const recommendBtn = document.createElement('button');
    recommendBtn.className = 'btn btn-primary';
    recommendBtn.textContent = 'Get Recommendations';
    recommendBtn.onclick = () => loadSprintRecommendations(sprint.id);
    
    const healthBtn = document.createElement('button');
    healthBtn.className = 'btn btn-secondary';
    healthBtn.textContent = 'Check Health';
    healthBtn.style.marginLeft = '8px';
    healthBtn.onclick = () => loadSprintHealth(sprint.id);
    
    actions.appendChild(recommendBtn);
    actions.appendChild(healthBtn);
    
    card.appendChild(header);
    card.appendChild(dates);
    card.appendChild(actions);
    
    return card;
}

// Create a utilization bar
function createUtilizationBar(percentage) {
    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '24px';
    container.style.backgroundColor = 'var(--bg-color)';
    container.style.borderRadius = '4px';
    container.style.overflow = 'hidden';
    container.style.position = 'relative';
    
    const bar = document.createElement('div');
    bar.style.width = `${Math.min(percentage, 100)}%`;
    bar.style.height = '100%';
    bar.style.backgroundColor = getUtilizationColor(percentage);
    bar.style.transition = 'width 0.3s';
    
    const label = document.createElement('span');
    label.textContent = `${Math.round(percentage)}%`;
    label.style.position = 'absolute';
    label.style.top = '50%';
    label.style.left = '50%';
    label.style.transform = 'translate(-50%, -50%)';
    label.style.fontSize = '0.75rem';
    label.style.fontWeight = '600';
    
    container.appendChild(bar);
    container.appendChild(label);
    
    return container;
}

// Helper: Get color based on utilization
function getUtilizationColor(percentage) {
    if (percentage > 100) return 'var(--danger-color)';
    if (percentage > 85) return 'var(--warning-color)';
    if (percentage < 30) return 'var(--info-color)';
    return 'var(--success-color)';
}

// Helper: Format date
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Show loading state
function showLoading() {
    document.getElementById('loading').classList.add('active');
}

// Hide loading state
function hideLoading() {
    document.getElementById('loading').classList.remove('active');
}

// Show error message
function showError(message) {
    alert(`Error: ${message}`);
}

// Show success message
function showSuccess(message) {
    console.log('Success:', message);
}
