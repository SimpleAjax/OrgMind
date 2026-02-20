/**
 * Object Explorer Page
 * Searchable, filterable table for viewing and managing objects
 */
'use client';

import { useState, useCallback } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '@/components/data-table';
import { useObjects, useObject } from '@/lib/hooks/use-api';
import { ObjectSummary } from '@/lib/api-client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, Plus, Package, Edit2, Trash2 } from 'lucide-react';
import { useSearchParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

// Columns definition for the data table
const columns: ColumnDef<ObjectSummary>[] = [
  {
    accessorKey: 'id',
    header: 'ID',
    cell: ({ row }) => (
      <span className="font-mono text-xs truncate max-w-[150px] block">
        {row.getValue('id')}
      </span>
    ),
  },
  {
    accessorKey: 'type_id',
    header: 'Type',
    cell: ({ row }) => (
      <Badge variant="outline">{row.getValue('type_id')}</Badge>
    ),
  },
  {
    accessorKey: 'data.name',
    header: 'Name',
    cell: ({ row }) => {
      const data = row.original.data;
      return (
        <span className="font-medium">
          {(data?.name as string) || '(unnamed)'}
        </span>
      );
    },
  },
  {
    accessorKey: 'created_at',
    header: 'Created',
    cell: ({ row }) => {
      const date = new Date(row.getValue('created_at'));
      return date.toLocaleDateString();
    },
  },
  {
    accessorKey: 'created_by',
    header: 'Created By',
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {row.getValue('created_by')}
      </span>
    ),
  },
];

// Object Detail Sheet Component
function ObjectDetailSheet({
  objectId,
  open,
  onOpenChange,
}: {
  objectId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: object, loading } = useObject(objectId);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[500px] sm:max-w-[500px]">
        <SheetHeader>
          <SheetTitle>Object Details</SheetTitle>
          <SheetDescription>
            View and edit object properties
          </SheetDescription>
        </SheetHeader>
        
        {loading ? (
          <div className="mt-8 space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : object ? (
          <ScrollArea className="h-[calc(100vh-200px)] mt-6 pr-4">
            <div className="space-y-6">
              <div>
                <Label className="text-muted-foreground">ID</Label>
                <p className="font-mono text-sm mt-1">{object.id}</p>
              </div>
              
              <div>
                <Label className="text-muted-foreground">Type</Label>
                <div className="mt-1">
                  <Badge variant="outline">{object.type_id}</Badge>
                </div>
              </div>
              
              <div>
                <Label className="text-muted-foreground">Created</Label>
                <p className="text-sm mt-1">
                  {new Date(object.created_at).toLocaleString()}
                </p>
              </div>
              
              <div>
                <Label className="text-muted-foreground">Updated</Label>
                <p className="text-sm mt-1">
                  {new Date(object.updated_at).toLocaleString()}
                </p>
              </div>
              
              <div>
                <Label className="text-muted-foreground">Data</Label>
                <pre className="mt-2 p-4 bg-muted rounded-lg text-xs overflow-auto">
                  {JSON.stringify(object.data, null, 2)}
                </pre>
              </div>
            </div>
          </ScrollArea>
        ) : (
          <div className="mt-8 text-center text-muted-foreground">
            Object not found
          </div>
        )}
        
        <div className="absolute bottom-0 left-0 right-0 p-6 border-t bg-background">
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1">
              <Edit2 className="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button variant="destructive" className="flex-1">
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function ObjectsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get('id');
  
  const { data: objects, loading, error, refetch } = useObjects(100, 0);
  const [detailOpen, setDetailOpen] = useState(!!selectedId);

  const handleRowClick = useCallback((row: ObjectSummary) => {
    router.push(`/objects?id=${row.id}`);
    setDetailOpen(true);
  }, [router]);

  const handleDetailOpenChange = useCallback((open: boolean) => {
    setDetailOpen(open);
    if (!open) {
      router.push('/objects');
    }
  }, [router]);

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Object Explorer</h1>
          <p className="text-muted-foreground mt-1">
            Browse, search, and manage all objects in the system
          </p>
        </div>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          New Object
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Objects</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{objects?.length ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              Across all types
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Types</CardTitle>
            <Search className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {new Set(objects?.map(o => o.type_id)).size ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Unique object types
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recently Added</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {objects?.filter(o => {
                const date = new Date(o.created_at);
                const weekAgo = new Date();
                weekAgo.setDate(weekAgo.getDate() - 7);
                return date > weekAgo;
              }).length ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              In the last 7 days
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Data Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Objects</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="text-center py-8 text-destructive">
              <p>Failed to load objects</p>
              <Button variant="outline" className="mt-4" onClick={refetch}>
                Retry
              </Button>
            </div>
          ) : (
            <DataTable
              columns={columns}
              data={objects || []}
              loading={loading}
              searchPlaceholder="Search by name, type, or ID..."
              onRowClick={handleRowClick}
            />
          )}
        </CardContent>
      </Card>

      {/* Object Detail Sheet */}
      <ObjectDetailSheet
        objectId={selectedId}
        open={detailOpen}
        onOpenChange={handleDetailOpenChange}
      />
    </div>
  );
}
