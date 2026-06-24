import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import ProfileView from './ProfileView';

describe('ProfileView component', () => {
  let mockTg;
  let mockReloadData;

  beforeEach(() => {
    vi.clearAllMocks();
    mockTg = {
      initData: 'query_id=test',
      initDataUnsafe: { user: { photo_url: 'http://test.com/photo.jpg' } },
      showAlert: vi.fn(),
      showConfirm: vi.fn((msg, cb) => cb(true)),
      HapticFeedback: { impactOccurred: vi.fn() }
    };
    mockReloadData = vi.fn();
    global.fetch = vi.fn();
  });

  const baseState = {
    users: [
      { id: 1, user_id: 1, name: 'Jon Snow', role: 'lord', army_size: 1000 },
      { id: 2, user_id: 2, name: 'Cersei', role: 'king', army_size: 5000 },
      { id: 3, user_id: 3, name: 'Robb Stark', role: 'lord', alliance_id: 1, army_size: 800 }
    ],
    castles: [],
    alliances: []
  };

  it('renders loading when me is null', () => {
    const { container } = render(<ProfileView me={null} state={baseState} />);
    expect(container.textContent).toBe('Завантаження...');
  });

  it('renders lord profile properly', () => {
    const me = { user_id: 1, first_name: 'Jon', role: 'lord', army_size: 1500, castles_count: 2 };
    render(<ProfileView me={me} state={baseState} tg={mockTg} />);
    
    expect(screen.getByText('Jon')).toBeInTheDocument();
    expect(screen.getByText('⚔️ Лорд')).toBeInTheDocument();
    expect(screen.getByText('1500')).toBeInTheDocument(); // Army
    expect(screen.getByText('2')).toBeInTheDocument(); // Castles
    // Base income is 2, plus no castles in state -> +2/год
    expect(screen.getByText('+2/год')).toBeInTheDocument();
    // Alliance creation box should be visible
    expect(screen.getByText('Створити Альянс', { selector: 'button' })).toBeInTheDocument();
  });

  it('renders king profile properly with vassals', () => {
    const me = { user_id: 2, first_name: 'Cersei', role: 'king', army_size: 5000, castles_count: 5 };
    const kingState = {
      ...baseState,
      users: [
        { id: 1, name: 'Jon Snow', role: 'lord', king_opinion: 'bad', king_tribute_rate: 0.2 },
        { id: 3, name: 'Sansa', role: 'lord', king_opinion: 'good', king_tribute_rate: 0 }
      ]
    };
    render(<ProfileView me={me} state={kingState} tg={mockTg} />);
    
    expect(screen.getByText('👑 Король')).toBeInTheDocument();
    expect(screen.getByText('Ваші Васали')).toBeInTheDocument();
    // Check vassal rendering
    expect(screen.getByText(/Jon Snow/)).toBeInTheDocument();
    expect(screen.getByText(/🔴/)).toBeInTheDocument();
    expect(screen.getByText('20%')).toBeInTheDocument();
    
    expect(screen.getByText(/Sansa/)).toBeInTheDocument();
    expect(screen.getByText(/🟢/)).toBeInTheDocument();
  });

  it('shows king tribute alert if lord pays tribute', () => {
    const me = { user_id: 1, first_name: 'Jon', role: 'lord', king_tribute_rate: 0.2 };
    render(<ProfileView me={me} state={baseState} tg={mockTg} />);
    expect(screen.getByText('Королівська Данина')).toBeInTheDocument();
    expect(screen.getByText(/Ви сплачуєте/)).toBeInTheDocument();
    expect(screen.getByText(/20%/)).toBeInTheDocument();
  });

  it('allows creating an alliance', async () => {
    const me = { user_id: 1, first_name: 'Jon', role: 'lord' };
    
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Альянс створено' })
    });

    render(<ProfileView me={me} state={baseState} tg={mockTg} reloadData={mockReloadData} />);
    
    const input = document.getElementById('new-alliance-input');
    fireEvent.change(input, { target: { value: 'Starks' } });
    
    const createBtn = screen.getByText('Створити Альянс', { selector: 'button' });
    fireEvent.click(createBtn);
    
    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/alliance/create', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Starks' })
      }));
      expect(mockTg.showAlert).toHaveBeenCalledWith('Альянс створено');
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('renders alliance tools if user is in an alliance', () => {
    const me = { user_id: 3, first_name: 'Robb', role: 'lord' };
    const stateWithAlliance = {
      ...baseState,
      users: [
        { id: 3, user_id: 3, name: 'Robb', alliance_id: 1 },
        { id: 4, user_id: 4, name: 'Arya', alliance_id: 1 }
      ],
      alliances: [
        { id: 1, name: 'Starks', leader_id: 3 }
      ]
    };

    render(<ProfileView me={me} state={stateWithAlliance} tg={mockTg} />);
    
    // Alliance tools
    expect(screen.getByText('Ваш Альянс')).toBeInTheDocument();
    expect(screen.getByText('Розформувати')).toBeInTheDocument();
    
    // Check invite dropdown
    expect(screen.getByText('Запросити лорда...')).toBeInTheDocument();
    
    // Check transfer dropdown
    expect(screen.getByText('Оберіть союзника...')).toBeInTheDocument();
    expect(screen.getByText('Arya')).toBeInTheDocument();
  });

  it('allows transferring army to alliance member', async () => {
    const me = { user_id: 3, first_name: 'Robb', role: 'lord', army_size: 1000 };
    const stateWithAlliance = {
      ...baseState,
      users: [
        { id: 3, user_id: 3, name: 'Robb', alliance_id: 1 },
        { id: 4, user_id: 4, name: 'Arya', alliance_id: 1 }
      ],
      alliances: [
        { id: 1, name: 'Starks', leader_id: 3 }
      ]
    };

    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Війська передано' })
    });

    render(<ProfileView me={me} state={stateWithAlliance} tg={mockTg} reloadData={mockReloadData} />);
    
    // Select Arya
    const selectBox = screen.getAllByRole('combobox')[1]; // First is invite, second is transfer
    fireEvent.change(selectBox, { target: { value: '4' } });

    // Drag slider
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '500' } });

    const transferBtn = screen.getByText(/Надіслати/, { selector: 'button' });
    fireEvent.click(transferBtn);

    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/transfer', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: '4', amount: 500 })
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('allows inviting lord to alliance', async () => {
    const me = { user_id: 3, first_name: 'Robb', role: 'lord' };
    const stateWithAlliance = {
      ...baseState,
      users: [
        { id: 3, user_id: 3, name: 'Robb', alliance_id: 1 },
        { id: 5, user_id: 5, name: 'Bran', role: 'lord', alliance_id: null }
      ],
      alliances: [
        { id: 1, name: 'Starks', leader_id: 3 }
      ]
    };

    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Запрошення надіслано' })
    });

    render(<ProfileView me={me} state={stateWithAlliance} tg={mockTg} reloadData={mockReloadData} />);
    
    // Select Bran
    const selectBox = screen.getAllByRole('combobox')[0]; // First is invite
    fireEvent.change(selectBox, { target: { value: '5' } });

    const inviteBtn = screen.getByText('+', { selector: 'button' });
    fireEvent.click(inviteBtn);

    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/alliance/invite', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: '5' })
      }));
    });
  });

  it('allows leaving alliance', async () => {
    const me = { user_id: 3, first_name: 'Robb', role: 'lord', alliance_id: 1 };
    const stateWithAlliance = {
      ...baseState,
      users: [
        { id: 3, user_id: 3, name: 'Robb', alliance_id: 1 }
      ],
      alliances: [
        { id: 1, name: 'Starks', leader_id: 2 } // someone else is leader
      ]
    };

    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Ви залишили альянс' })
    });

    render(<ProfileView me={me} state={stateWithAlliance} tg={mockTg} reloadData={mockReloadData} />);
    
    const leaveBtn = screen.getByText('Покинути', { selector: 'button' });
    fireEvent.click(leaveBtn);

    expect(mockTg.showConfirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/alliance/leave', expect.objectContaining({
        method: 'POST'
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('handles fetch errors gracefully', async () => {
    const me = { user_id: 1, first_name: 'Jon', role: 'lord' };
    global.fetch.mockRejectedValueOnce(new Error('Network error'));

    render(<ProfileView me={me} state={baseState} tg={mockTg} reloadData={mockReloadData} />);
    
    const input = document.getElementById('new-alliance-input');
    fireEvent.change(input, { target: { value: 'Starks' } });
    
    const createBtn = screen.getByText('Створити Альянс', { selector: 'button' });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(mockTg.showAlert).toHaveBeenCalledWith("Помилка з'єднання");
    });
  });
});
