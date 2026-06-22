import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Map, User as UserIcon, Sword, Shield, Crown } from 'lucide-react';
import MapView from './components/MapView';
import ProfileView from './components/ProfileView';
import ThroneView from './components/ThroneView';

// Initialize Telegram WebApp
const tg = window.Telegram?.WebApp;
const initData = tg?.initData || '';

export default function App() {
  const [activeTab, setActiveTab] = useState('map');
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState(null);
  const [gameState, setGameState] = useState({ castles: [], king: null, users: [], config: { min_attack_army: 100 } });

  // Fetch data
  const fetchData = async () => {
    try {
      const headers = { 'Authorization': `Bearer ${initData}` };
      
      // Use real API if initData exists, else mock for dev
      if (initData) {
        const [meRes, stateRes] = await Promise.all([
          fetch('/api/me', { headers }).then(r => r.json()),
          fetch('/api/state', { headers }).then(r => r.json())
        ]);
        
        if (!meRes.error) setMe(meRes);
        if (!stateRes.error) setGameState(stateRes);
      } else {
        // Mock data
        setTimeout(() => {
          setMe({ user_id: 1, first_name: 'Jon Snow', role: 'lord', army_size: 1500, castles_count: 1 });
          setGameState({
            king: { id: 2, name: 'Cersei Lannister', role: 'king' },
            users: [
              { id: 1, name: 'Jon Snow', role: 'lord' },
              { id: 2, name: 'Cersei Lannister', role: 'king' }
            ],
            castles: [
              { id: 1, name: 'Північ', garrison: 500, army_per_hour: 20, owner: { id: 1, name: 'Jon Snow' } },
              { id: 2, name: 'Західні Землі', garrison: 1200, army_per_hour: 50, owner: { id: 2, name: 'Cersei Lannister' } },
              { id: 3, name: 'Драконячий Камінь', garrison: 0, army_per_hour: 15, owner: null }
            ],
            config: { min_attack_army: 100 }
          });
          setLoading(false);
        }, 1000);
        return;
      }
    } catch (e) {
      console.error("Error fetching data:", e);
      if (tg) tg.showAlert("Помилка з'єднання з сервером.");
    }
    setLoading(false);
  };

  useEffect(() => {
    if (tg) {
      tg.expand();
      tg.ready();
    }
    fetchData();
  }, []);

  const handleAttack = async (castleId, amount) => {
    if (!initData) {
      alert(`Attacking castle ${castleId} with ${amount}`);
      return;
    }
    
    try {
      const res = await fetch('/api/attack', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${initData}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ castle_id: castleId, amount })
      }).then(r => r.json());
      
      if (res.success) {
        tg?.showAlert("Війська вирушили на штурм!");
        fetchData();
      } else {
        tg?.showAlert(`Помилка: ${res.error}`);
      }
    } catch (e) {
      tg?.showAlert("Помилка відправки наказу.");
    }
  };

  if (loading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
      </div>
    );
  }

  if (!me) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', padding: 20, textAlign: 'center', color: '#fff' }}>
        <h2>Помилка авторизації</h2>
        <p style={{ color: 'var(--hint-color)', marginTop: 10 }}>Вашого персонажа не знайдено в базі даних. Можливо, базу було очищено.</p>
        <p style={{ marginTop: 10 }}>Будь ласка, відправте команду <strong>/start</strong> у боті, щоб створити лорда.</p>
        <button 
          className="action-button" 
          style={{ marginTop: 20 }}
          onClick={() => tg?.close()}
        >
          Закрити
        </button>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="content-area">
        <AnimatePresence mode="wait">
          {activeTab === 'map' && (
            <motion.div
              key="map"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              style={{ height: '100%' }}
            >
              <MapView state={gameState} me={me} onAttack={handleAttack} tg={tg} reloadData={fetchData} />
            </motion.div>
          )}

          {activeTab === 'throne' && (
            <motion.div
              key="throne"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              style={{ position: 'absolute', width: '100%', height: '100%' }}
            >
              <ThroneView state={gameState} me={me} tg={tg} reloadData={fetchData} />
            </motion.div>
          )}
          
          {activeTab === 'profile' && (
            <motion.div
              key="profile"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              style={{ position: 'absolute', width: '100%', height: '100%' }}
            >
              <ProfileView me={me} state={gameState} tg={tg} reloadData={fetchData} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="nav-bar">
        <div 
          className={`nav-item ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('map');
            tg?.HapticFeedback?.selectionChanged();
          }}
        >
          <Map />
          <span>Карта</span>
        </div>
        <div 
          className={`nav-item ${activeTab === 'throne' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('throne');
            tg?.HapticFeedback?.selectionChanged();
          }}
        >
          <Crown />
          <span>Трон</span>
        </div>
        <div 
          className={`nav-item ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('profile');
            tg?.HapticFeedback?.selectionChanged();
          }}
        >
          <UserIcon />
          <span>Профіль</span>
        </div>
      </div>
    </div>
  );
}
