
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
import App from '../../App';

vi.mock('../../api', () => ({
  getMe: vi.fn().mockResolvedValue({ subject: 'test-user', display_name: 'Test User' }),
  listProjects: vi.fn().mockResolvedValue([]),
  listConnections: vi.fn().mockResolvedValue([]),
  listSnapshots: vi.fn().mockResolvedValue([]),
}));

describe('App edit functionality', () => {
    it('renders without crashing', () => {
        render(<App />);
        expect(screen.getByText('pg-erd-cloud')).toBeInTheDocument();
    });
});
