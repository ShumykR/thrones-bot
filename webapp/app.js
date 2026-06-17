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
    selectedCastle: null
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

function renderMap() {
    if (state.king) {
        els.kingName.textContent = state.king.name;
        els.kingBanner.style.display = 'block';
    } else {
        els.kingBanner.style.display = 'none';
    }

    els.castlesGrid.innerHTML = '';
    
    state.castles.forEach(castle => {
        const card = document.createElement('div');
        card.className = 'castle-card';
        card.style.setProperty('--owner-color', getColorForUser(castle.owner?.id));
        
        let ownerName = 'Вільний замок';
        if (castle.owner) {
            ownerName = state.me && castle.owner.id === state.me.user_id ? 'Ваш замок' : castle.owner.name;
        }

        card.innerHTML = `
            <span class="castle-icon">🏰</span>
            <div class="castle-name">${castle.name}</div>
            <div class="castle-owner" style="color: ${getColorForUser(castle.owner?.id)}">${ownerName}</div>
        `;
        
        card.addEventListener('click', () => openCastleModal(castle));
        els.castlesGrid.appendChild(card);
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
        
        if (isOwnedByMe || state.me.army_size < 100 || !castle.owner) {
            // Cannot attack own castle or unoccupied castle (per logic) or insufficient army
            els.mAttackSection.style.display = 'none';
        } else {
            els.mAttackSection.style.display = 'block';
            els.mSlider.max = state.me.army_size;
            els.mSlider.value = Math.min(100, state.me.army_size);
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
        
        // As a WebApp inside Telegram, we can prompt the user to send the command
        const command = `/attack @${castle.owner?.username || 'user'} ${castle.name} ${amount}`;
        tg.showAlert(`Штурм можна розпочати командою у чаті:\n\n${command}`);
        closeModal();
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
