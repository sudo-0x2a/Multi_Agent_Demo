/**
 * Global Simulation State
 * Main synchronisation object between the server and the UI.
 */
let state = {
    map: {},        // Stores location coordinates { "Name": [x, y] }
    characters: [], // List of active characters with their locations and status
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
    mapGrid.style.gridTemplateColumns = `repeat(${maxX + 1}, 140px)`;
    mapGrid.style.gridTemplateRows = `repeat(${maxY + 1}, 140px)`;

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
                    <div class="cell-agents" id="agents-${x}-${y}"></div>
                `;
            } else {
                cell.className += ' empty-cell';
                cell.innerHTML = '<div class="cell-name">-</div>';
            }

            mapGrid.appendChild(cell);
        }
    }

    updateAgentTokens();
}

/**
 * Places character icons in their respective grid cells based on current spatial data.
 */
function updateAgentTokens() {
    // Purge current tokens
    document.querySelectorAll('.cell-agents').forEach(el => el.innerHTML = '');

    state.characters.forEach(char => {
        const coords = state.map[char.location];
        if (coords) {
            const container = document.getElementById(`agents-${coords[0]}-${coords[1]}`);
            if (container) {
                const token = document.createElement('div');
                token.className = 'agent-token';
                token.style.backgroundColor = agentColors[char.name] || '#7f8c8d';
                token.textContent = char.name.charAt(0);
                token.title = `${char.name} (${char.status || 'IDLE'})`;
                container.appendChild(token);
            }
        }
    });
}

/**
 * Orchestrates the full UI refresh cycle.
 */
function updateUI() {
    turnCount.textContent = state.turn;
    updateAgentTokens();
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

        let actionDescription = '';
        if (isDialogue) {
            const target = args['目标'] || event.target_override || 'Unknown';
            const message = args['内容'] || '';

            if (event.action === '开始说话') {
                actionDescription = `Initiated dialogue with <b>${target}</b>`;
            } else if (event.action === '结束说话') {
                actionDescription = `Concluded dialogue with <b>${target}</b>`;
            } else {
                actionDescription = `To <b>${target}</b>: "${message}"`;
            }
        } else if (isMove) {
            const destination = event.new_location || args['方向'] || 'Unknown';
            if (event.action === '开始移动') {
                actionDescription = `Preparing for departure...`;
            } else if (event.action === '结束移动') {
                actionDescription = `Halted movement.`;
            } else {
                actionDescription = `Traveling to <b>${destination}</b>`;
            }
        } else {
            actionDescription = event.action === '查看地图' ? 'Browsed world map.' : event.action;
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
