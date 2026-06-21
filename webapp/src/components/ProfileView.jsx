import { motion } from 'framer-motion';
import { Shield, Sword, Crown, Castle as CastleIcon, Flag, Users } from 'lucide-react';

export default function ProfileView({ me, state, tg }) {
  if (!me) return <div className="profile-view">Завантаження...</div>;

  const roleLabels = {
    'king': 'Король',
    'lord': 'Лорд',
    'puppet': 'Маріонетка'
  };

  const isKing = me.role === 'king';
  const photoUrl = tg?.initDataUnsafe?.user?.photo_url;

  return (
    <div className="profile-view">
      <div className="profile-header">
        <div className="avatar-circle" style={photoUrl ? { background: `url(${photoUrl}) center/cover no-repeat` } : {}}>
          {!photoUrl && me.first_name.charAt(0).toUpperCase()}
        </div>
        <div className="profile-info">
          <h1>{me.first_name}</h1>
          <div className="role-badge">
            {isKing && <Crown size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: '-2px' }} />}
            {roleLabels[me.role] || me.role}
          </div>
        </div>
      </div>

      <h2 className="section-title">Військові сили</h2>
      <div className="stats-grid">
        <div className="stat-box">
          <Sword className="stat-icon" size={24} />
          <div className="stat-content">
            <span className="stat-label">Розмір армії</span>
            <span className="stat-value">{me.army_size}</span>
          </div>
        </div>
        <div className="stat-box">
          <CastleIcon className="stat-icon" size={24} />
          <div className="stat-content">
            <span className="stat-label">Замків</span>
            <span className="stat-value">{me.castles_count}</span>
          </div>
        </div>
      </div>

      {me.role === 'puppet' && (
        <>
          <h2 className="section-title">Маріонетка</h2>
          <div className="stat-box" style={{ marginBottom: 24 }}>
            <Flag className="stat-icon" size={24} />
            <div className="stat-content">
              <span className="stat-label">Бали Незалежності</span>
              <span className="stat-value">{me.independence_points} / 10</span>
            </div>
          </div>
        </>
      )}

      <h2 className="section-title">Дії</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Placeholder for future actions */}
        <button className="action-button" onClick={() => tg?.showAlert("Ця функція скоро з'явиться у WebApp!")}>
          <Users size={20} />
          Створити Альянс
        </button>
        <button className="action-button" onClick={() => tg?.showAlert("Ця функція скоро з'явиться у WebApp!")}>
          <Sword size={20} />
          Організувати Змову
        </button>
        {isKing && (
          <button className="action-button" style={{ background: '#f59e0b', color: '#000' }} onClick={() => tg?.showAlert("Ця функція скоро з'явиться у WebApp!")}>
            <Crown size={20} />
            Королівський Наказ
          </button>
        )}
      </div>
    </div>
  );
}
