/**
 * Dashboard Metrics Hook
 * Fetches and combines all dashboard data
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { api, HealthStatus, ObjectSummary } from '@/lib/api-client';

interface DashboardMetrics {
  objectCount: number;
  typeCount: number;
  ruleCount: number;
  agentCount: number;
  recentObjects: ObjectSummary[];
  systemHealth: HealthStatus;
}

interface UseDashboardMetricsReturn {
  metrics: DashboardMetrics | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useDashboardMetrics(): UseDashboardMetricsReturn {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const [health, objects, types, rules, agents] = await Promise.all([
        api.health.check(),
        api.objects.list(5, 0),
        api.types.list(),
        api.rules.list(),
        api.agents.list(),
      ]);

      setMetrics({
        objectCount: objects.length,
        typeCount: types.length,
        ruleCount: rules.length,
        agentCount: agents.length,
        recentObjects: objects,
        systemHealth: health,
      });
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch dashboard metrics'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return { metrics, loading, error, refetch: fetchMetrics };
}

export default useDashboardMetrics;
