/**
 * Global Simulation State
 * Main synchronisation object between the server and the UI.
 */
let state = {
    map: {},        // Stores location coordinates { "Name": [x, y] }
    characters: [], // List of active characters with their locations and status
    items: [],      // List of items with their locations
    events: [],     // chronological log of all simulation events
    turn: 0,        // Current simulation step
    running: false, // UI playback status
    initialized: false
};

// --- DOM Reference Registry ---
const startBtn = document.getElementById('startBtn');
const stepBtn = document.getElementById('stepBtn');
const resetBtn = document.getElementById('resetBtn');
const turnCount = document.getElementById('turnCount');
const mapGrid = document.getElementById('mapGrid');
const eventLog = document.getElementById('eventLog');


/** 
 * Design configuration for specific agents.
 */
const agentColors = {
    '小张': '#4CAF50', // Emerald Green
    '小红': '#E91E63'  // Rose Pink
};

/**
 * Design configuration for items.
 */
const itemColors = {
    '挂钟': '#FF9800',    // Orange
    '电视机': '#2196F3', // Blue
    '消毒液': '#9C27B0' // Purple
};

// Cell size configuration
const CELL_SIZE = 200;
const CELL_GAP = 10;


/**
 * Bootstraps the interface by fetching initial state and drawing the map.
 */
async function init() {
    await fetchState();
    renderMap();
    state.initialized = true;
}

/**
 * Synchronises the local 'state' object with the backend API.
 * Updates all relevant UI components upon success.
 */
async function fetchState() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();

        state.map = data.map || {};
        state.characters = data.characters || [];
        state.items = data.items || [];
        state.events = data.events || [];
        state.turn = data.turn || 0;

        updateUI();
    } catch (error) {
        console.error('API Error: Failed to synchronise simulation state.', error);
    }
}

/**
 * Triggers a single turn progression on the server.
 * Disables interaction during the request to prevent race conditions.
 */
async function stepSimulation() {
    try {
        stepBtn.disabled = true;
        const response = await fetch('/api/step', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            await fetchState();
        }

        // Handle termination state
        if (data.complete) {
            state.running = false;
            startBtn.textContent = '✓ Complete';
            startBtn.classList.add('finished');
            startBtn.disabled = true;
            stepBtn.disabled = true;
        } else {
            stepBtn.disabled = false;
        }
    } catch (error) {
        console.error('Execution Error: Step command failed.', error);
        stepBtn.disabled = false;
    }
}

/**
 * Resets the entire simulation to T-0.
 * Clears the localized history and visual logs.
 */
async function resetSimulation() {
    try {
        await fetch('/api/reset', { method: 'POST' });
        await fetchState();

        state.running = false;
        startBtn.textContent = '▶ Start';
        startBtn.classList.remove('finished');
        startBtn.disabled = false;
        stepBtn.disabled = true;
        resetBtn.disabled = true;

        // Wipe visual displays
        eventLog.innerHTML = '';
    } catch (error) {
        console.error('Reset Error: Failed to restore initial state.', error);
    }
}

/**
 * Dynamically constructs the interactive CSS grid based on the world map dimensions.
 */
