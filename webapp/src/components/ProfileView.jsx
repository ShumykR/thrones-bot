import { useState } from 'react';
import { Shield, Sword, Users, Flame, Send, TrendingUp } from 'lucide-react';

export default function ProfileView({ me, state, tg, reloadData }) {


  if (!me) return <div className="profile-view">Завантаження...</div>;





  const getRoleLabel = (role) => {
    switch (role) {
      case 'king': return '👑 Король';
      case 'puppet': return '⛓️ Маріонетка';
      default: return '⚔️ Лорд';
    }
  };

  const isKing = me.role === 'king';
  const [photoError, setPhotoError] = useState(false);
  const photoUrl = photoError ? null : (me.photo_url || tg?.initDataUnsafe?.user?.photo_url);

  const myStateUser = state.users?.find(u => u.id === me.user_id);
  const allianceId = myStateUser?.alliance_id;
  const isAllianceLeader = state.alliances?.find(a => a.id === allianceId)?.leader_id === me.user_id;
  const allianceMembers = state.users?.filter(u => u.alliance_id === allianceId && u.id !== me.user_id) || [];
  const myCastles = state.castles?.filter(c => c.owner?.id === me.user_id && c.name !== "Королівські Землі") || [];
  const myIncome = myCastles.reduce((sum, c) => sum + (c.army_per_hour || 10), 0) || 2;
  const myTributeAmount = Math.floor(myIncome * (me.king_tribute_rate || 0));

  const [transferTargetId, setTransferTargetId] = useState('');
  const [transferAmount, setTransferAmount] = useState(0);

  const handleTransfer = async () => {
    if (!transferTargetId || transferAmount <= 0) return;
    tg?.HapticFeedback?.impactOccurred('medium');
    try {
      const res = await fetch('/api/transfer', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tg?.initData}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ target_id: transferTargetId, amount: transferAmount })
      }).then(r => r.json());
      tg?.showAlert(res.message || res.error);
      if (res.success) {
        setTransferAmount(0);
        if (reloadData) reloadData();
      }
    } catch (e) {
      tg?.showAlert("Помилка з'єднання");
    }
  };

  return (
    <div className="profile-view" style={{ overflowY: 'auto', paddingBottom: '100px' }}>
      <div className="profile-header">
        <div className="avatar-circle" style={photoUrl ? { background: `url(${photoUrl}) center/cover no-repeat` } : {}}>
          {!photoUrl && me.first_name.charAt(0).toUpperCase()}
          {photoUrl && <img src={photoUrl} style={{ display: 'none' }} onError={() => setPhotoError(true)} />}
        </div>
        <div className="profile-info">
          <h1>{me.first_name}</h1>
          <div className="role-badge">{getRoleLabel(me.role)}</div>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-box">
          <Sword className="stat-icon" />
          <div className="stat-content">
            <span className="stat-label">Військо</span>
            <span className="stat-value">{me.army_size}</span>
          </div>
        </div>
        <div className="stat-box">
          <Shield className="stat-icon" />
          <div className="stat-content">
            <span className="stat-label">Замки</span>
            <span className="stat-value">{me.castles_count}</span>
          </div>
        </div>
        <div className="stat-box" style={{ flexDirection: 'column', alignItems: 'flex-start', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', width: '100%', marginBottom: '12px' }}>
            <TrendingUp className="stat-icon" style={{ marginBottom: 0 }} />
            <div className="stat-content" style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="stat-label">Приріст</span>
              <span className="stat-value">+{myIncome - myTributeAmount}/год</span>
            </div>
          </div>
          <div style={{ width: '100%', fontSize: '12px', opacity: 0.8, display: 'flex', flexDirection: 'column', gap: '4px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
            {myCastles.length === 0 && <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>База:</span> <span>+2</span></div>}
            {myCastles.map(c => (
              <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between' }}><span>{c.name}:</span> <span style={{ color: '#10b981' }}>+{c.army_per_hour || 10}</span></div>
            ))}
            {myTributeAmount > 0 && <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Данина Королю:</span> <span style={{ color: '#ef4444' }}>-{myTributeAmount}</span></div>}
          </div>
        </div>
      </div>


      {isKing && (
        <div style={{ marginTop: '20px', background: 'rgba(251, 191, 36, 0.1)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(251, 191, 36, 0.3)' }}>
          <h3 className="section-title" style={{ color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Users size={18} /> Ваші Васали
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
            {state.users?.filter(u => u.role !== 'king').map(u => {
              const opinionEmoji = u.king_opinion === 'good' ? '🟢' : u.king_opinion === 'bad' ? '🔴' : '⚪';
              const vassalCastles = state.castles?.filter(c => c.owner?.id === u.id && c.name !== "Королівські Землі") || [];
              const vassalIncome = vassalCastles.reduce((sum, c) => sum + (c.army_per_hour || 10), 0) || 2;
              const vassalTribute = Math.floor(vassalIncome * (u.king_tribute_rate || 0));

              return (
                <div key={u.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', alignItems: 'center' }}>
                  <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: '18px' }}>{opinionEmoji}</span> 
                    {u.name}
                  </span>
                  <span style={{ color: '#fbbf24', fontWeight: 'bold' }}>
                    {Math.round((u.king_tribute_rate || 0) * 100)}% 
                    <span style={{ fontSize: '12px', opacity: 0.8, marginLeft: '4px' }}>({vassalTribute}/год)</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {me.king_tribute_rate > 0 && me.role !== 'king' && (
        <div style={{ marginTop: '20px', background: 'rgba(239, 68, 68, 0.1)', padding: '16px', borderRadius: '12px' }}>
          <h3 className="section-title" style={{ color: '#ef4444' }}>Королівська Данина</h3>
          <p style={{ fontSize: '14px', marginBottom: '0' }}>Ви сплачуєте <b>{Math.round(me.king_tribute_rate * 100)}%</b> ({myTributeAmount} воїнів/год) свого доходу Короні через непокору.</p>
        </div>
      )}

      {allianceId && !isKing && (
        <div style={{ marginTop: '20px', background: 'rgba(59, 130, 246, 0.1)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 className="section-title" style={{ color: '#3b82f6', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              <Shield size={18} /> Ваш Альянс
            </h3>
            <button 
              className="action-button" 
              style={{ background: 'transparent', color: '#ef4444', border: '1px solid #ef4444', padding: '6px 12px', fontSize: '12px' }}
              onClick={() => {
                tg?.showConfirm(isAllianceLeader ? "Дійсно розформувати альянс?" : "Дійсно покинути альянс?", async (confirm) => {
                  if (confirm) {
                    try {
                      const res = await fetch('/api/alliance/leave', {
                        method: 'POST',
                        headers: {
                          'Authorization': `Bearer ${tg?.initData}`,
                          'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({})
                      }).then(r => r.json());
                      tg?.showAlert(res.message || res.error);
                      if (res.success && reloadData) reloadData();
                    } catch (e) {
                      tg?.showAlert("Помилка з'єднання");
                    }
                  }
                });
              }}
            >
              {isAllianceLeader ? 'Розформувати' : 'Покинути'}
            </button>
          </div>
          <p style={{ fontSize: '14px', marginBottom: '16px', color: 'var(--hint-color)' }}>
            Передавайте війська союзникам для взаємодопомоги.
          </p>

          {isAllianceLeader && (
            <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
              <select 
                className="mode-select" 
                id="invite-target-id"
                style={{ flex: 1 }}
              >
                <option value="">Запросити лорда...</option>
                {state.users?.filter(u => u.id !== me.user_id && !u.alliance_id && u.role !== 'king').map(u => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>
              <button 
                className="action-button" 
                style={{ background: '#3b82f6', width: 'auto', padding: '0 16px' }}
                onClick={async () => {
                  const targetSelect = document.getElementById('invite-target-id');
                  const targetId = targetSelect ? targetSelect.value : '';
                  if (!targetId) return tg?.showAlert("Оберіть лорда!");

                  const targetName = targetSelect.options[targetSelect.selectedIndex].text;
                  tg?.showConfirm(`Надіслати запрошення лорду ${targetName}?`, async (confirm) => {
                    if (confirm) {
                      try {
                        const res = await fetch('/api/alliance/invite', {
                          method: 'POST',
                          headers: {
                            'Authorization': `Bearer ${tg?.initData}`,
                            'Content-Type': 'application/json'
                          },
                          body: JSON.stringify({ target_id: targetId })
                        }).then(r => r.json());
                        tg?.showAlert(res.message || res.error);
                      } catch (e) {
                        tg?.showAlert("Помилка з'єднання");
                      }
                    }
                  });
                }}
              >
                +
              </button>
            </div>
          )}

          {allianceMembers.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <select 
                value={transferTargetId}
                onChange={e => setTransferTargetId(e.target.value)}
                className="mode-select"
                style={{ width: '100%' }}
              >
                <option value="">Оберіть союзника...</option>
                {allianceMembers.map(u => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>

              {transferTargetId && (
                <div className="slider-container" style={{ margin: 0 }}>
                  <div className="slider-info">
                    <span>Передати:</span>
                    <span style={{ fontWeight: 'bold', color: '#3b82f6' }}>{transferAmount}</span>
                  </div>
                  <input 
                    type="range" 
                    min="0" 
                    max={me.army_size} 
                    value={transferAmount}
                    onChange={(e) => setTransferAmount(parseInt(e.target.value))}
                  />
                  <button 
                    className="action-button" 
                    style={{ marginTop: '8px', background: '#3b82f6' }}
                    disabled={transferAmount <= 0}
                    onClick={() => {
                      const targetName = allianceMembers.find(u => u.id == transferTargetId)?.name;
                      tg?.showConfirm(`Надіслати ${transferAmount} воїнів союзнику ${targetName}?`, (confirm) => {
                        if (confirm) handleTransfer();
                      });
                    }}
                  >
                    <Send size={18} /> Надіслати
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '12px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', textAlign: 'center', color: 'var(--hint-color)' }}>
              У вашому альянсі немає інших лордів.
            </div>
          )}
        </div>
      )}

      {!allianceId && !isKing && (
        <div style={{ marginTop: '20px', background: 'rgba(59, 130, 246, 0.1)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
          <h3 className="section-title" style={{ color: '#3b82f6', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={18} /> Створити Альянс
          </h3>
          <p style={{ fontSize: '14px', marginBottom: '16px', color: 'var(--hint-color)' }}>
            Ви не перебуваєте в альянсі. Створіть свій, щоб об'єднати лордів під вашим стягом!
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <input 
              type="text" 
              placeholder="Назва альянсу (до 30 симв.)"
              className="mode-select"
              id="new-alliance-input"
              style={{ width: '100%', boxSizing: 'border-box' }}
            />
            <button 
              className="action-button" 
              style={{ background: '#3b82f6' }}
              onClick={async () => {
                const nameInput = document.getElementById('new-alliance-input');
                const name = nameInput ? nameInput.value.trim() : '';
                if (!name) return tg?.showAlert("Введіть назву!");
                
                tg?.showConfirm(`Створити альянс «${name}»?`, async (confirm) => {
                  if (confirm) {
                    try {
                      const res = await fetch('/api/alliance/create', {
                        method: 'POST',
                        headers: {
                          'Authorization': `Bearer ${tg?.initData}`,
                          'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ name })
                      }).then(r => r.json());
                      tg?.showAlert(res.message || res.error);
                      if (res.success) {
                        if (nameInput) nameInput.value = '';
                        if (reloadData) reloadData();
                      }
                    } catch (e) {
                      tg?.showAlert("Помилка з'єднання");
                    }
                  }
                });
              }}
            >
              Створити Альянс
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
