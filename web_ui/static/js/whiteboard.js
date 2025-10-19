// Whiteboard functionality for network visualization

class Whiteboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.agents = new Map();
        this.connections = new Map();
        this.zoom = 1;
        this.panX = 0;
        this.panY = 0;
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.selectedAgent = null;
        this.showConnections = true;
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Mouse events for panning
        this.container.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.container.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.container.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.container.addEventListener('wheel', this.onWheel.bind(this));
        
        // Context menu
        this.container.addEventListener('contextmenu', this.onContextMenu.bind(this));
        
        // Close context menu on click
        document.addEventListener('click', this.closeContextMenu.bind(this));
    }
    
    addAgent(agent) {
        const agentElement = this.createAgentElement(agent);
        this.container.appendChild(agentElement);
        this.agents.set(agent.id, {
            ...agent,
            element: agentElement
        });
        
        this.updateAgentPosition(agent.id, agent.position_x || 0, agent.position_y || 0);
    }
    
    createAgentElement(agent) {
        const agentDiv = document.createElement('div');
        agentDiv.className = `agent-node ${agent.status}`;
        agentDiv.dataset.agentId = agent.id;
        agentDiv.innerHTML = `
            <i class="fas fa-server"></i>
            <div class="agent-label">${agent.hostname}</div>
        `;
        
        // Make draggable
        agentDiv.addEventListener('mousedown', this.onAgentMouseDown.bind(this));
        agentDiv.addEventListener('click', this.onAgentClick.bind(this));
        agentDiv.addEventListener('dblclick', this.onAgentDoubleClick.bind(this));
        
        return agentDiv;
    }
    
    updateAgentPosition(agentId, x, y) {
        const agent = this.agents.get(agentId);
        if (agent) {
            agent.position_x = x;
            agent.position_y = y;
            agent.element.style.left = `${x}px`;
            agent.element.style.top = `${y}px`;
            
            this.updateConnections();
        }
    }
    
    addConnection(connection) {
        const connectionElement = this.createConnectionElement(connection);
        this.container.appendChild(connectionElement);
        this.connections.set(connection.id, {
            ...connection,
            element: connectionElement
        });
        
        this.updateConnectionPosition(connection.id);
    }
    
    createConnectionElement(connection) {
        const line = document.createElement('div');
        line.className = 'connection-line';
        line.style.backgroundColor = connection.color || '#007bff';
        line.title = `${connection.source_port || 'Any'} -> ${connection.target_port || 'Any'} (${connection.protocol || 'Any'})`;
        
        return line;
    }
    
    updateConnectionPosition(connectionId) {
        const connection = this.connections.get(connectionId);
        if (!connection) return;
        
        const sourceAgent = this.agents.get(connection.source_agent_id);
        const targetAgent = this.agents.get(connection.target_agent_id);
        
        if (!sourceAgent || !targetAgent) return;
        
        const sourceX = sourceAgent.position_x + 40; // Center of agent node
        const sourceY = sourceAgent.position_y + 40;
        const targetX = targetAgent.position_x + 40;
        const targetY = targetAgent.position_y + 40;
        
        const distance = Math.sqrt(Math.pow(targetX - sourceX, 2) + Math.pow(targetY - sourceY, 2));
        const angle = Math.atan2(targetY - sourceY, targetX - sourceX) * 180 / Math.PI;
        
        connection.element.style.width = `${distance}px`;
        connection.element.style.left = `${sourceX}px`;
        connection.element.style.top = `${sourceY}px`;
        connection.element.style.transform = `rotate(${angle}deg)`;
        connection.element.style.display = this.showConnections ? 'block' : 'none';
    }
    
    updateConnections() {
        for (const connectionId of this.connections.keys()) {
            this.updateConnectionPosition(connectionId);
        }
    }
    
    onMouseDown(event) {
        if (event.target === this.container) {
            this.isDragging = true;
            this.dragStartX = event.clientX - this.panX;
            this.dragStartY = event.clientY - this.panY;
        }
    }
    
    onMouseMove(event) {
        if (this.isDragging) {
            this.panX = event.clientX - this.dragStartX;
            this.panY = event.clientY - this.dragStartY;
            this.updateTransform();
        }
    }
    
    onMouseUp() {
        this.isDragging = false;
    }
    
    onWheel(event) {
        event.preventDefault();
        
        const delta = event.deltaY > 0 ? 0.9 : 1.1;
        this.zoom *= delta;
        this.zoom = Math.max(0.1, Math.min(3, this.zoom));
        
        this.updateTransform();
        this.updateZoomDisplay();
    }
    
    onAgentMouseDown(event) {
        event.stopPropagation();
        
        const agentElement = event.currentTarget;
        const agentId = agentElement.dataset.agentId;
        let startX = event.clientX;
        let startY = event.clientY;
        let hasMoved = false;
        
        const onMouseMove = (moveEvent) => {
            hasMoved = true;
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;
            
            const agent = this.agents.get(agentId);
            if (agent) {
                const newX = agent.position_x + deltaX / this.zoom;
                const newY = agent.position_y + deltaY / this.zoom;
                
                this.updateAgentPosition(agentId, newX, newY);
            }
            
            startX = moveEvent.clientX;
            startY = moveEvent.clientY;
        };
        
        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            
            if (hasMoved) {
                this.saveAgentPosition(agentId);
            }
        };
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }
    
    onAgentClick(event) {
        event.stopPropagation();
        const agentId = event.currentTarget.dataset.agentId;
        this.selectAgent(agentId);
    }
    
    onAgentDoubleClick(event) {
        event.stopPropagation();
        const agentId = event.currentTarget.dataset.agentId;
        this.showAgentDetails(agentId);
    }
    
    onContextMenu(event) {
        event.preventDefault();
        
        if (event.target.classList.contains('agent-node')) {
            const agentId = event.target.dataset.agentId;
            this.selectedAgent = agentId;
            this.showContextMenu(event.clientX, event.clientY);
        }
    }
    
    showContextMenu(x, y) {
        const contextMenu = document.getElementById('context-menu');
        contextMenu.style.left = `${x}px`;
        contextMenu.style.top = `${y}px`;
        contextMenu.style.display = 'block';
    }
    
    closeContextMenu() {
        const contextMenu = document.getElementById('context-menu');
        contextMenu.style.display = 'none';
    }
    
    selectAgent(agentId) {
        // Remove previous selection
        this.container.querySelectorAll('.agent-node.selected').forEach(node => {
            node.classList.remove('selected');
        });
        
        // Select new agent
        const agent = this.agents.get(agentId);
        if (agent) {
            agent.element.classList.add('selected');
            this.selectedAgent = agentId;
        }
    }
    
    showAgentDetails(agentId) {
        const agent = this.agents.get(agentId);
        if (agent) {
            // Load agent details via AJAX
            fetch(`/api/agents/${agentId}/`)
                .then(response => response.json())
                .then(data => {
                    this.displayAgentInfo(data);
                })
                .catch(error => {
                    console.error('Error loading agent details:', error);
                });
        }
    }
    
    displayAgentInfo(agentData) {
        const panel = document.getElementById('agent-info-panel');
        const title = document.getElementById('agent-info-title');
        const content = document.getElementById('agent-info-content');
        
        title.textContent = agentData.hostname;
        content.innerHTML = `
            <div class="mb-3">
                <strong>Status:</strong> 
                <span class="badge bg-${this.getStatusColor(agentData.status)}">${agentData.status}</span>
            </div>
            <div class="mb-3">
                <strong>IP Address:</strong> ${agentData.ip_address}
            </div>
            <div class="mb-3">
                <strong>Mode:</strong> ${agentData.mode}
            </div>
            <div class="mb-3">
                <strong>Last Seen:</strong> ${agentData.last_seen ? new Date(agentData.last_seen).toLocaleString() : 'Never'}
            </div>
            <div class="mb-3">
                <strong>Version:</strong> ${agentData.version || 'Unknown'}
            </div>
            <div class="mb-3">
                <strong>OS:</strong> ${agentData.operating_system || 'Unknown'}
            </div>
            <hr>
            <button class="btn btn-primary btn-sm" onclick="executeCommand('get_status')">
                <i class="fas fa-sync"></i> Refresh Status
            </button>
            <button class="btn btn-outline-secondary btn-sm" onclick="window.location.href='/agents/${agentData.id}/'">
                <i class="fas fa-external-link-alt"></i> Full Details
            </button>
        `;
        
        panel.classList.add('open');
    }
    
    getStatusColor(status) {
        const colors = {
            'online': 'success',
            'offline': 'danger',
            'pending': 'warning',
            'error': 'danger'
        };
        return colors[status] || 'secondary';
    }
    
    updateTransform() {
        this.container.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
    }
    
    updateZoomDisplay() {
        const zoomLevel = document.getElementById('zoom-level');
        if (zoomLevel) {
            zoomLevel.textContent = `${Math.round(this.zoom * 100)}%`;
        }
    }
    
    saveAgentPosition(agentId) {
        const agent = this.agents.get(agentId);
        if (agent) {
            // Save position to server
            fetch('/api/agents/positions/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    agents: [{
                        id: agentId,
                        x: agent.position_x,
                        y: agent.position_y
                    }]
                })
            }).catch(error => {
                console.error('Error saving agent position:', error);
            });
        }
    }
    
    autoLayout() {
        const agents = Array.from(this.agents.values());
        const centerX = this.container.offsetWidth / 2;
        const centerY = this.container.offsetHeight / 2;
        const radius = Math.min(centerX, centerY) * 0.6;
        
        agents.forEach((agent, index) => {
            const angle = (index / agents.length) * 2 * Math.PI;
            const x = centerX + radius * Math.cos(angle) - 40;
            const y = centerY + radius * Math.sin(angle) - 40;
            
            this.updateAgentPosition(agent.id, x, y);
            this.saveAgentPosition(agent.id);
        });
    }
    
    resetView() {
        this.zoom = 1;
        this.panX = 0;
        this.panY = 0;
        this.updateTransform();
        this.updateZoomDisplay();
    }
    
    zoomIn() {
        this.zoom *= 1.2;
        this.zoom = Math.min(3, this.zoom);
        this.updateTransform();
        this.updateZoomDisplay();
    }
    
    zoomOut() {
        this.zoom *= 0.8;
        this.zoom = Math.max(0.1, this.zoom);
        this.updateTransform();
        this.updateZoomDisplay();
    }
    
    toggleConnections() {
        this.showConnections = !this.showConnections;
        this.updateConnections();
    }
}