function renderMap() {
    mapGrid.innerHTML = '';

    const locations = Object.entries(state.map);
    if (locations.length === 0) return;

    // Calculate bounding box for the grid
    let maxX = 0, maxY = 0;
    locations.forEach(([_, coords]) => {
        maxX = Math.max(maxX, coords[0]);
        maxY = Math.max(maxY, coords[1]);
    });

    // Set grid properties: fixed-size cells for consistency
    mapGrid.style.gridTemplateColumns = `repeat(${maxX + 1}, ${CELL_SIZE}px)`;
    mapGrid.style.gridTemplateRows = `repeat(${maxY + 1}, ${CELL_SIZE}px)`;

    const gridLayout = {};
    locations.forEach(([name, coords]) => {
        gridLayout[`${coords[0]},${coords[1]}`] = name;
    });

    // Generate cells: rendering top-to-bottom relative to Y coordinates
    for (let y = maxY; y >= 0; y--) {
        for (let x = 0; x <= maxX; x++) {
            const cell = document.createElement('div');
            cell.className = 'map-cell';

            const locationName = gridLayout[`${x},${y}`];
            if (locationName) {
                cell.innerHTML = `
                    <div class="cell-name">${locationName}</div>
                    <div class="cell-items" id="items-${x}-${y}"></div>
                    <div class="cell-agents" id="agents-${x}-${y}"></div>
                `;
            } else {
                cell.className += ' empty-cell';
                cell.innerHTML = '<div class="cell-name">-</div>';
            }

            mapGrid.appendChild(cell);
        }
    }


    // Persist gridMaxY for coordinate calculation
    state.gridMaxY = maxY;

    renderItems();
    updateAgentPositions();
}

/**
 * Renders items as labeled square tokens inside their location cells.
 * Items are positioned in the lower portion of the cell.
 */
function renderItems() {
    // Group items by location
    const itemsByLocation = {};
    state.items.forEach(item => {
        if (!itemsByLocation[item.location]) {
            itemsByLocation[item.location] = [];
        }
        itemsByLocation[item.location].push(item);
    });

    // Render items in each location
    for (const [locationName, items] of Object.entries(itemsByLocation)) {
        const coords = state.map[locationName];
        if (!coords) continue;

        const itemContainer = document.getElementById(`items-${coords[0]}-${coords[1]}`);
        if (!itemContainer) continue;

        itemContainer.innerHTML = '';

        items.forEach((item, index) => {
            const itemEl = document.createElement('div');
            itemEl.className = 'item-token';
            itemEl.style.backgroundColor = itemColors[item.name] || '#607D8B';
            itemEl.title = item.name;
            itemEl.textContent = item.name.charAt(0);
            itemContainer.appendChild(itemEl);
        });
    }
}

/**
 * Registry of persistent DOM elements for agents to enable smooth transitions.
 * Format: { "AgentName": DOMElement }
 */
const agentElements = {};

/**
 * Updates agent positions using absolute coordinates for smooth animation.
 * Handles multiple agents at the same location by offsetting them horizontally.
 */
function updateAgentPositions() {
    // 1. Mark all agents as initially unvisited to handle removals
    const activeAgents = new Set(state.characters.map(c => c.name));

    // 2. Remove DOM elements for agents that no longer exist
    for (const [name, element] of Object.entries(agentElements)) {
        if (!activeAgents.has(name)) {
            element.remove();
            delete agentElements[name];
        }
    }

    // 3. Group characters by location to handle overlaps
    const charactersByLocation = {};
    state.characters.forEach(char => {
        if (!charactersByLocation[char.location]) {
            charactersByLocation[char.location] = [];
        }
        charactersByLocation[char.location].push(char);
    });

    // 4. Update or Create DOM elements for current agents
    state.characters.forEach(char => {
        const coords = state.map[char.location];

        if (!coords) return; // Skip if location is unknown

        let agentEl = agentElements[char.name];

        // Create if doesn't exist
        if (!agentEl) {
            agentEl = document.createElement('div');
            agentEl.className = 'agent-wrapper';
            agentEl.innerHTML = `
                <div class="agent-token" style="background-color: ${agentColors[char.name] || '#7f8c8d'}">
                    ${char.name.charAt(0)}
                </div>
            `;
            mapGrid.appendChild(agentEl);
            agentElements[char.name] = agentEl;
        } else {
            // Fix for disappearing agents: Re-attach if mapGrid was wiped
            if (!mapGrid.contains(agentEl)) {
                mapGrid.appendChild(agentEl);
            }
        }

        // Update Token Visuals (in case color/status changes)
        const token = agentEl.querySelector('.agent-token');
        if (token) {
            token.style.backgroundColor = agentColors[char.name] || '#7f8c8d';
            token.title = `${char.name} (${char.status || 'IDLE'})`;
        }

        // Calculate Position using global constants
        // X = Padding + (x * (CellSize + Gap))
        // Y = Padding + ((MaxY - y) * (CellSize + Gap)) -> Because grid renders top-to-bottom

        // Ensure state.gridMaxY is available (set during renderMap)
        // If not available (racing with renderMap), calculate it locally
        let maxY = state.gridMaxY;
        if (typeof maxY === 'undefined') {
            const locations = Object.values(state.map);
            maxY = 0;
            locations.forEach(c => { maxY = Math.max(maxY, c[1]); });
        }

        const GRID_PADDING = 20;
        let cellLeft = GRID_PADDING + (coords[0] * (CELL_SIZE + CELL_GAP));
        const cellTop = GRID_PADDING + ((maxY - coords[1]) * (CELL_SIZE + CELL_GAP));

        // Horizontal offset for multiple agents
        const agentsAtLocation = charactersByLocation[char.location] || [];
        if (agentsAtLocation.length > 1) {
            const index = agentsAtLocation.findIndex(c => c.name === char.name);
            const count = agentsAtLocation.length;
            const spacing = 40;
            const offset = (index - (count - 1) / 2) * spacing;
            cellLeft += offset;
        }

        agentEl.style.left = `${cellLeft}px`;
        agentEl.style.top = `${cellTop}px`;
    });
}

