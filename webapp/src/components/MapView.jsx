import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Sword, X, Coins } from 'lucide-react';
import MapSvg from './MapSvg';

const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6'];

function getColorForUser(userId) {
  if (!userId) return '#334155';
  return colors[userId % colors.length];
}

export default function MapView({ state, me, onAttack, tg }) {
  const [selectedCastle, setSelectedCastle] = useState(null);

  return (
    <div className="map-container">
      <MapSvg 
        state={state} 
        getColorForUser={getColorForUser}
        onCastleClick={(castle) => {
          setSelectedCastle(castle);
          tg?.HapticFeedback?.impactOccurred('light');
        }} 
      />

      <AnimatePresence>
        {selectedCastle && (
          <CastleModal 
            castle={selectedCastle} 
            me={me} 
            config={state.config}
            onClose={() => setSelectedCastle(null)}
            onAttack={(amount) => {
              onAttack(selectedCastle.id, amount);
              setSelectedCastle(null);
            }}
            tg={tg}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function CastleModal({ castle, me, config, onClose, onAttack, tg }) {
  const [attackAmount, setAttackAmount] = useState(config.min_attack_army);
  const color = getColorForUser(castle.owner?.id);
  
  const isMine = castle.owner && me && castle.owner.id === me.user_id;
  const canAttack = me && !isMine && castle.owner && me.army_size >= config.min_attack_army;

  return (
    <>
      <motion.div 
        className="loading-overlay"
        style={{ background: 'rgba(0,0,0,0.5)', zIndex: 99 }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div 
        className="bottom-panel"
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      >
        <div className="panel-header">
          <div className="panel-title">{castle.name}</div>
          <button className="close-button" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        
        <div style={{ marginBottom: 20 }}>
          <span style={{ color: 'var(--hint-color)', fontSize: 14 }}>Власник: </span>
          <strong style={{ color }}>{castle.owner ? castle.owner.name : 'Вільний'}</strong>
        </div>

        <div className="stats-grid">
          <div className="stat-box">
            <Shield className="stat-icon" size={24} />
            <div className="stat-content">
              <span className="stat-label">Гарнізон</span>
              <span className="stat-value">{castle.garrison}</span>
            </div>
          </div>
          <div className="stat-box">
            <Coins className="stat-icon" size={24} />
            <div className="stat-content">
              <span className="stat-label">Прибуток</span>
              <span className="stat-value">+{castle.army_per_hour} / год</span>
            </div>
          </div>
        </div>

        {canAttack && (
          <div className="attack-section">
            <h3 className="section-title">Атакувати Замок</h3>
            <div className="slider-container">
              <div className="slider-info">
                <span>Військ для атаки:</span>
                <span style={{ fontWeight: 'bold', color: 'var(--button-color)' }}>{attackAmount}</span>
              </div>
              <input 
                type="range" 
                min={config.min_attack_army} 
                max={me.army_size} 
                value={attackAmount}
                onChange={(e) => setAttackAmount(parseInt(e.target.value))}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--hint-color)', marginTop: 4 }}>
                <span>{config.min_attack_army}</span>
                <span>{me.army_size}</span>
              </div>
            </div>
            
            <button 
              className="action-button destructive"
              onClick={() => {
                tg?.showConfirm(`Відправити ${attackAmount} воїнів на штурм замку ${castle.name}?`, (confirm) => {
                  if (confirm) onAttack(attackAmount);
                });
              }}
            >
              <Sword size={20} />
              Штурм
            </button>
          </div>
        )}
        
        {!canAttack && me && !isMine && !castle.owner && (
           <div style={{ textAlign: 'center', color: 'var(--hint-color)', marginTop: 20 }}>
             Цей замок нічийний. Його потрібно зайняти.
           </div>
        )}
      </motion.div>
    </>
  );
}
