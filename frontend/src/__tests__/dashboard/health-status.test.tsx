/**
 * HealthStatus Component Tests
 */
import { render, screen } from '@/lib/test-utils';
import { HealthStatus } from '@/components/dashboard/health-status';
import { HealthStatus as HealthStatusType } from '@/lib/api-client';

describe('HealthStatus', () => {
  const mockHealthyStatus: HealthStatusType = {
    status: 'ready',
    version: '1.0.0',
    checks: {
      postgres: 'healthy',
      nats: 'healthy',
    },
  };

  const mockUnhealthyStatus: HealthStatusType = {
    status: 'not_ready',
    version: '1.0.0',
    checks: {
      postgres: 'unhealthy',
      nats: 'healthy',
    },
  };

  it('renders loading state', () => {
    render(<HealthStatus loading={true} />);
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('renders healthy status correctly', () => {
    render(<HealthStatus status={mockHealthyStatus} />);

    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
    expect(screen.getByText('NATS')).toBeInTheDocument();
  });

  it('renders unhealthy status correctly', () => {
    render(<HealthStatus status={mockUnhealthyStatus} />);

    expect(screen.getByText('Not Ready')).toBeInTheDocument();
    expect(screen.getByText('unhealthy')).toBeInTheDocument();
  });

  it('displays version information', () => {
    render(<HealthStatus status={mockHealthyStatus} />);

    expect(screen.getByText(/Version: 1.0.0/)).toBeInTheDocument();
  });

  it('handles missing status gracefully', () => {
    render(<HealthStatus status={undefined} />);

    expect(screen.getByText('Health status unavailable')).toBeInTheDocument();
  });
});