/**
 * Orchestrates the full UI refresh cycle.
 */
function updateUI() {
    turnCount.textContent = state.turn;
    turnCount.textContent = state.turn;
    updateAgentPositions();
    renderEventLog();
}

/**
 * Renders the chronological event log into the side panel.
 * Supports different styling for Dialogue, Movement, and System events.
 */
function renderEventLog() {
    eventLog.innerHTML = '';

    state.events.forEach(event => {
        const item = document.createElement('div');
        const isDialogue = ['说话', '开始说话', '结束说话', '继续说话'].includes(event.action);
        const isMove = ['移动', '开始移动', '结束移动'].includes(event.action);

        item.className = `event-item ${isDialogue ? 'type-dialogue' : isMove ? 'type-move' : 'type-system'}`;

        const actor = event.actor || 'System';
        const args = event.args || {};

        // Simplified action description: just action name and optional target
        let actionDescription = event.action;

        // Add target for actions that have one
        if (isDialogue) {
            const target = args['目标'] || event.target_override;
            if (target) {
                actionDescription = `${event.action} -> ${target}`;
            }
            // For 说话 action, also show the message content
            const message = args['内容'];
            if (message && event.action === '说话') {
                actionDescription = `${event.action} -> ${target}: "${message}"`;
            }
        } else if (isMove) {
            const destination = event.new_location || args['方向'];
            if (destination) {
                actionDescription = `${event.action} -> ${destination}`;
            }
        } else if (event.action === '物品交互') {
            const target = args['目标'];
            if (target) {
                actionDescription = `${event.action} -> ${target}`;
            }
        }

        const innerThought = args['内心'] || '';

        item.innerHTML = `
            <div class="event-meta">
                <span class="actor-tag" style="color:${agentColors[actor] || '#666'}">${actor}</span>
            </div>
            <div class="event-body">${actionDescription}</div>
            ${innerThought ? `<div class="event-concept">💭 ${innerThought}</div>` : ''}
        `;

        eventLog.appendChild(item);
    });

    // Auto-scroll to the latest activity
    eventLog.scrollTop = eventLog.scrollHeight;
}


// --- User Interaction Hooks ---

startBtn.addEventListener('click', async () => {
    if (!state.running) {
        state.running = true;
        startBtn.textContent = '⏸ Running';
        startBtn.disabled = true; // For this demo, we auto-step once on start
        stepBtn.disabled = false;
        resetBtn.disabled = false;
        await stepSimulation();
    }
});

stepBtn.addEventListener('click', stepSimulation);
resetBtn.addEventListener('click', resetSimulation);

// Global entry point
document.addEventListener('DOMContentLoaded', init);
