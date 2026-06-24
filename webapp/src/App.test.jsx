import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import App from './App';

describe('App component', () => {
  vi.mock('./components/MapSvg', () => ({
    default: ({ onCastleClick }) => (
      <div data-testid="map-svg-mock">
        <button onClick={() => onCastleClick({ id: 1, name: 'Вінтерфелл', garrison: 500, owner: { id: 4 } })}>Click Вінтерфелл</button>
        <button onClick={() => onCastleClick({ id: 1, name: 'Північ', garrison: 500, owner: { id: 1 } })}>Click Північ</button>
      </div>
    )
  }));

  beforeEach(() => {
    vi.clearAllMocks();
    window.Telegram.WebApp.initData = 'query_id=test';
    
    // Setup mock fetch for the two API calls in fetchData
    global.fetch.mockImplementation((url) => {
      if (url === '/api/me') {
        return Promise.resolve({
          json: () => Promise.resolve({ user_id: 1, first_name: 'Jon Snow', role: 'lord', army_size: 1500, castles_count: 1 })
        });
      }
      if (url === '/api/state') {
        return Promise.resolve({
          json: () => Promise.resolve({
            king: { id: 2, name: 'Cersei Lannister', role: 'king' },
            users: [
              { id: 1, name: 'Jon Snow', role: 'lord' },
              { id: 2, name: 'Cersei Lannister', role: 'king' }
            ],
            castles: [
              { id: 1, name: 'Вінтерфелл', garrison: 500, army_per_hour: 20, owner: { id: 1, name: 'Jon Snow' } },
              { id: 2, name: 'Королівська Гавань', garrison: 1200, army_per_hour: 50, owner: { id: 2, name: 'Cersei Lannister' } }
            ],
            conspiracy: null,
            scouted_castles: {}
          })
        });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
  });

  it('renders loading state initially', () => {
    // Override fetch to never resolve so loading state stays
    global.fetch.mockImplementation(() => new Promise(() => {}));
    const { container } = render(<App />);
    expect(container.querySelector('.loading-overlay')).toBeInTheDocument();
  });

  it('renders map with castles after loading', async () => {
    const { container } = render(<App />);
    
    // Wait for the app-container to load
    await waitFor(() => {
      expect(container.querySelector('.app-container')).toBeInTheDocument();
    });

    // Check that nav bar is rendered
    expect(container.querySelector('.nav-bar')).toBeInTheDocument();
    expect(screen.getByText('Карта')).toBeInTheDocument();
    
    // Check that MapSvg is rendered
    expect(container.querySelector('.map-container')).toBeInTheDocument();
  });

  it('renders auth error when user is not found', async () => {
    global.fetch.mockImplementation((url) => {
      if (url === '/api/me') {
        return Promise.resolve({ json: () => Promise.resolve({ error: "User not found" }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({ error: "State error" }) });
    });
    
    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByText('Помилка авторизації')).toBeInTheDocument();
    });
    
    // Test the close button
    const closeBtn = screen.getByText('Закрити');
    closeBtn.click();
  });

  it('navigates through tabs', async () => {
    const { container } = render(<App />);
    
    await waitFor(() => {
      expect(container.querySelector('.app-container')).toBeInTheDocument();
    });

    // Click on Profile tab
    const profileTab = screen.getByText('Профіль').closest('.nav-item');
    fireEvent.click(profileTab);
    
    await waitFor(() => {
      expect(screen.getByText('Jon Snow')).toBeInTheDocument();
      expect(screen.queryByText('Карта')).toBeInTheDocument(); // Map tab still exists
    });

    // Click on Throne tab
    const throneTab = screen.getByText('Трон').closest('.nav-item');
    fireEvent.click(throneTab);
    
    await waitFor(() => {
      expect(screen.getByText(/Залізний Трон/i)).toBeInTheDocument();
    });

    // Click on Map tab
    const mapTab = screen.getByText('Карта').closest('.nav-item');
    fireEvent.click(mapTab);
    
    await waitFor(() => {
      expect(container.querySelector('.map-container')).toBeInTheDocument();
    });
  });

  it('uses mock data when not initialized via Telegram', async () => {
    // Override tg to be null or initData to be empty
    window.Telegram.WebApp.initData = '';
    
    const { container } = render(<App />);
    
    // It should load mock data after 1 second timeout
    await waitFor(() => {
      expect(screen.getByText(/Північ/)).toBeInTheDocument(); // From mock data
    }, { timeout: 1500 });
    
    // Now trigger an attack which should just alert
    const windowSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    
    const mapTab = screen.getByText('Карта').closest('.nav-item');
    fireEvent.click(mapTab);
    
    // We are on map, click on castle
    const mapBtn = screen.getByText(/Вінтерфелл/, { selector: 'button' });
    fireEvent.click(mapBtn);

    const attackBtn = screen.getByText('Штурм', { selector: 'button' });
    fireEvent.click(attackBtn);
    
    expect(windowSpy).toHaveBeenCalledWith('Attacking castle 1 with 100');
    windowSpy.mockRestore();
  });

  it('handles attack API call successfully', async () => {
    window.Telegram.WebApp.initData = 'test';
    const mockShowAlert = window.Telegram.WebApp.showAlert;
    
    global.fetch.mockImplementation((url, options) => {
      if (url === '/api/attack') {
        return Promise.resolve({ json: () => Promise.resolve({ success: true }) });
      }
      if (url === '/api/me') {
        return Promise.resolve({ json: () => Promise.resolve({ user_id: 2, first_name: 'Jon', role: 'lord', army_size: 1500 }) });
      }
      if (url === '/api/state') {
        return Promise.resolve({
          json: () => Promise.resolve({
            king: { id: 3 },
            users: [{ id: 2, name: 'Jon', role: 'lord' }],
            castles: [{ id: 1, name: 'Вінтерфелл', garrison: 500, owner: { id: 4 } }],
            config: { min_attack_army: 100 }
          })
        });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });

    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByText('Click Вінтерфелл')).toBeInTheDocument();
    });

    const castleBtn = screen.getByText('Click Вінтерфелл', { selector: 'button' });
    fireEvent.click(castleBtn);

    const attackBtn = screen.getByText('Штурм', { selector: 'button' });
    fireEvent.click(attackBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/attack', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ castle_id: 1, amount: 100 })
      }));
      expect(mockShowAlert).toHaveBeenCalledWith("Війська вирушили на штурм!");
    });
  });

  it('handles attack API call error', async () => {
    window.Telegram.WebApp.initData = 'test';
    const mockShowAlert = window.Telegram.WebApp.showAlert;
    
    global.fetch.mockImplementation((url, options) => {
      if (url === '/api/attack') {
        return Promise.resolve({ json: () => Promise.resolve({ success: false, error: 'Not enough troops' }) });
      }
      if (url === '/api/me') {
        return Promise.resolve({ json: () => Promise.resolve({ user_id: 2, first_name: 'Jon', role: 'lord', army_size: 1500 }) });
      }
      if (url === '/api/state') {
        return Promise.resolve({
          json: () => Promise.resolve({
            king: { id: 3 },
            users: [{ id: 2, name: 'Jon', role: 'lord' }],
            castles: [{ id: 1, name: 'Вінтерфелл', garrison: 500, owner: { id: 4 } }],
            config: { min_attack_army: 100 }
          })
        });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });

    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByText('Click Вінтерфелл')).toBeInTheDocument();
    });

    const castleBtn = screen.getByText('Click Вінтерфелл', { selector: 'button' });
    fireEvent.click(castleBtn);

    const attackBtn = screen.getByText('Штурм', { selector: 'button' });
    fireEvent.click(attackBtn);

    await waitFor(() => {
      expect(mockShowAlert).toHaveBeenCalledWith("Помилка: Not enough troops");
    });
  });
});
