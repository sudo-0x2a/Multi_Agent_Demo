// State
let state = {
    map: {},
    characters: [],
    events: [],
    turn: 0,
    running: false,
    initialized: false
};

// DOM Elements
const startBtn = document.getElementById('startBtn');
const stepBtn = document.getElementById('stepBtn');
const resetBtn = document.getElementById('resetBtn');
const turnCount = document.getElementById('turnCount');
const mapGrid = document.getElementById('mapGrid');
const eventLog = document.getElementById('eventLog');


// Agent colors
const agentColors = {
    '小张': '#4CAF50',
    '小红': '#E91E63'
};

// Initialize
async function init() {
    await fetchState();
    renderMap();
    state.initialized = true;
}

// Fetch current state from API
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
        console.error('Failed to fetch state:', error);
    }
}

// Step simulation
async function stepSimulation() {
    try {
        stepBtn.disabled = true;
        const response = await fetch('/api/step', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            await fetchState();
        }

        if (data.complete) {
            state.running = false;
            startBtn.textContent = '✓ Complete';
            startBtn.disabled = true;
            stepBtn.disabled = true;
        } else {
            stepBtn.disabled = false;
        }
    } catch (error) {
        console.error('Step failed:', error);
        stepBtn.disabled = false;
    }
}

// Reset simulation
async function resetSimulation() {
    try {
        await fetch('/api/reset', { method: 'POST' });
        await fetchState();
        state.running = false;
        startBtn.textContent = '▶ Start';
        startBtn.disabled = false;
        stepBtn.disabled = true;
        resetBtn.disabled = true;
        eventLog.innerHTML = '';
        bubbleContainer.innerHTML = '';
    } catch (error) {
        console.error('Reset failed:', error);
    }
}

// Render the map grid
function renderMap() {
    mapGrid.innerHTML = '';

    // Calculate grid dimensions
    const locations = Object.entries(state.map);
    if (locations.length === 0) return;

    let maxX = 0, maxY = 0;
    locations.forEach(([name, coords]) => {
        maxX = Math.max(maxX, coords[0]);
        maxY = Math.max(maxY, coords[1]);
    });

    mapGrid.style.gridTemplateColumns = `repeat(${maxX + 1}, 140px)`;
    mapGrid.style.gridTemplateRows = `repeat(${maxY + 1}, 140px)`;

    // Create grid cells
    const grid = {};
    locations.forEach(([name, coords]) => {
        grid[`${coords[0]},${coords[1]}`] = name;
    });

    // Render cells (row by row, top to bottom = high Y to low Y)
    for (let y = maxY; y >= 0; y--) {
        for (let x = 0; x <= maxX; x++) {
            const cell = document.createElement('div');
            cell.className = 'map-cell';
            cell.dataset.x = x;
            cell.dataset.y = y;

            const locationName = grid[`${x},${y}`];
            if (locationName) {
                cell.innerHTML = `
                    <div class="cell-name">${locationName}</div>
                    <div class="cell-agents" id="agents-${x}-${y}"></div>
                `;
            } else {
                cell.style.opacity = '0.3';
                cell.innerHTML = '<div class="cell-name">-</div>';
            }

            mapGrid.appendChild(cell);
        }
    }

    updateAgentPositions();
}

// Update agent positions on map
function updateAgentPositions() {
    // Clear all agent containers
    document.querySelectorAll('.cell-agents').forEach(el => el.innerHTML = '');

    state.characters.forEach(char => {
        const coords = state.map[char.location];
        if (coords) {
            const container = document.getElementById(`agents-${coords[0]}-${coords[1]}`);
            if (container) {
                const token = document.createElement('div');
                token.className = 'agent-token';
                token.style.background = agentColors[char.name] || '#666';
                token.textContent = char.name.charAt(0);
                token.title = char.name;
                container.appendChild(token);
            }
        }
    });
}

// Update UI elements
function updateUI() {
    turnCount.textContent = state.turn;
    updateAgentPositions();
    renderEvents();
}

// Render event log
function renderEvents() {
    eventLog.innerHTML = '';

    state.events.forEach(event => {
        const item = document.createElement('div');
        item.className = `event-item ${event.action === '说话' ? 'dialogue' : event.action === '移动' ? 'move' : ''}`;

        const actor = event.actor || 'System';
        const args = event.args || {};

        let content = '';
        if (event.action === '说话') {
            const target = args['目标'] || '';
            const text = args['内容'] || '';
            content = `对 ${target} 说: "${text}"`;
        } else if (event.action === '移动') {
            const newLoc = event.new_location || args['方向'] || '';
            content = `移动 → ${newLoc}`;
        } else if (event.action === '查看地图') {
            content = '查看了地图';
        } else if (event.action === '保持沉默') {
            content = '保持沉默';
        } else {
            content = event.action;
        }

        const inner = args['内心'] || '';

        item.innerHTML = `
            <div class="event-actor">${actor}</div>
            <div class="event-content">${content}</div>
            ${inner ? `<div class="event-thought">(${inner})</div>` : ''}
        `;

        eventLog.appendChild(item);
    });

    // Scroll to bottom
    eventLog.scrollTop = eventLog.scrollHeight;
}



// Event Listeners
startBtn.addEventListener('click', async () => {
    if (!state.running) {
        state.running = true;
        startBtn.textContent = '⏸ Running';
        stepBtn.disabled = false;
        resetBtn.disabled = false;
        await stepSimulation();
    }
});

stepBtn.addEventListener('click', stepSimulation);
resetBtn.addEventListener('click', resetSimulation);

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
