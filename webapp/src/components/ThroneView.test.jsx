import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ThroneView from './ThroneView';

describe('ThroneView component', () => {
  let mockTg;
  let mockReloadData;

  beforeEach(() => {
    vi.clearAllMocks();
    mockTg = {
      initData: 'query_id=test',
      showAlert: vi.fn(),
      showConfirm: vi.fn((msg, cb) => cb(true))
    };
    mockReloadData = vi.fn();
    global.fetch = vi.fn();
  });

  const baseState = {
    king: { id: 2, name: 'Cersei', authority: 50 },
    users: [
      { id: 1, user_id: 1, name: 'Jon Snow', role: 'lord', army_size: 1000 },
      { id: 2, user_id: 2, name: 'Cersei', role: 'king', army_size: 5000 }
    ],
    castles: [
      { id: 1, name: 'Вінтерфелл', owner: { id: 1 } },
      { id: 2, name: 'Скеля Кастерлі', owner: { id: 2 } }
    ],
    conspiracy: null
  };

  it('renders throne info and king details', () => {
    const me = { user_id: 1, role: 'lord', army_size: 1000 };
    render(<ThroneView state={baseState} me={me} tg={mockTg} />);
    
    expect(screen.getByText('Король Cersei')).toBeInTheDocument();
    expect(screen.getByText('Залізний Трон')).toBeInTheDocument();
    expect(screen.getByText('Розпочати змову')).toBeInTheDocument();
  });

  it('allows starting a conspiracy', async () => {
    const me = { user_id: 1, role: 'lord', army_size: 1000 };
    
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Змову розпочато' })
    });

    render(<ThroneView state={baseState} me={me} tg={mockTg} reloadData={mockReloadData} />);
    
    const startBtn = screen.getByText('Розпочати змову', { selector: 'button' });
    fireEvent.click(startBtn);
    
    // Now it should show slider and 'Підтвердити'
    const confirmBtn = screen.getByText('Підтвердити', { selector: 'button' });
    expect(screen.getByText(/Скільки воїнів надіслати/)).toBeInTheDocument();
    
    fireEvent.click(confirmBtn);
    
    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/conspiracy', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ amount: 700 }) // 70% of 1000
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('shows active conspiracy status', () => {
    const me = { user_id: 1, role: 'lord', army_size: 1000 };
    const conspiracyState = {
      ...baseState,
      conspiracy: {
        initiator_id: 1,
        rebels: { '1': 700, '3': 500 },
        loyalists: { '2': 1000 }
      },
      users: [
        ...baseState.users,
        { id: 3, user_id: 3, name: 'Robb' }
      ]
    };

    render(<ThroneView state={conspiracyState} me={me} tg={mockTg} />);
    
    expect(screen.getByText('Змова вже триває! Приєднуйтесь до голосування в боті.')).toBeInTheDocument();
    expect(screen.getByText('Учасники змови:')).toBeInTheDocument();
    expect(screen.getByText('Jon Snow')).toBeInTheDocument();
    expect(screen.getByText('Robb')).toBeInTheDocument();
    expect(screen.getByText('Cersei')).toBeInTheDocument();
  });

  it('shows king panel for the king', () => {
    const me = { user_id: 2, role: 'king', army_size: 5000 };
    render(<ThroneView state={baseState} me={me} tg={mockTg} />);
    
    expect(screen.getByText('Королівські накази')).toBeInTheDocument();
    expect(screen.getByText('Розіслати указ')).toBeInTheDocument();
    expect(screen.getByText('Взаємодія з лордом')).toBeInTheDocument();
    expect(screen.getByText('Авторитет: 50')).toBeInTheDocument();
  });

  it('allows king to send a decree', async () => {
    const me = { user_id: 2, role: 'king', army_size: 5000 };
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true })
    });

    render(<ThroneView state={baseState} me={me} tg={mockTg} reloadData={mockReloadData} />);
    
    const input = screen.getByPlaceholderText('Текст указу...');
    fireEvent.change(input, { target: { value: 'All hail the King' } });
    
    const sendBtn = screen.getByText('Розіслати указ', { selector: 'button' });
    fireEvent.click(sendBtn);
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/decree', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'All hail the King' })
      }));
    });
  });

  it('allows king to interact with lords', async () => {
    const me = { user_id: 2, role: 'king', army_size: 5000 };
    global.fetch.mockResolvedValue({
      json: async () => ({ success: true })
    });

    render(<ThroneView state={baseState} me={me} tg={mockTg} reloadData={mockReloadData} />);
    
    // Select Lord
    const selectLord = screen.getByText('Оберіть лорда...').parentElement;
    fireEvent.change(selectLord, { target: { value: '1' } }); // Select Jon Snow
    
    // Options should appear
    expect(screen.getByText('Кара та покарання')).toBeInTheDocument();
    expect(screen.getByText('Королівська Милість')).toBeInTheDocument();
    
    // Test Mute
    const muteBtn = screen.getByText(/Mute/, { selector: 'button' });
    fireEvent.click(muteBtn);
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/mute', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: "1" })
      }));
    });

    // Test Demand Troops
    const demandTroopsSlider = screen.getAllByRole('slider').find(el => el.max === '1000');
    fireEvent.change(demandTroopsSlider, { target: { value: '100' } });
    const demandTroopsBtn = screen.getByText(/Надіслати вимогу/);
    fireEvent.click(demandTroopsBtn);
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/order', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: "1", order_type: 'troops', value: 100 })
      }));
    });




    // Test Punish
    const punishBtn = screen.getByText(/Данина/, { selector: 'button' });
    fireEvent.click(punishBtn);
    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/punish', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: "1" })
      }));
    });

    // Test Give Troops
    const troopsSlider = screen.getAllByRole('slider').find(el => el.max === '5000');
    fireEvent.change(troopsSlider, { target: { value: 1000 } });
    
    // Check if the amount is actually updated
    expect(screen.getByText('1000')).toBeInTheDocument();
    
    const giveTroopsBtn = screen.getByText(/Дарувати військо/, { selector: 'button' });
    expect(giveTroopsBtn).not.toBeDisabled();
    fireEvent.click(giveTroopsBtn);
    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/order', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: "1", order_type: 'give_troops', value: 1000 })
      }));
    });

    // Test Give Castle
    const castleSelect = screen.getByText('Оберіть замок для дарунку...').parentElement;
    fireEvent.change(castleSelect, { target: { value: 'Скеля Кастерлі' } });
    
    const giveCastleBtn = screen.getByText(/Дарувати замок/, { selector: 'button' });
    fireEvent.click(giveCastleBtn);
    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/order', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: "1", order_type: 'give_castle', value: 'Скеля Кастерлі' })
      }));
    });

    // Test Demand Castle
    const demandCastleSelect = screen.getByText('Оберіть замок для вилучення...').parentElement;
    fireEvent.change(demandCastleSelect, { target: { value: 'Вінтерфелл' } });
    
    const demandCastleBtn = screen.getByText(/Вимагати замок/, { selector: 'button' });
    fireEvent.click(demandCastleBtn);
    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/order', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: "1", order_type: 'castle', value: 'Вінтерфелл' })
      }));
    });
  });
});
