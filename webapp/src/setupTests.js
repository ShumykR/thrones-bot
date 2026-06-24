import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Telegram WebApp
window.Telegram = {
  WebApp: {
    ready: vi.fn(),
    expand: vi.fn(),
    close: vi.fn(),
    showAlert: vi.fn(),
    showConfirm: vi.fn((msg, cb) => cb(true)),
    initData: "query_id=test",
    initDataUnsafe: {
      user: {
        id: 123456789,
        first_name: "TestUser",
        username: "testuser"
      }
    },
    MainButton: {
      show: vi.fn(),
      hide: vi.fn(),
      setParams: vi.fn(),
      onClick: vi.fn(),
      offClick: vi.fn(),
    },
    HapticFeedback: {
      impactOccurred: vi.fn(),
      selectionChanged: vi.fn(),
    },
    themeParams: {
      bg_color: "#ffffff",
      text_color: "#000000",
      button_color: "#3390ec",
      button_text_color: "#ffffff"
    }
  }
};

// Mock fetch globally
global.fetch = vi.fn();
