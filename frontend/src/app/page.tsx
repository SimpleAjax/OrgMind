/**
 * Dashboard Page
 * Main dashboard with system metrics, health status, and recent activity
 */
'use client';

import { MetricCard } from '@/components/dashboard/metric-card';
import { HealthStatus } from '@/components/dashboard/health-status';
import { RecentObjects } from '@/components/dashboard/recent-objects';
import { useDashboardMetrics } from '@/components/dashboard/use-dashboard-metrics';
import { 
  Package, 
  Layers, 
  Network, 
  Bot,
  Activity 
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

export default function DashboardPage() {
  const { metrics, loading, error, refetch } = useDashboardMetrics();

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            System overview and key metrics
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refetch}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <Activity className="h-4 w-4" />
          <AlertTitle>Error loading dashboard</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      {/* Metric Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Objects"
          value={metrics?.objectCount ?? 0}
          description="Objects in system"
          icon={Package}
          loading={loading}
        />
        <MetricCard
          title="Object Types"
          value={metrics?.typeCount ?? 0}
          description="Defined schemas"
          icon={Layers}
          loading={loading}
        />
        <MetricCard
          title="Active Rules"
          value={metrics?.ruleCount ?? 0}
          description="Automation rules"
          icon={Network}
          loading={loading}
        />
        <MetricCard
          title="Agents"
          value={metrics?.agentCount ?? 0}
          description="AI assistants"
          icon={Bot}
          loading={loading}
        />
      </div>

      {/* Secondary Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <HealthStatus
          status={metrics?.systemHealth}
          loading={loading}
          className="lg:col-span-3"
        />
        <RecentObjects
          objects={metrics?.recentObjects}
          loading={loading}
          className="lg:col-span-4"
        />
      </div>
    </div>
  );
}
