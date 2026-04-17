import { render } from '@testing-library/react';
import { WorkflowGraph } from './WorkflowGraph';
import { describe, it, expect } from 'vitest';
import { WorkflowState } from '../types';

describe('WorkflowGraph', () => {
  it('renders awaiting state when workflow is null', () => {
    const { getByText } = render(<WorkflowGraph workflow={null} />);
    expect(getByText('Awaiting Selection')).toBeInTheDocument();
  });

  it('renders workflow state and does not throw', () => {
    const workflow: WorkflowState = {
      currentState: 'planning',
      iteration: 1,
      timeInState: 10,
      availableTransitions: [],
      nodes: [
        { name: 'idle', isActive: false, isCompleted: true, position: [0, 0] },
        { name: 'planning', isActive: true, isCompleted: false, position: [100, 0] }
      ],
      edges: [],
    };
    
    const { getAllByText, getByTestId } = render(<WorkflowGraph workflow={workflow} />);
    expect(getAllByText('planning')[0]).toBeInTheDocument();
    expect(getByTestId('workflow-iteration')).toHaveTextContent('1');
  });
});
