/**
 * Recent Objects Component
 * Displays a list of recently created/updated objects
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Clock, Package } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ObjectSummary } from '@/lib/api-client';
import Link from 'next/link';

interface RecentObjectsProps {
  objects?: ObjectSummary[];
  loading?: boolean;
  className?: string;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function RecentObjects({ objects = [], loading = false, className }: RecentObjectsProps) {
  if (loading) {
    return (
      <Card className={cn(className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Recent Objects
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded bg-muted" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Recent Objects
        </CardTitle>
      </CardHeader>
      <CardContent>
        {objects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Package className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">No objects yet</p>
          </div>
        ) : (
          <ScrollArea className="h-[300px] pr-4">
            <div className="space-y-3">
              {objects.map((obj) => (
                <Link
                  key={obj.id}
                  href={`/objects?id=${obj.id}`}
                  className="block rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {obj.type_id}
                      </Badge>
                      <span className="font-medium truncate max-w-[150px]">
                        {(obj.data?.name as string) || obj.id}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatRelativeTime(obj.created_at)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground truncate">
                    ID: {obj.id}
                  </div>
                </Link>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

export default RecentObjects;