// Global whiteboard instance
let whiteboard;

// Initialize whiteboard
function initWhiteboard(agents, connections, state) {
    whiteboard = new Whiteboard('whiteboard');
    
    // Add agents
    agents.forEach(agent => {
        whiteboard.addAgent(agent);
    });
    
    // Add connections
    connections.forEach(connection => {
        whiteboard.addConnection(connection);
    });
    
    // Restore state
    if (state) {
        whiteboard.zoom = state.zoom || 1;
        whiteboard.panX = state.center_x || 0;
        whiteboard.panY = state.center_y || 0;
        whiteboard.updateTransform();
        whiteboard.updateZoomDisplay();
    }
}

// Global functions for toolbar buttons
function zoomIn() {
    if (whiteboard) whiteboard.zoomIn();
}

function zoomOut() {
    if (whiteboard) whiteboard.zoomOut();
}

function resetView() {
    if (whiteboard) whiteboard.resetView();
}

function autoLayout() {
    if (whiteboard) whiteboard.autoLayout();
}

function toggleConnections() {
    if (whiteboard) whiteboard.toggleConnections();
}

function closeAgentInfo() {
    document.getElementById('agent-info-panel').classList.remove('open');
}

// Context menu functions
function showAgentInfo() {
    if (whiteboard && whiteboard.selectedAgent) {
        whiteboard.showAgentDetails(whiteboard.selectedAgent);
    }
    whiteboard.closeContextMenu();
}

function createConnection() {
    // TODO: Implement connection creation dialog
    console.log('Create connection for agent:', whiteboard.selectedAgent);
    whiteboard.closeContextMenu();
}

function editAgent() {
    if (whiteboard && whiteboard.selectedAgent) {
        window.location.href = `/agents/${whiteboard.selectedAgent}/`;
    }
    whiteboard.closeContextMenu();
}

function executeCommand(commandType) {
    if (whiteboard && whiteboard.selectedAgent) {
        // TODO: Implement command execution
        console.log('Execute command:', commandType, 'for agent:', whiteboard.selectedAgent);
    }
}

// Utility function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}