/**
 * System Health Status Component
 * Displays the overall system health with component breakdown
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, Activity, Database, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';
import { HealthStatus as HealthStatusType } from '@/lib/api-client';

interface HealthStatusProps {
  status?: HealthStatusType;
  loading?: boolean;
  className?: string;
}

export function HealthStatus({ status, loading = false, className }: HealthStatusProps) {
  if (loading) {
    return (
      <Card className={cn(className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-muted" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card className={cn(className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Health status unavailable</p>
        </CardContent>
      </Card>
    );
  }

  const isHealthy = status.status === 'ready';

  const components = [
    { name: 'API', status: isHealthy ? 'healthy' : 'unhealthy', icon: Activity },
    { name: 'PostgreSQL', status: status.checks.postgres, icon: Database },
    { name: 'NATS', status: status.checks.nats, icon: Radio },
  ];

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Health
          </div>
          <Badge variant={isHealthy ? 'default' : 'destructive'}>
            {isHealthy ? 'Ready' : 'Not Ready'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {components.map((component) => {
            const isComponentHealthy = component.status === 'healthy';
            const Icon = component.icon;
            return (
              <div
                key={component.name}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{component.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {isComponentHealthy ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span
                    className={cn(
                      'text-sm capitalize',
                      isComponentHealthy ? 'text-green-600' : 'text-red-600'
                    )}
                  >
                    {component.status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4 text-xs text-muted-foreground">
          Version: {status.version}
        </div>
      </CardContent>
    </Card>
  );
}

export default HealthStatus;
