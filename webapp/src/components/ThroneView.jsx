import { useState, useEffect } from 'react';
import { Crown, MessageSquare, AlertTriangle, ShieldOff, Sword, Gift } from 'lucide-react';
import throneImg from '../assets/throne.jpg';

export default function ThroneView({ state, me, tg, reloadData }) {
  const king = state.king;
  const isKing = king && me && king.id === me.user_id;
  
  const [decreeText, setDecreeText] = useState('');
  const [targetId, setTargetId] = useState('');
  const [photoError, setPhotoError] = useState(false);
  let photoUrl = null;
  if (king && !photoError) {
    photoUrl = '/api/photo/' + king.id;
  }

  const [showConspiracySlider, setShowConspiracySlider] = useState(false);
  const minConspiracyAmount = Math.ceil((me?.army_size || 0) * 0.70);
  const [conspiracyAmount, setConspiracyAmount] = useState(minConspiracyAmount);

  // Initialize conspiracyAmount whenever the modal opens or me.army_size changes
  useEffect(() => {
    if (me) {
      setConspiracyAmount(Math.ceil(me.army_size * 0.70));
    }
  }, [me]);

  const handleConspiracy = async () => {
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
            setShowConspiracySlider(false);
            if (reloadData) await reloadData();
          }
        } catch (e) {
          tg?.showAlert("Помилка з'єднання");
        }
      }
    });
  };

  const handleDecree = async () => {
    if (!decreeText) return;
    try {
      const res = await fetch('/api/decree', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tg?.initData}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: decreeText })
      }).then(r => r.json());
      
      tg?.showAlert(res.message || res.error);
      if (res.success) {
        setDecreeText('');
        if (reloadData) reloadData();
      }
    } catch (e) {
      tg?.showAlert("Помилка з'єднання");
    }
  };

  const handleKingAction = async (endpoint, payload = {}) => {
    if (!targetId) return;
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tg?.initData}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ target_id: targetId, ...payload })
      }).then(r => r.json());
      
      tg?.showAlert(res.message || res.error);
      if (res.success && reloadData) reloadData();
    } catch (e) {
      tg?.showAlert("Помилка з'єднання");
    }
  };

  const targetUser = state.users?.find(u => u.id == targetId);
  const targetCastles = state.castles?.filter(c => c.owner?.id == targetId && c.name !== "Королівські Землі");
  const myCastles = state.castles?.filter(c => c.owner?.id == me?.user_id && c.name !== "Королівські Землі");
  
  const [demandTroopsAmount, setDemandTroopsAmount] = useState(0);
  const [demandCastleId, setDemandCastleId] = useState('');
  
  const [giveTroopsAmount, setGiveTroopsAmount] = useState(0);
  const [giveCastleId, setGiveCastleId] = useState('');

  const loyalistsCount = state.users?.filter(u => u.role !== 'king' && u.king_opinion === 'good').length || 0;
  const rebelsCount = state.users?.filter(u => u.role !== 'king' && u.king_opinion === 'bad').length || 0;
  const authGrowth = 10 + (loyalistsCount * 5) - (rebelsCount * 5);

  return (
    <div className="throne-view" style={{ overflowY: 'auto' }}>
      <div className="throne-container" style={{ minHeight: '300px' }}>
        <img src={throneImg} alt="Iron Throne" className="throne-img" />
        
        {king ? (
          <div className="king-avatar-container">
            <div className="king-avatar" style={photoUrl ? { background: `url(${photoUrl}) center/cover no-repeat` } : {}}>
              {!photoUrl && king.name.charAt(0).toUpperCase()}
              {photoUrl && <img src={photoUrl} style={{ display: 'none' }} onError={() => setPhotoError(true)} />}
            </div>
            <div className="king-crown">
              <Crown size={24} color="#fbbf24" fill="#fbbf24" />
            </div>
            <div className="king-name-label">
              Король {king.name}
            </div>
            {me && me.role === 'king' && (
              <div className="king-authority-label" style={{ marginTop: '8px', background: 'rgba(0,0,0,0.6)', padding: '8px 16px', borderRadius: '12px', color: '#fbbf24', fontWeight: 'bold', fontSize: '14px', border: '1px solid #fbbf24', textAlign: 'center' }}>
                <div style={{ fontSize: '18px', marginBottom: '4px' }}>Авторитет: {king.authority !== undefined ? king.authority : 50}</div>
                <div style={{ fontSize: '12px', opacity: 0.9 }}>
                  Приріст: {authGrowth > 0 ? '+' : ''}{authGrowth}/день
                </div>
                <div style={{ fontSize: '11px', opacity: 0.7, marginTop: '2px', display: 'flex', gap: '8px', justifyContent: 'center' }}>
                  <span>База: +10</span>
                  <span>🟢 +{loyalistsCount * 5}</span>
                  <span>🔴 -{rebelsCount * 5}</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="king-avatar-container">
            <div className="king-avatar empty-throne">
              ?
            </div>
            <div className="king-name-label" style={{ background: 'transparent' }}>
              Трон вільний
            </div>
          </div>
        )}
      </div>

      <div className="throne-info" style={{ paddingBottom: '100px' }}>
        <h2 className="section-title" style={{ textAlign: 'center' }}>Залізний Трон</h2>
        
        {!isKing && king && me?.role !== 'puppet' && (
          <div style={{ marginTop: '20px' }}>
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
              onClick={handleConspiracy}
              disabled={state.conspiracy}
              style={{ opacity: state.conspiracy ? 0.5 : 1 }}
            >
              <Sword size={18} />
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
              <div style={{ marginTop: '8px' }}>
                <p style={{ textAlign: 'center', fontSize: '12px', color: '#ef4444', fontWeight: 'bold' }}>
                  Змова вже триває! Приєднуйтесь до голосування в боті.
                </p>
                {state.conspiracy.initiator_id === me?.user_id && (
                  <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '12px' }}>
                    <h4 style={{ textAlign: 'center', marginBottom: '12px', color: '#f87171', fontSize: '14px' }}>Учасники змови:</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                      {Object.entries(state.conspiracy.rebels || {}).map(([id, amount]) => {
                        const user = state.users?.find(u => u.id.toString() === id);
                        return (
                          <div key={id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>⚔️ <span style={{ color: '#f87171' }}>{user ? user.name : 'Невідомий'}</span></span>
                            <span style={{ color: 'var(--hint-color)' }}>{amount} воїнів</span>
                          </div>
                        );
                      })}
                      {Object.entries(state.conspiracy.loyalists || {}).map(([id, amount]) => {
                        const user = state.users?.find(u => u.id.toString() === id);
                        return (
                          <div key={id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>👑 <span style={{ color: '#60a5fa' }}>{user ? user.name : 'Невідомий'}</span></span>
                            <span style={{ color: 'var(--hint-color)' }}>{amount} воїнів</span>
                          </div>
                        );
                      })}
                      {Object.keys(state.conspiracy.rebels || {}).length === 0 && Object.keys(state.conspiracy.loyalists || {}).length === 0 && (
                        <div style={{ textAlign: 'center', color: 'var(--hint-color)' }}>Поки ніхто не проголосував...</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              !showConspiracySlider && (
                <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--hint-color)', marginTop: '8px' }}>
                  Ви зможете обрати кількість війська (мінімум 70%).
                </p>
              )
            )}
          </div>
        )}

        {isKing && (
          <div className="king-panel" style={{ marginTop: '20px' }}>
            <h3 className="section-title">Королівські накази</h3>
            
            <div style={{ marginBottom: '16px' }}>
              <input 
                type="text" 
                placeholder="Текст указу..." 
                value={decreeText}
                onChange={e => setDecreeText(e.target.value)}
                style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid var(--hint-color)', background: 'transparent', color: 'white', marginBottom: '8px' }}
              />
              <button className="action-button" onClick={() => {
                if (!decreeText) return;
                tg?.showConfirm(`Розіслати указ: "${decreeText}" усім лордам?`, (confirm) => {
                  if (confirm) handleDecree();
                });
              }}>
                <MessageSquare size={18} /> Розіслати указ
              </button>
            </div>

            <div style={{ marginBottom: '16px', background: 'rgba(255,255,255,0.05)', padding: '16px', borderRadius: '12px' }}>
              <h4 style={{ marginBottom: '12px', fontSize: '14px' }}>Взаємодія з лордом</h4>
              <select 
                value={targetId}
                onChange={e => {
                  setTargetId(e.target.value);
                  setDemandTroopsAmount(0);
                  setDemandCastleId('');
                }}
                className="mode-select"
                style={{ width: '100%', marginBottom: '16px' }}
              >
                <option value="">Оберіть лорда...</option>
                {state.users?.filter(u => u.id !== me.user_id).map(u => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>

              {targetUser && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  
                  {/* --- КАРА ТА ПОКАРАННЯ --- */}
                  <div style={{ padding: '12px', borderLeft: '4px solid #ef4444', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '0 8px 8px 0' }}>
                    <h5 style={{ margin: '0 0 12px 0', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <AlertTriangle size={16} /> Кара та покарання
                    </h5>
                    
                    {/* Demand Troops Slider */}
                    {targetUser.army_size > 0 && (
                      <div className="slider-container" style={{ margin: 0, marginBottom: '12px' }}>
                        <div className="slider-info">
                          <span>Вимагати військо:</span>
                          <span style={{ fontWeight: 'bold', color: '#3b82f6' }}>{demandTroopsAmount}</span>
                        </div>
                        <input 
                          type="range" 
                          min="0" 
                          max={targetUser.army_size} 
                          value={demandTroopsAmount}
                          onChange={(e) => setDemandTroopsAmount(parseInt(e.target.value))}
                        />
                        <button 
                          className="action-button" 
                          style={{ marginTop: '8px', background: '#3b82f6' }}
                          disabled={demandTroopsAmount === 0}
                          onClick={() => {
                            tg?.showConfirm(`Вимагати ${demandTroopsAmount} воїнів у лорда ${targetUser.name}?`, (confirm) => {
                              if (confirm) handleKingAction('/api/order', { order_type: 'troops', value: demandTroopsAmount });
                            });
                          }}
                        >
                          <Sword size={18} /> Надіслати вимогу (15 <Crown size={14} style={{display: 'inline', verticalAlign: 'text-bottom'}} />)
                        </button>
                      </div>
                    )}

                    {/* Demand Castle Select */}
                    {targetCastles?.length > 0 && (
                      <div style={{ marginBottom: '12px' }}>
                        <select 
                          value={demandCastleId}
                          onChange={e => setDemandCastleId(e.target.value)}
                          className="mode-select"
                          style={{ width: '100%', marginBottom: '8px' }}
                        >
                          <option value="">Оберіть замок для вилучення...</option>
                          {targetCastles.map(c => (
                            <option key={c.id} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                        <button 
                          className="action-button" 
                          style={{ background: '#10b981' }}
                          disabled={!demandCastleId}
                          onClick={() => {
                            tg?.showConfirm(`Вимагати замок ${demandCastleId} у лорда ${targetUser.name}?`, (confirm) => {
                              if (confirm) handleKingAction('/api/order', { order_type: 'castle', value: demandCastleId });
                            });
                          }}
                        >
                          <Crown size={18} /> Вимагати замок (30 <Crown size={14} style={{display: 'inline', verticalAlign: 'text-bottom'}} />)
                        </button>
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button 
                        className="action-button" 
                        style={{ flex: 1, background: '#f59e0b' }} 
                        onClick={() => {
                          tg?.showConfirm(`Відібрати голос у лорда ${targetUser.name} на 1 добу? (Вартість: 10 Авторитету)`, (confirm) => {
                            if (confirm) handleKingAction('/api/mute');
                          });
                        }}
                      >
                        <ShieldOff size={18} /> Mute (10 <Crown size={14} style={{display: 'inline', verticalAlign: 'text-bottom'}} />)
                      </button>
                      <button 
                        className="action-button destructive" 
                        style={{ flex: 1 }} 
                        onClick={() => {
                          tg?.showConfirm(`Підняти данину лорду ${targetUser.name} на 10%? (Вартість: 20 Авторитету)`, (confirm) => {
                            if (confirm) handleKingAction('/api/punish');
                          });
                        }}
                      >
                        <AlertTriangle size={18} /> Данина (20 <Crown size={14} style={{display: 'inline', verticalAlign: 'text-bottom'}} />)
                      </button>
                    </div>
                  </div>

                  {/* --- КОРОЛІВСЬКА МИЛІСТЬ --- */}
                  <div style={{ padding: '12px', borderLeft: '4px solid #10b981', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '0 8px 8px 0' }}>
                    <h5 style={{ margin: '0 0 12px 0', color: '#10b981', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Gift size={16} /> Королівська Милість
                    </h5>

                    {/* Give Troops Slider */}
                    {me.army_size > 0 && (
                      <div className="slider-container" style={{ margin: 0, marginBottom: '12px' }}>
                        <div className="slider-info">
                          <span>Дарувати військо:</span>
                          <span style={{ fontWeight: 'bold', color: '#10b981' }}>{giveTroopsAmount}</span>
                        </div>
                        <input 
                          type="range" 
                          min="0" 
                          max={me.army_size} 
                          value={giveTroopsAmount}
                          onChange={(e) => setGiveTroopsAmount(parseInt(e.target.value))}
                        />
                        <button 
                          className="action-button" 
                          style={{ marginTop: '8px', background: '#10b981', color: '#fff' }}
                          disabled={giveTroopsAmount === 0}
                          onClick={() => {
                            tg?.showConfirm(`Подарувати ${giveTroopsAmount} воїнів лорду ${targetUser.name}?`, (confirm) => {
                              if (confirm) handleKingAction('/api/order', { order_type: 'give_troops', value: giveTroopsAmount });
                            });
                          }}
                        >
                          <Gift size={18} /> Дарувати військо
                        </button>
                      </div>
                    )}

                    {/* Give Castle Select */}
                    {myCastles?.length > 0 && (
                      <div>
                        <select 
                          value={giveCastleId}
                          onChange={e => setGiveCastleId(e.target.value)}
                          className="mode-select"
                          style={{ width: '100%', marginBottom: '8px' }}
                        >
                          <option value="">Оберіть замок для дарунку...</option>
                          {myCastles.map(c => (
                            <option key={c.id} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                        <button 
                          className="action-button" 
                          style={{ background: '#3b82f6' }}
                          disabled={!giveCastleId}
                          onClick={() => {
                            tg?.showConfirm(`Подарувати замок ${giveCastleId} лорду ${targetUser.name}?`, (confirm) => {
                              if (confirm) handleKingAction('/api/order', { order_type: 'give_castle', value: giveCastleId });
                            });
                          }}
                        >
                          <Crown size={18} /> Дарувати замок
                        </button>
                      </div>
                    )}
                  </div>
                  
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
