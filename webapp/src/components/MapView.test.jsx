import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import MapView from './MapView';

// Mock MapSvg to easily trigger castle clicks without dealing with complex SVG paths
vi.mock('./MapSvg', () => ({
  default: ({ state, onCastleClick }) => (
    <div data-testid="map-svg-mock">
      {state.castles.map(c => (
        <button key={c.id} onClick={() => onCastleClick(c)}>
          Click {c.name}
        </button>
      ))}
    </div>
  )
}));

describe('MapView and CastleModal components', () => {
  let mockTg;
  let mockOnAttack;
  let mockReloadData;

  beforeEach(() => {
    vi.clearAllMocks();
    mockTg = {
      initData: 'query_id=test',
      showAlert: vi.fn(),
      showConfirm: vi.fn((msg, cb) => cb(true)),
      HapticFeedback: { impactOccurred: vi.fn() }
    };
    mockOnAttack = vi.fn();
    mockReloadData = vi.fn();
    global.fetch = vi.fn();
  });

  const baseState = {
    config: { min_attack_army: 100 },
    users: [
      { id: 1, user_id: 1, name: 'Jon Snow', role: 'lord', army_size: 1000 },
      { id: 2, user_id: 2, name: 'Cersei', role: 'king', army_size: 5000 }
    ],
    castles: [
      { id: 1, name: 'Вінтерфелл', garrison: 500, army_per_hour: 20, owner: { id: 1, name: 'Jon Snow' } },
      { id: 2, name: 'Королівські Землі', garrison: 1200, army_per_hour: 50, owner: { id: 2, name: 'Cersei' } },
      { id: 3, name: 'Порожній Замок', garrison: 0, army_per_hour: 10, owner: null }
    ],
    king: { id: 2 },
    scouted_castles: {}
  };

  const me = { user_id: 1, role: 'lord', army_size: 1500 };

  it('renders map switcher and legend', () => {
    render(<MapView state={baseState} me={me} onAttack={mockOnAttack} tg={mockTg} />);
    expect(screen.getByText('👑 Власники')).toBeInTheDocument();
    expect(screen.getByText('Вільні землі')).toBeInTheDocument();
    expect(screen.getByText('Jon Snow')).toBeInTheDocument();
  });

  it('opens CastleModal on castle click and allows attacking enemy', async () => {
    render(<MapView state={baseState} me={me} onAttack={mockOnAttack} tg={mockTg} />);
    
    // Click empty castle
    fireEvent.click(screen.getByText('Click Порожній Замок'));
    
    expect(screen.getByText('Порожній Замок', { selector: '.panel-title' })).toBeInTheDocument();
    expect(screen.getByText('Власник:')).toBeInTheDocument();
    expect(screen.getByText('Вільний')).toBeInTheDocument();
    
    // Attack button should be there
    const attackBtn = screen.getByText('Штурм', { selector: 'button' });
    fireEvent.click(attackBtn);
    
    expect(mockTg.showConfirm).toHaveBeenCalled();
    expect(mockOnAttack).toHaveBeenCalledWith(3, 100); // 100 is min_attack_army
  });

  it('allows owner to manage garrison', async () => {
    render(<MapView state={baseState} me={me} onAttack={mockOnAttack} tg={mockTg} reloadData={mockReloadData} />);
    
    // Click own castle
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    expect(screen.getByText('Керування гарнізоном')).toBeInTheDocument();
    
    // Set slider value
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '50' } });
    
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Гарнізон змінено' })
    });

    const confirmBtn = screen.getByText('Підтвердити', { selector: 'button' });
    fireEvent.click(confirmBtn);
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/garrison', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ castle_id: 1, amount: 50 })
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('allows scouting enemy castle', async () => {
    const anotherLord = { user_id: 3, role: 'lord', army_size: 1500 };
    render(<MapView state={baseState} me={anotherLord} onAttack={mockOnAttack} tg={mockTg} reloadData={mockReloadData} />);
    
    // Click Jon Snow's castle
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    expect(screen.getByText('Розвідка')).toBeInTheDocument();
    
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, garrison: 500, message: 'Розвідка успішна' })
    });

    const scoutBtn = screen.getByText('Відправити розвідників', { selector: 'button' });
    fireEvent.click(scoutBtn);
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/scout', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ castle_id: 1, amount: 10 }) // default scout is 10
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('displays Crownlands correctly for King and Lords', () => {
    const { unmount } = render(<MapView state={baseState} me={me} onAttack={mockOnAttack} tg={mockTg} />);
    
    fireEvent.click(screen.getByText('Click Королівські Землі'));
    expect(screen.getByText('Залізний Трон')).toBeInTheDocument();
    expect(screen.getByText('Розпочати змову')).toBeInTheDocument();
    
    unmount();
    
    // King viewing Crownlands shouldn't see conspiracy
    const kingMe = { user_id: 2, role: 'king', army_size: 5000 };
    render(<MapView state={baseState} me={kingMe} onAttack={mockOnAttack} tg={mockTg} />);
    
    fireEvent.click(screen.getByText('Click Королівські Землі'));
    expect(screen.queryByText('Розпочати змову')).not.toBeInTheDocument();
  });

  it('allows starting conspiracy and confirming', async () => {
    render(<MapView state={baseState} me={me} onAttack={mockOnAttack} tg={mockTg} reloadData={mockReloadData} />);
    
    // Click Crownlands
    fireEvent.click(screen.getByText('Click Королівські Землі'));
    
    // Start conspiracy button
    const conspireBtn = screen.getByText('Розпочати змову', { selector: 'button' });
    fireEvent.click(conspireBtn);

    // Expect slider to appear
    expect(screen.getByText('Скільки воїнів надіслати? (мін. 70%)')).toBeInTheDocument();
    
    // Test cancel slider
    fireEvent.click(screen.getByText('Скасувати'));
    expect(screen.queryByText('Скільки воїнів надіслати? (мін. 70%)')).not.toBeInTheDocument();

    // Reopen slider
    fireEvent.click(screen.getByText('Розпочати змову', { selector: 'button' }));

    // Drag slider
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '1200' } });

    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Змова почалась' })
    });

    const confirmBtn = screen.getByText('Підтвердити', { selector: 'button' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockTg.showConfirm).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledWith('/api/conspiracy', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ amount: 1200 })
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });
  });

  it('allows king to demand castle', async () => {
    const kingMe = { user_id: 2, role: 'king', army_size: 5000 };
    render(<MapView state={baseState} me={kingMe} onAttack={mockOnAttack} tg={mockTg} />);
    
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    const demandBtn = screen.getByText('Вимагати замок', { selector: 'button' });
    
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Замок віддано' })
    });

    fireEvent.click(demandBtn);
    
    await waitFor(() => {
      expect(mockTg.showConfirm).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledWith('/api/order', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_id: 1, order_type: 'castle', value: 'Вінтерфелл' })
      }));
    });
  });

  it('allows scout amount changing and shows errors on scout', async () => {
    const anotherLord = { user_id: 3, role: 'lord', army_size: 1500 };
    render(<MapView state={baseState} me={anotherLord} onAttack={mockOnAttack} tg={mockTg} />);
    
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    const scoutSliders = screen.getAllByRole('slider');
    const scoutSlider = scoutSliders[0]; // Assuming first is scout if both are there, wait, attack slider is also there.
    
    // Change attack amount
    if(scoutSliders.length > 1) {
       fireEvent.change(scoutSliders[1], { target: { value: '200' } });
    }
    
    global.fetch.mockRejectedValueOnce(new Error('Network error'));
    
    const scoutBtn = screen.getByText('Відправити розвідників', { selector: 'button' });
    fireEvent.click(scoutBtn);
    
    await waitFor(() => {
      expect(mockTg.showAlert).toHaveBeenCalledWith("Помилка з'єднання під час розвідки");
    });
  });

  it('calls attack directly if scouted', async () => {
    const scoutedState = { ...baseState, scouted_castles: { 1: { garrison: 400, timestamp: Date.now() } } };
    const anotherLord = { user_id: 3, role: 'lord', army_size: 1500 };
    render(<MapView state={scoutedState} me={anotherLord} onAttack={mockOnAttack} tg={mockTg} />);
    
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    const attackBtn = screen.getByText('Штурм', { selector: 'button' });
    fireEvent.click(attackBtn);
    
    expect(mockTg.showConfirm).toHaveBeenCalled();
  });

  it('allows changing garrison and handles error gracefully', async () => {
    const myCastleState = {
      ...baseState,
      castles: [
        { id: 1, name: 'Вінтерфелл', garrison: 500, army_per_hour: 20, owner: { id: 1, name: 'Jon Snow' } },
      ]
    };
    const me = { user_id: 1, role: 'lord', army_size: 1000 };
    render(<MapView state={myCastleState} me={me} onAttack={mockOnAttack} tg={mockTg} reloadData={mockReloadData} />);
    
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    // Change garrison slider
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '200' } });

    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, message: 'Гарнізон оновлено' })
    });

    const confirmBtn = screen.getByText('Підтвердити', { selector: 'button' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/garrison', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ castle_id: 1, amount: 200 })
      }));
      expect(mockReloadData).toHaveBeenCalled();
    });

    // Reopen
    fireEvent.click(screen.getByText('Click Вінтерфелл'));
    
    // Test error
    const newSlider = screen.getByRole('slider');
    fireEvent.change(newSlider, { target: { value: '-100' } });
    mockTg.showAlert.mockClear();
    global.fetch.mockRejectedValueOnce(new Error('Network Error'));
    
    const newConfirmBtn = screen.getByText('Підтвердити', { selector: 'button' });
    fireEvent.click(newConfirmBtn);

    await waitFor(() => {
      expect(mockTg.showAlert).toHaveBeenCalledWith("Помилка з'єднання");
    });
  });

  it('handles error in conspiracy', async () => {
    const me = { user_id: 3, role: 'lord', army_size: 1500 };
    render(<MapView state={baseState} me={me} onAttack={mockOnAttack} tg={mockTg} />);
    
    fireEvent.click(screen.getByText('Click Королівські Землі'));
    
    fireEvent.click(screen.getByText('Розпочати змову', { selector: 'button' }));
    
    global.fetch.mockRejectedValueOnce(new Error('Network error'));

    const confirmBtn = screen.getByText('Підтвердити', { selector: 'button' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockTg.showAlert).toHaveBeenCalledWith("Помилка з'єднання");
    });
  });
});
