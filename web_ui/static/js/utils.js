// General utility functions for the web UI

// Generic AJAX handler with error handling
function makeRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    return fetch(url, mergedOptions)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .catch(error => {
            console.error('Request failed:', error);
            showNotification('error', `Request failed: ${error.message}`);
            throw error;
        });
}

// Notification system
function showNotification(type, message, duration = 5000) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show notification`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    container.appendChild(notification);
    
    if (duration > 0) {
        setTimeout(() => {
            notification.remove();
        }, duration);
    }
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1055';
    document.body.appendChild(container);
    return container;
}

// Agent management functions
function refreshAgent(agentId) {
    makeRequest(`/api/agents/${agentId}/commands/`, {
        method: 'POST',
        body: JSON.stringify({
            command: 'get_status',
            params: {}
        })
    })
    .then(data => {
        showNotification('success', 'Status refresh command sent');
        setTimeout(() => {
            location.reload();
        }, 2000);
    })
    .catch(error => {
        showNotification('error', 'Failed to refresh agent status');
    });
}

function executeAgentCommand(agentId, command, params = {}) {
    return makeRequest(`/api/agents/${agentId}/commands/`, {
        method: 'POST',
        body: JSON.stringify({
            command: command,
            params: params
        })
    });
}

// Form utilities
function serializeForm(form) {
    const formData = new FormData(form);
    const data = {};
    
    for (const [key, value] of formData.entries()) {
        if (data[key]) {
            if (Array.isArray(data[key])) {
                data[key].push(value);
            } else {
                data[key] = [data[key], value];
            }
        } else {
            data[key] = value;
        }
    }
    
    return data;
}

function validateForm(form) {
    const errors = [];
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            errors.push(`${field.labels[0]?.textContent || field.name} is required`);
            field.classList.add('is-invalid');
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    // Email validation
    const emailFields = form.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            errors.push(`${field.labels[0]?.textContent || field.name} must be a valid email`);
            field.classList.add('is-invalid');
        }
    });
    
    return errors;
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Modal utilities
function showModal(modalId) {
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
    return modal;
}

function hideModal(modalId) {
    const modalElement = document.getElementById(modalId);
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
        modal.hide();
    }
}

// Data refresh utilities
function autoRefresh(url, container, interval = 30000) {
    let refreshTimer;
    
    function refresh() {
        makeRequest(url)
            .then(data => {
                if (typeof data === 'string') {
                    container.innerHTML = data;
                } else {
                    updateContainerWithData(container, data);
                }
            })
            .catch(error => {
                console.error('Auto-refresh failed:', error);
            });
    }
    
    function start() {
        refreshTimer = setInterval(refresh, interval);
    }
    
    function stop() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }
    
    return {
        start,
        stop,
        refresh
    };
}

function updateContainerWithData(container, data) {
    // Generic function to update container with JSON data
    // This can be customized based on data structure
    if (data.html) {
        container.innerHTML = data.html;
    } else if (data.agents) {
        updateAgentsDisplay(container, data.agents);
    } else {
        console.warn('Unknown data format for container update');
    }
}

// Status display utilities
function getStatusBadge(status) {
    const statusClasses = {
        'online': 'success',
        'offline': 'danger',
        'pending': 'warning',
        'error': 'danger',
        'unknown': 'secondary'
    };
    
    const className = statusClasses[status] || 'secondary';
    return `<span class="badge bg-${className}">${status}</span>`;
}

function formatLastSeen(timestamp) {
    if (!timestamp) return 'Never';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    if (diffDays < 7) return `${diffDays} days ago`;
    
    return date.toLocaleDateString();
}

// File download utilities
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    downloadFile(url, filename);
    URL.revokeObjectURL(url);
}

// Theme utilities
function toggleTheme() {
    const body = document.body;
    const currentTheme = body.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    body.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update theme toggle button icon
    const themeIcon = document.querySelector('#theme-toggle i');
    if (themeIcon) {
        themeIcon.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
}

function loadSavedTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
    
    // Update theme toggle button icon
    const themeIcon = document.querySelector('#theme-toggle i');
    if (themeIcon) {
        themeIcon.className = savedTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// Search utilities
function initializeSearch(searchInput, resultContainer, searchUrl) {
    let searchTimeout;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();
        
        if (query.length < 2) {
            resultContainer.innerHTML = '';
            return;
        }
        
        searchTimeout = setTimeout(() => {
            makeRequest(`${searchUrl}?q=${encodeURIComponent(query)}`)
                .then(data => {
                    displaySearchResults(resultContainer, data.results || data);
                })
                .catch(error => {
                    resultContainer.innerHTML = '<div class="text-danger">Search failed</div>';
                });
        }, 300);
    });
}

function displaySearchResults(container, results) {
    if (!results || results.length === 0) {
        container.innerHTML = '<div class="text-muted">No results found</div>';
        return;
    }
    
    const html = results.map(result => `
        <div class="search-result p-2 border-bottom">
            <div class="fw-bold">${result.title || result.hostname || result.name}</div>
            <div class="text-muted small">${result.description || result.ip_address || ''}</div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// Initialize common functionality
document.addEventListener('DOMContentLoaded', function() {
    // Load saved theme
    loadSavedTheme();
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Theme toggle button
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Generic form submission handlers
    document.querySelectorAll('form[data-ajax="true"]').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const errors = validateForm(this);
            if (errors.length > 0) {
                showNotification('danger', errors.join('<br>'));
                return;
            }
            
            const formData = serializeForm(this);
            const url = this.action;
            const method = this.method || 'POST';
            
            makeRequest(url, {
                method: method,
                body: JSON.stringify(formData)
            })
            .then(data => {
                if (data.success) {
                    showNotification('success', data.message || 'Operation completed successfully');
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    }
                } else {
                    showNotification('danger', data.message || 'Operation failed');
                }
            })
            .catch(error => {
                showNotification('danger', 'Form submission failed');
            });
        });
    });
});

// Export functions for use in other scripts
window.firewalldCentral = {
    makeRequest,
    showNotification,
    refreshAgent,
    executeAgentCommand,
    serializeForm,
    validateForm,
    showModal,
    hideModal,
    autoRefresh,
    getStatusBadge,
    formatLastSeen,
    downloadFile,
    downloadJSON,
    toggleTheme,
    initializeSearch
};