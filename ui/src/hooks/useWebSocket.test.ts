import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

describe('useWebSocket', () => {
  let mockWebSocket: any;

  beforeEach(() => {
    mockWebSocket = {
      send: vi.fn(),
      close: vi.fn(),
      readyState: WebSocket.OPEN,
    };
    
    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      send = mockWebSocket.send;
      close = mockWebSocket.close;
      readyState = mockWebSocket.readyState;
      onopen: any;
      onclose: any;
      onmessage: any;
      
      constructor(public url: string) {
        mockWebSocket.onopen = () => this.onopen?.();
        mockWebSocket.onmessage = (msg: any) => this.onmessage?.(msg);
      }
    }
    
    globalThis.WebSocket = MockWebSocket as any;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('connects to WebSocket and joins project', () => {
    renderHook(() => useWebSocket('test-project'));

    act(() => {
      mockWebSocket.onopen();
    });

    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'join_project', project_path: 'test-project' })
    );
  });

  it('updates workflow state on message without infinite renders', () => {
    const { result } = renderHook(() => useWebSocket('test-project'));

    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({
          type: 'workflow_state',
          project_path: 'test-project',
          new_state: 'planning',
          iteration: 1,
          time_in_state: 10,
          available_transitions: ['next'],
          nodes: [],
          edges: [],
        }),
      });
    });

    expect(result.current.workflow).toEqual({
      currentState: 'planning',
      iteration: 1,
      timeInState: 10,
      availableTransitions: ['next'],
      nodes: [],
      edges: [],
    });
  });
});
