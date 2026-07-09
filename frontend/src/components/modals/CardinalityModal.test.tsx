import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CardinalityModal } from './CardinalityModal';

describe('CardinalityModal', () => {
    it('renders a distinct count input with a dynamic aria-label', () => {
        const mockNode = {
            id: 'test-node',
            type: 'tableNode',
            position: { x: 0, y: 0 },
            data: {
                title: 'test_table',
                columns: [
                    { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true }
                ]
            }
        };

        render(
            <CardinalityModal
                isOpen={true}
                cardinalityNode={mockNode as any}
                nodes={[mockNode] as any}
                cardinalityRowCount="1000"
                setCardinalityRowCount={vi.fn()}
                cardinalityRowCountNumber={1000}
                cardinalityDistinctCounts={{}}
                cardinalityColumnSelections={{}}
                cardinalityRecommendations={[]}
                appliedCardinalitySignatures={{ names: new Set(), columns: new Set() }}
                onCloseCardinalityWizard={vi.fn()}
                onCardinalityTableChange={vi.fn()}
                onCardinalityColumnToggle={vi.fn()}
                onCardinalityDistinctCountChange={vi.fn()}
                onApplyCardinalityRecommendation={vi.fn()}
                parsePositiveInteger={vi.fn()}
                calculateCardinalityRatio={vi.fn()}
                formatPercent={(val) => `${val}%`}
                strengthLabel={vi.fn()}
            />
        );

        const input = screen.getByLabelText('1번째 컬럼 고유 값(Distinct) 수');
        expect(input).toBeInTheDocument();
        expect(input).toHaveAttribute('type', 'number');
    });
});
