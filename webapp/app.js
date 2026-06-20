// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// DOM Elements
const els = {
    loading: document.getElementById('loading-overlay'),
    userName: document.getElementById('user-name'),
    userRole: document.getElementById('user-role'),
    armySize: document.getElementById('army-size'),
    castlesCount: document.getElementById('castles-count'),
    castlesGrid: document.getElementById('castles-grid'),
    kingBanner: document.getElementById('king-banner'),
    kingName: document.getElementById('king-name'),
    
    // Modal
    modal: document.getElementById('castle-modal'),
    modalClose: document.getElementById('close-modal'),
    mCastleName: document.getElementById('modal-castle-name'),
    mOwner: document.getElementById('modal-owner'),
    mGarrison: document.getElementById('modal-garrison'),
    mIncome: document.getElementById('modal-income'),
    mAttackSection: document.getElementById('attack-section'),
    mSlider: document.getElementById('army-slider'),
    mArmyVal: document.getElementById('army-val'),
    mBtnAttack: document.getElementById('btn-attack')
};

// State
let state = {
    me: null,
    castles: [],
    king: null,
    selectedCastle: null,
    config: { min_attack_army: 100 }
};

// Utilities
const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6'];
function getColorForUser(userId) {
    if (!userId) return '#334155'; // Unowned
    return colors[userId % colors.length];
}

// Ensure initData is ready or mock for dev
const initData = tg.initData || '';

async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = {
        'Authorization': `Bearer ${initData}`
    };
    if (body) {
        headers['Content-Type'] = 'application/json';
    }
    
    try {
        const res = await fetch(endpoint, {
            method,
            headers,
            body: body ? JSON.stringify(body) : null
        });
        if (!res.ok) throw new Error(`API Error: ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error(e);
        if (initData) tg.showAlert("Сталася помилка з'єднання з Воронячою поштою.");
        return null;
    }
}

// Render logic
function renderHeader() {
    if (!state.me) return;
    
    els.userName.textContent = state.me.first_name;
    const roleIcons = {
        'king': 'Король',
        'lord': 'Лорд',
        'puppet': 'Маріонетка'
    };
    els.userRole.textContent = roleIcons[state.me.role] || state.me.role;
    els.armySize.textContent = state.me.army_size;
    els.castlesCount.textContent = state.me.castles_count;
}

const castleCoords = {
    "Стіна": { top: "5%", left: "50%" },
    "Чорний Замок": { top: "7%", left: "50%" },
    "Вінтерфелл": { top: "20%", left: "45%" },
    "Залізні Острови": { top: "45%", left: "20%" },
    "Близнята": { top: "45%", left: "40%" },
    "Лорд-Перетин": { top: "46%", left: "42%" },
    "Арренська Вежа": { top: "48%", left: "65%" },
    "Харренгол": { top: "55%", left: "48%" },
    "Кастерлі Рок": { top: "60%", left: "25%" },
    "Висад": { top: "68%", left: "60%" },
    "Червоний Замок": { top: "69%", left: "61%" },
    "Драконячий Камінь": { top: "62%", left: "70%" },
    "Хайгарден": { top: "75%", left: "30%" },
    "Штормовий Кінець": { top: "78%", left: "65%" },
    "Дорнійська Фортеця": { top: "90%", left: "70%" },
    "Уотергарден": { top: "92%", left: "72%" }
};

function renderMap() {
    if (state.king) {
        document.getElementById('king-name').textContent = state.king.name;
        document.getElementById('throne-container').style.display = 'block';
        
        // Avatar logic
        const kingAvatar = document.getElementById('king-avatar');
        if (state.me && state.king.id === state.me.user_id && tg.initDataUnsafe?.user?.photo_url) {
            // King is the current user
            kingAvatar.src = tg.initDataUnsafe.user.photo_url;
        } else {
            // Fallback: generate initials avatar for the king
            kingAvatar.src = `https://api.dicebear.com/7.x/initials/svg?seed=${state.king.name}&backgroundColor=1a1d24&textColor=fbbf24`;
        }
    } else {
        document.getElementById('throne-container').style.display = 'none';
    }

    // Keep the map image, remove old dots
    const container = document.getElementById('map-container');
    const existingDots = container.querySelectorAll('.castle-dot');
    existingDots.forEach(dot => dot.remove());
    
    // To track unique owners for the legend
    const ownersMap = new Map();
    
    state.castles.forEach(castle => {
        const dot = document.createElement('div');
        dot.className = 'castle-dot';
        const color = getColorForUser(castle.owner?.id);
        dot.style.setProperty('--owner-color', color);
        
        if (castle.owner) {
            ownersMap.set(castle.owner.id, { name: castle.owner.name, color: color });
        }

        // Use coordinates if available, else random fallback
        const coords = castleCoords[castle.name];
        if (coords) {
            dot.style.top = coords.top;
            dot.style.left = coords.left;
        } else {
            dot.style.top = Math.random() * 80 + 10 + '%';
            dot.style.left = Math.random() * 80 + 10 + '%';
        }

        // Add label
        const label = document.createElement('div');
        label.className = 'castle-dot-label';
        label.textContent = castle.name;
        dot.appendChild(label);
        
        dot.addEventListener('click', (e) => {
            e.stopPropagation(); // prevent map click
            openCastleModal(castle);
        });
        container.appendChild(dot);
    });
    
    // Render Legend
    const legendContainer = document.getElementById('legend-items');
    legendContainer.innerHTML = '';
    
    if (ownersMap.size === 0) {
        legendContainer.innerHTML = '<div style="color: #94a3b8; text-align: center;">Всі замки вільні</div>';
    } else {
        ownersMap.forEach((data, id) => {
            const item = document.createElement('div');
            item.className = 'legend-item';
            const isMe = state.me && state.me.user_id === id;
            item.innerHTML = `
                <div class="legend-color" style="background-color: ${data.color}"></div>
                <span>${data.name} ${isMe ? '(Ви)' : ''}</span>
            `;
            legendContainer.appendChild(item);
        });
    }

    // Dev tool: click on map to get coordinates
    const mapImg = document.getElementById('westeros-img');
    mapImg.addEventListener('click', (e) => {
        const rect = mapImg.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1);
        const y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1);
        tg.showAlert(`Координати: top: "${y}%", left: "${x}%"`);
    });
}

