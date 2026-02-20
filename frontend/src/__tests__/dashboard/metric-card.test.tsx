/**
 * MetricCard Component Tests
 */
import { render, screen } from '@/lib/test-utils';
import { MetricCard } from '@/components/dashboard/metric-card';
import { Activity } from 'lucide-react';

describe('MetricCard', () => {
  it('renders with title and value', () => {
    render(
      <MetricCard
        title="Test Metric"
        value={42}
        icon={Activity}
      />
    );

    expect(screen.getByText('Test Metric')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders with description', () => {
    render(
      <MetricCard
        title="Test Metric"
        value={100}
        description="This is a description"
        icon={Activity}
      />
    );

    expect(screen.getByText('This is a description')).toBeInTheDocument();
  });

  it('renders with trend indicator', () => {
    render(
      <MetricCard
        title="Test Metric"
        value={100}
        trend={{ value: 10, isPositive: true }}
        icon={Activity}
      />
    );

    expect(screen.getByText('↑ 10%')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(
      <MetricCard
        title="Test Metric"
        value={0}
        loading={true}
        icon={Activity}
      />
    );

    // Check for loading animation elements
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('renders negative trend correctly', () => {
    render(
      <MetricCard
        title="Test Metric"
        value={100}
        trend={{ value: 5, isPositive: false }}
        icon={Activity}
      />
    );

    expect(screen.getByText('↓ 5%')).toBeInTheDocument();
  });
});
