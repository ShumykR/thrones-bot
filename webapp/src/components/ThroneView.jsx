import { Crown } from 'lucide-react';
import throneImg from '../assets/throne.jpg';

export default function ThroneView({ state, me, tg }) {
  // Let's assume the user with role 'king' is the king.
  // For MVP, if we don't have the king's photo, we might use the player's if they are king, 
  // or a generic avatar. Wait, we don't have all users' photo_urls in the DB.
  // Let's show the player's avatar if they are the king, otherwise a placeholder or first letter.
  
  const king = state.users?.find(u => u.role === 'king');
  
  // If the current user is the king, use their Telegram photo_url
  let photoUrl = null;
  if (king && me && king.id === me.user_id) {
    photoUrl = tg?.initDataUnsafe?.user?.photo_url;
  }

  return (
    <div className="throne-view">
      <div className="throne-container">
        <img src={throneImg} alt="Iron Throne" className="throne-img" />
        
        {king ? (
          <div className="king-avatar-container">
            <div className="king-avatar" style={photoUrl ? { background: `url(${photoUrl}) center/cover no-repeat` } : {}}>
              {!photoUrl && king.name.charAt(0).toUpperCase()}
            </div>
            <div className="king-crown">
              <Crown size={24} color="#fbbf24" fill="#fbbf24" />
            </div>
            <div className="king-name-label">
              Король {king.name}
            </div>
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

      <div className="throne-info">
        <h2 className="section-title" style={{ textAlign: 'center', marginTop: '20px' }}>Залізний Трон</h2>
        <p style={{ textAlign: 'center', color: 'var(--hint-color)', fontSize: '14px', lineHeight: '1.5' }}>
          Той, хто сидить на Залізному Троні, править усіма Сімома Королівствами.<br/>
          Схили коліно або підніми повстання!
        </p>
      </div>
    </div>
  );
}
