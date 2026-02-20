/**
 * Metric Card Component
 * Displays a single dashboard metric with icon and trend
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: number | string;
  description?: string;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
  loading?: boolean;
}

export function MetricCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  className,
  loading = false,
}: MetricCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            <div className="h-4 w-32 animate-pulse rounded bg-muted" />
          </div>
        ) : (
          <>
            <div className="text-2xl font-bold">{value}</div>
            {(description || trend) && (
              <p className="text-xs text-muted-foreground">
                {trend && (
                  <span
                    className={cn(
                      'mr-1',
                      trend.isPositive ? 'text-green-600' : 'text-red-600'
                    )}
                  >
                    {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
                  </span>
                )}
                {description}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default MetricCard;