function openCastleModal(castle) {
    state.selectedCastle = castle;
    
    els.mCastleName.textContent = castle.name;
    els.mOwner.textContent = castle.owner ? castle.owner.name : 'Вільний';
    els.mOwner.style.color = getColorForUser(castle.owner?.id);
    
    els.mGarrison.textContent = castle.garrison;
    els.mIncome.textContent = castle.army_per_hour;
    
    // Check if attack is possible
    if (!state.me) {
        els.mAttackSection.style.display = 'none';
    } else {
        const isOwnedByMe = castle.owner && castle.owner.id === state.me.user_id;
        
        if (isOwnedByMe || state.me.army_size < state.config.min_attack_army || !castle.owner) {
            // Cannot attack own castle or unoccupied castle (per logic) or insufficient army
            els.mAttackSection.style.display = 'none';
        } else {
            els.mAttackSection.style.display = 'block';
            els.mSlider.min = state.config.min_attack_army;
            els.mSlider.max = state.me.army_size;
            els.mSlider.value = Math.min(state.config.min_attack_army, state.me.army_size);
            els.mArmyVal.textContent = els.mSlider.value;
        }
    }
    
    els.modal.classList.add('active');
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

function closeModal() {
    els.modal.classList.remove('active');
    state.selectedCastle = null;
}

// Event Listeners
els.modalClose.addEventListener('click', closeModal);
els.modal.addEventListener('click', (e) => {
    if (e.target === els.modal) closeModal();
});

els.mSlider.addEventListener('input', (e) => {
    els.mArmyVal.textContent = e.target.value;
});

els.mBtnAttack.addEventListener('click', () => {
    const amount = parseInt(els.mSlider.value);
    const castle = state.selectedCastle;
    
    if (!castle) return;
    
    tg.showConfirm(`Відправити ${amount} воїнів на штурм замку ${castle.name}?`, (confirm) => {
        if (!confirm) return;
        
        if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
        
        apiFetch('/api/attack', 'POST', {
            castle_id: castle.id,
            amount: amount
        }).then(res => {
            if (res && res.success) {
                tg.showAlert("Війська вирушили на штурм!");
                // Optimistically deduct army
                state.me.army_size -= amount;
                renderHeader();
            } else if (res && res.error) {
                tg.showAlert(`Помилка: ${res.error}`);
            }
            closeModal();
        });
    });
});

// Init
async function init() {
    // Notify telegram we are ready
    tg.ready();
    
    // Fetch data
    if (initData) {
        const [meRes, stateRes] = await Promise.all([
            apiFetch('/api/me'),
            apiFetch('/api/state')
        ]);
        
        if (meRes && !meRes.error) state.me = meRes;
        if (stateRes && !stateRes.error) {
            state.castles = stateRes.castles;
            state.king = stateRes.king;
            if (stateRes.config) {
                state.config = stateRes.config;
            }
        }
    } else {
        // Mock data for browser dev
        state.me = { user_id: 1, first_name: 'Jon', role: 'lord', army_size: 500, castles_count: 1 };
        state.king = { id: 2, name: 'Cersei' };
        state.castles = [
            { id: 1, name: 'Вінтерфелл', garrison: 100, army_per_hour: 10, owner: { id: 1, name: 'Jon' } },
            { id: 2, name: 'Кастерлі Рок', garrison: 200, army_per_hour: 10, owner: { id: 2, name: 'Cersei', username: 'cersei' } },
            { id: 3, name: 'Драконячий Камінь', garrison: 0, army_per_hour: 10, owner: null }
        ];
    }
    
    renderHeader();
    renderMap();
    
    els.loading.style.opacity = '0';
    setTimeout(() => els.loading.style.display = 'none', 500);
}

init();
