import { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Sword, X, Coins, ArrowRightLeft, Crown, AlertTriangle } from 'lucide-react';
import MapSvg from './MapSvg';

const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6'];

function getColorForUser(userId) {
  if (!userId) return '#334155';
  return colors[userId % colors.length];
}

export default function MapView({ state, me, onAttack, tg, reloadData }) {
  const [selectedCastle, setSelectedCastle] = useState(null);
  const [mapMode, setMapMode] = useState('default'); // 'default', 'alliances', 'opinion', 'war'
  const [scoutedCastles, setScoutedCastles] = useState({});

  // Determine active modes
  const hasConspiracy = !!state.conspiracy;
  
  // Custom color getter based on mapMode
  const getDynamicColor = (userId) => {
    if (!userId) return '#334155';
    
    // King's domains are always golden
    if (state.king && userId === state.king.id) {
      return '#fbbf24';
    }
    
    if (mapMode === 'default') {
      return getColorForUser(userId);
    }
    
    const user = state.users.find(u => u.id === userId);
    if (!user) return '#334155';

    if (mapMode === 'alliances') {
      if (user.alliance_id) return colors[user.alliance_id % colors.length];
      return '#334155'; // Not in alliance
    }

    if (mapMode === 'opinion') {
      if (user.king_opinion === 'good') return '#10b981'; // Green
      if (user.king_opinion === 'bad') return '#ef4444'; // Red
      return '#64748b'; // Neutral
    }

    if (mapMode === 'war') {
      if (!hasConspiracy) return '#334155';
      if (state.conspiracy.rebels.includes(userId.toString())) return '#ef4444'; // Rebel
      if (state.conspiracy.loyalists.includes(userId.toString())) return '#3b82f6'; // Loyalist
      return '#64748b'; // Neutral
    }

    return getColorForUser(userId);
  };

  return (
    <div className="map-container">
      {/* Modes Switcher */}
      <div className="map-modes-panel">
        <select value={mapMode} onChange={(e) => setMapMode(e.target.value)} className="mode-select">
          <option value="default">👑 Власники</option>
          <option value="alliances">🛡 Альянси</option>
          <option value="opinion">💭 Думка про Короля</option>
          {hasConspiracy && <option value="war">⚔️ Війна за Трон</option>}
        </select>
      </div>

      <MapSvg 
        state={state} 
        getColorForUser={getDynamicColor}
        onCastleClick={(castle) => {
          setSelectedCastle(castle);
          tg?.HapticFeedback?.impactOccurred('light');
        }} 
      />

      {/* Legend */}
      <div className="map-legend">
        {mapMode === 'default' && (
          <>
            <div className="legend-item"><span className="legend-color" style={{background: '#334155'}}></span>Вільні землі</div>
            {Array.from(new Set(state.castles.filter(c => c.owner).map(c => c.owner.id))).map(ownerId => {
              const user = state.users.find(u => u.id === ownerId);
              if (!user) return null;
              return (
                <div key={ownerId} className="legend-item">
                  <span className="legend-color" style={{background: getDynamicColor(ownerId)}}></span>
                  {user.name}
                </div>
              );
            })}
          </>
        )}
        {mapMode === 'alliances' && (
          <>
            <div className="legend-item"><span className="legend-color" style={{background: '#334155'}}></span>Без альянсу</div>
            {state.alliances?.map(alliance => (
              <div key={alliance.id} className="legend-item">
                <span className="legend-color" style={{background: colors[alliance.id % colors.length]}}></span>
                {alliance.name}
              </div>
            ))}
          </>
        )}
        {mapMode === 'opinion' && (
          <>
            <div className="legend-item"><span className="legend-color" style={{background: '#10b981'}}></span>Лоялісти (Добре)</div>
            <div className="legend-item"><span className="legend-color" style={{background: '#ef4444'}}></span>Бунтівники (Погано)</div>
            <div className="legend-item"><span className="legend-color" style={{background: '#64748b'}}></span>Нейтральні</div>
          </>
        )}
        {mapMode === 'war' && hasConspiracy && (
          <>
            <div className="legend-item"><span className="legend-color" style={{background: '#ef4444'}}></span>Повстанці</div>
            <div className="legend-item"><span className="legend-color" style={{background: '#3b82f6'}}></span>Лоялісти</div>
            <div className="legend-item"><span className="legend-color" style={{background: '#64748b'}}></span>Нейтральні</div>
          </>
        )}
      </div>

      <AnimatePresence>
        {selectedCastle && (
          <CastleModal 
            castle={selectedCastle} 
            state={state}
            me={me} 
            config={state.config}
            onClose={() => setSelectedCastle(null)}
            onAttack={(amount) => {
              onAttack(selectedCastle.id, amount);
              setSelectedCastle(null);
            }}
            tg={tg}
            scoutedCastles={scoutedCastles}
            setScoutedCastles={setScoutedCastles}
            reloadData={reloadData}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function CastleModal({ castle, state, me, config, onClose, onAttack, tg, scoutedCastles, setScoutedCastles, reloadData }) {
  const [attackAmount, setAttackAmount] = useState(state.config?.min_attack_army || 100);
  const [garrisonTransfer, setGarrisonTransfer] = useState(0); 
  const [scoutAmount, setScoutAmount] = useState(10);
  const [showConspiracySlider, setShowConspiracySlider] = useState(false);
  const minConspiracyAmount = Math.ceil((me?.army_size || 0) * 0.70);
  const [conspiracyAmount, setConspiracyAmount] = useState(minConspiracyAmount);
  
  useEffect(() => {
    if (castle) {
      setAttackAmount(state.config?.min_attack_army || 100);
      setGarrisonTransfer(0);
      setScoutAmount(10);
    }
  }, [castle, state.config]);

  if (!castle) return null;

  const isMine = castle.owner?.id === me.user_id;
  const isScouted = isMine || scoutedCastles[castle.id] !== undefined || (state.scouted_castles && state.scouted_castles[castle.id] !== undefined);
  const displayGarrison = isScouted ? (isMine ? castle.garrison : (scoutedCastles[castle.id] ?? state.scouted_castles?.[castle.id]?.garrison)) : "???";
  const isKing = state.king && me && state.king.id === me.user_id;
  const canAttack = !isMine && me.army_size >= (state.config?.min_attack_army || 100) && castle.name !== "Королівські Землі";

  const isCrownlands = castle.name === "Королівські Землі";
  
  let loyalistsSum = 0;
  if (isCrownlands) {
    loyalistsSum = state.users?.filter(u => u.king_opinion === 'good').reduce((sum, u) => sum + u.army_size, 0) || 0;
  }

  const handleGarrisonChange = async () => {
    if (garrisonTransfer === 0) return;
    try {
      const res = await fetch('/api/garrison', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tg?.initData}`
        },
        body: JSON.stringify({
          castle_id: castle.id,
          amount: garrisonTransfer
        })
      }).then(r => r.json());
      tg?.showAlert(res.message || res.error);
      if (res.message) {
        if (reloadData) await reloadData();
        onClose(); // Close to refresh data
      }
    } catch (e) {
      tg?.showAlert("Помилка з'єднання");
    }
  };

  const handleScout = async () => {
    if (scoutAmount <= 0) return;
    try {
      const res = await fetch('/api/scout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tg?.initData}`
        },
        body: JSON.stringify({
          castle_id: castle.id,
          amount: scoutAmount
        })
      }).then(r => r.json());
      
      tg?.showAlert(res.message || res.error);
      if (res.success && res.garrison !== undefined) {
        setScoutedCastles(prev => ({ ...prev, [castle.id]: res.garrison }));
      }
      if (reloadData) await reloadData();
    } catch (e) {
      tg?.showAlert("Помилка з'єднання під час розвідки");
    }
  };

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
        style={{ zIndex: 100, maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="panel-header">
          <div className="panel-title">{castle.name}</div>
          <button className="close-button" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        
        <div style={{ marginBottom: 20 }}>
          <span style={{ color: 'var(--hint-color)', fontSize: 14 }}>Власник: </span>
          <strong style={{ color: castle.owner ? '#fff' : 'var(--hint-color)' }}>{castle.owner ? castle.owner.name : 'Вільний'}</strong>
        </div>

        <div className="stats-grid">
          <div className="stat-box">
            <Shield className="stat-icon" size={24} />
            <div className="stat-content">
              <span className="stat-label">{isCrownlands ? 'Армія Короля' : 'Гарнізон'}</span>
              <span className="stat-value">
                {isCrownlands ? (state.king ? state.users?.find(u => u.id === state.king.id)?.army_size || 0 : 0) : displayGarrison}
              </span>
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

        {/* Garrison Management for Owner */}
        {isMine && !isCrownlands && (
          <div className="attack-section" style={{ background: 'rgba(255,255,255,0.05)', padding: 16, borderRadius: 12, marginBottom: 16 }}>
            <h3 className="section-title" style={{ fontSize: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <ArrowRightLeft size={18} /> Керування гарнізоном
            </h3>
            <p style={{ fontSize: 13, color: 'var(--hint-color)', marginBottom: 12 }}>
              Переміщення військ між вашою армією та гарнізоном.
            </p>
            
            <div className="slider-container">
              <div className="slider-info">
                <span>Забрати: <span style={{color: '#ef4444'}}>{garrisonTransfer < 0 ? Math.abs(garrisonTransfer) : 0}</span></span>
                <span>Додати: <span style={{color: '#10b981'}}>{garrisonTransfer > 0 ? garrisonTransfer : 0}</span></span>
              </div>
              <input 
                type="range" 
                min={-castle.garrison} 
                max={me.army_size} 
                value={garrisonTransfer}
                onChange={(e) => setGarrisonTransfer(parseInt(e.target.value))}
              />
              <div style={{ display: 'flex', justifyContent: 'center', fontSize: 12, color: 'var(--hint-color)', marginTop: 4 }}>
                Поточний перевід: <strong style={{color: 'white', marginLeft: 4}}>{garrisonTransfer}</strong>
              </div>
            </div>
            
            <button 
              className="action-button"
              disabled={garrisonTransfer === 0}
              style={{ opacity: garrisonTransfer === 0 ? 0.5 : 1, marginTop: 8 }}
              onClick={handleGarrisonChange}
            >
              Підтвердити
            </button>
          </div>
        )}

        {!isMine && !isCrownlands && (
          <div className="attack-section" style={{ background: 'rgba(59, 130, 246, 0.1)', padding: 16, borderRadius: 12, marginBottom: 16 }}>
            <h3 className="section-title" style={{ fontSize: 16, display: 'flex', alignItems: 'center', gap: 8, color: '#3b82f6' }}>
              Розвідка
            </h3>
            <p style={{ fontSize: 13, color: 'var(--hint-color)', marginBottom: 12 }}>
              Відправте розвідників, щоб дізнатися кількість гарнізону. Чим більше військ, тим вищий шанс успіху (і шанс їх втратити при розкритті).
            </p>
            
            <div className="slider-container">
              <div className="slider-info">
                <span>Розвідників:</span>
                <span style={{ fontWeight: 'bold', color: '#3b82f6' }}>{scoutAmount}</span>
              </div>
              <input 
                type="range" 
                min={1} 
                max={Math.min(100, me.army_size)} 
                value={scoutAmount}
                onChange={(e) => setScoutAmount(parseInt(e.target.value))}
              />
            </div>
            
            <button 
              className="action-button"
              style={{ background: '#3b82f6', marginTop: 8 }}
              onClick={handleScout}
            >
              Відправити розвідників
            </button>
          </div>
        )}

        {canAttack && !isCrownlands && (
          <div className="attack-section">
            <h3 className="section-title">Атакувати Замок</h3>
            <div className="slider-container">
              <div className="slider-info">
                <span>Військ для атаки:</span>
                <span style={{ fontWeight: 'bold', color: 'var(--button-color)' }}>{attackAmount}</span>
              </div>
              <input 
                type="range" 
                min={config?.min_attack_army || 100} 
                max={me.army_size} 
                value={attackAmount}
                onChange={(e) => setAttackAmount(parseInt(e.target.value))}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--hint-color)', marginTop: 4 }}>
                <span>{config?.min_attack_army || 100}</span>
                <span>{me.army_size}</span>
              </div>
            </div>
            
            <button 
              className="action-button destructive"
              onClick={() => {
                if (!isScouted) {
                  tg?.showConfirm(`Ви не знаєте гарнізон замку ${castle.name}! Атака наосліп може призвести до великих втрат. Відправити ${attackAmount} воїнів на штурм?`, (confirm) => {
                    if (confirm) onAttack(attackAmount);
                  });
                } else {
                  tg?.showConfirm(`Відправити ${attackAmount} воїнів на штурм замку ${castle.name}?`, (confirm) => {
                    if (confirm) onAttack(attackAmount);
                  });
                }
              }}
            >
              <Sword size={20} />
              Штурм
            </button>
          </div>
        )}

        {isKing && !isMine && !isCrownlands && castle.owner && (
          <div className="attack-section" style={{ marginTop: '20px' }}>
            <h3 className="section-title">Королівська влада</h3>
            
            {/* Demand Castle Button */}
            <button 
              className="action-button"
              style={{ background: '#10b981', marginBottom: '8px' }}
              onClick={async () => {
                tg?.showConfirm(`Вимагати замок ${castle.name} у лорда ${castle.owner.name}?`, async (confirm) => {
                  if (confirm) {
                    try {
                      const res = await fetch('/api/order', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${tg?.initData}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ target_id: castle.owner.id, order_type: 'castle', value: castle.name })
                      }).then(r => r.json());
                      tg?.showAlert(res.message || res.error);
                      onClose();
                    } catch (e) {
                      tg?.showAlert("Помилка з'єднання");
                    }
                  }
                });
              }}
            >
              <Crown size={20} />
              Вимагати замок
            </button>
            

          </div>
        )}

        {isCrownlands && !isMine && me && me.role !== 'puppet' && castle.owner && (
          <div className="attack-section" style={{ marginTop: '20px' }}>
            <h3 className="section-title">Залізний Трон</h3>
            <p style={{ textAlign: 'center', fontSize: '14px', marginBottom: '16px' }}>Ці землі належать Короні. Ви не можете їх атакувати, але можете розпочати повстання!</p>
            
            {showConspiracySlider && !state.conspiracy ? (
              <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px', marginBottom: '16px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', textAlign: 'center', color: '#f87171' }}>Скільки воїнів надіслати? (мін. 70%)</h4>
                <input 
                  type="range" 
                  min={minConspiracyAmount} 
                  max={me.army_size} 
                  value={conspiracyAmount} 
                  onChange={(e) => setConspiracyAmount(parseInt(e.target.value))}
                  style={{ width: '100%', accentColor: '#ef4444' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '14px', fontWeight: 'bold' }}>
                  <span>{minConspiracyAmount}</span>
                  <span style={{ color: '#ef4444', fontSize: '16px' }}>{conspiracyAmount}</span>
                  <span>{me.army_size}</span>
                </div>
              </div>
            ) : null}

            <button 
              className="action-button destructive"
              disabled={state.conspiracy}
              style={{ opacity: state.conspiracy ? 0.5 : 1 }}
              onClick={async () => {
                if (!showConspiracySlider) {
                  setShowConspiracySlider(true);
                  return;
                }

                tg?.showConfirm(`Ви дійсно хочете розпочати Змову, витративши ${conspiracyAmount} воїнів?`, async (confirm) => {
                  if (confirm) {
                    try {
                      const res = await fetch('/api/conspiracy', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          'Authorization': `Bearer ${tg?.initData}`
                        },
                        body: JSON.stringify({ amount: conspiracyAmount })
                      }).then(r => r.json());
                      tg?.showAlert(res.message || res.error);
                      if (res.message) {
                        if (reloadData) await reloadData();
                        onClose();
                      }
                    } catch (e) {
                      tg?.showAlert("Помилка з'єднання");
                    }
                  }
                });
              }}
            >
              <Sword size={20} />
              {showConspiracySlider && !state.conspiracy ? "Підтвердити" : "Розпочати змову"}
            </button>
            
            {showConspiracySlider && !state.conspiracy && (
              <button 
                className="action-button" 
                onClick={() => setShowConspiracySlider(false)}
                style={{ marginTop: '8px', background: '#475569' }}
              >
                Скасувати
              </button>
            )}

            {state.conspiracy ? (
              <p style={{ textAlign: 'center', fontSize: '12px', color: '#ef4444', marginTop: '8px', fontWeight: 'bold' }}>
                Змова вже триває! Приєднуйтесь до голосування в боті.
              </p>
            ) : (
              !showConspiracySlider && (
                <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--hint-color)', marginTop: '8px' }}>
                  Ви зможете обрати кількість війська (мінімум 70%).
                </p>
              )
            )}
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
