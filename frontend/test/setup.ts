import { vi, type Mock } from 'vitest';
import type { LovelaceCard } from '../src/types';
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
vi.stubGlobal('ResizeObserver', ResizeObserverMock);

// Mock for Home Assistant helpers
interface TestWindow extends Window {
  loadCardHelpers: Mock;
}

// Not every suite needs a DOM: the stylesheet test runs in the node
// environment, where touching `window` at all would throw.
if (typeof window !== 'undefined') {
  window.customCards = [];

  const testWindow = window as unknown as TestWindow;
  testWindow.loadCardHelpers = vi.fn().mockResolvedValue({
    createCardElement: vi.fn().mockResolvedValue({
      constructor: { getConfigElement: vi.fn().mockResolvedValue(undefined) },
    } as unknown as LovelaceCard),
  });
}
