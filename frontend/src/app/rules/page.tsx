/**
 * Rules Management Page
 * Visual JSONLogic rule builder and management interface
 */
'use client';

import { useState, useCallback } from 'react';
import { useRules } from '@/lib/hooks/use-api';
import { Rule } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Plus, 
  Trash2, 
  Edit2, 
  Network, 
  Play,
  Code,
  Eye,
  CheckCircle2,
  XCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

// JSONLogic Operator Types
type LogicOperator = '==' | '!=' | '>' | '<' | '>=' | '<=' | 'in' | 'and' | 'or' | 'not';

interface LogicCondition {
  id: string;
  operator: LogicOperator;
  variable?: string;
  value?: string | number | boolean;
  conditions?: LogicCondition[];
}

// Rule Builder Component
function RuleBuilder({
  initialRule,
  onSave,
  onCancel,
}: {
  initialRule?: Partial<Rule>;
  onSave: (rule: Partial<Rule>) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initialRule?.name || '');
  const [description, setDescription] = useState(initialRule?.description || '');
  const [conditions, setConditions] = useState<LogicCondition[]>([
    { id: '1', operator: '==', variable: '', value: '' }
  ]);
  const [actions, setActions] = useState<Array<{ type: string; value: string }>>([
    { type: 'log', value: '' }
  ]);
  const [jsonPreview, setJsonPreview] = useState('');

  const addCondition = () => {
    setConditions([...conditions, { id: Date.now().toString(), operator: '==', variable: '', value: '' }]);
  };

  const updateCondition = (id: string, updates: Partial<LogicCondition>) => {
    setConditions(conditions.map(c => c.id === id ? { ...c, ...updates } : c));
  };

  const removeCondition = (id: string) => {
    setConditions(conditions.filter(c => c.id !== id));
  };

  const addAction = () => {
    setActions([...actions, { type: 'log', value: '' }]);
  };

  const updateAction = (index: number, updates: Partial<{ type: string; value: string }>) => {
    setActions(actions.map((a, i) => i === index ? { ...a, ...updates } : a));
  };

  const removeAction = (index: number) => {
    setActions(actions.filter((_, i) => i !== index));
  };

  const buildJSONLogic = (): Record<string, unknown> => {
    if (conditions.length === 0) return {};
    if (conditions.length === 1) {
      const c = conditions[0];
      return { [c.operator]: [{ var: c.variable }, c.value] };
    }
    return {
      and: conditions.map(c => ({ [c.operator]: [{ var: c.variable }, c.value] }))
    };
  };

  const handlePreview = () => {
    const logic = buildJSONLogic();
    setJsonPreview(JSON.stringify({
      name,
      description,
      condition: logic,
      actions: actions.map(a => ({ [a.type]: a.value }))
    }, null, 2));
  };

  const handleSave = () => {
    onSave({
      name,
      description,
      condition: buildJSONLogic(),
      actions: actions.map(a => ({ type: a.type, value: a.value })),
      is_active: true,
    });
  };

  return (
    <div className="space-y-6">
      <Tabs defaultValue="builder" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="builder">Visual Builder</TabsTrigger>
          <TabsTrigger value="json" onClick={handlePreview}>JSON Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="builder" className="space-y-6">
          {/* Rule Info */}
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Rule Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Auto-assign High Priority Tasks"
              />
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this rule does..."
              />
            </div>
          </div>

          {/* Conditions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">When (Conditions)</CardTitle>
              <CardDescription>
                Define when this rule should trigger
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {conditions.map((condition, idx) => (
                <div key={condition.id} className="flex gap-2 items-start">
                  <div className="flex-1 grid grid-cols-3 gap-2">
                    <Input
                      placeholder="Variable (e.g., priority)"
                      value={condition.variable}
                      onChange={(e) => updateCondition(condition.id, { variable: e.target.value })}
                    />
                    <Select
                      value={condition.operator}
                      onValueChange={(v) => updateCondition(condition.id, { operator: v as LogicOperator })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="==">equals</SelectItem>
                        <SelectItem value="!=">not equals</SelectItem>
                        <SelectItem value=">">greater than</SelectItem>
                        <SelectItem value="<">less than</SelectItem>
                        <SelectItem value=">=">greater or equal</SelectItem>
                        <SelectItem value="<=">less or equal</SelectItem>
                        <SelectItem value="in">contains</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      placeholder="Value"
                      value={condition.value as string}
                      onChange={(e) => updateCondition(condition.id, { value: e.target.value })}
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeCondition(condition.id)}
                    disabled={conditions.length === 1}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <Button variant="outline" onClick={addCondition} className="w-full">
                <Plus className="h-4 w-4 mr-2" />
                Add Condition
              </Button>
            </CardContent>
          </Card>

          {/* Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Then (Actions)</CardTitle>
              <CardDescription>
                Define what happens when conditions are met
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {actions.map((action, idx) => (
                <div key={idx} className="flex gap-2 items-start">
                  <div className="flex-1 grid grid-cols-2 gap-2">
                    <Select
                      value={action.type}
                      onValueChange={(v) => updateAction(idx, { type: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="log">Log Message</SelectItem>
                        <SelectItem value="notify">Send Notification</SelectItem>
                        <SelectItem value="assign">Assign To</SelectItem>
                        <SelectItem value="update">Update Field</SelectItem>
                        <SelectItem value="webhook">Call Webhook</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      placeholder="Action value"
                      value={action.value}
                      onChange={(e) => updateAction(idx, { value: e.target.value })}
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeAction(idx)}
                    disabled={actions.length === 1}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <Button variant="outline" onClick={addAction} className="w-full">
                <Plus className="h-4 w-4 mr-2" />
                Add Action
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="json">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">JSONLogic Output</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted p-4 rounded-lg text-xs overflow-auto max-h-[400px]">
                {jsonPreview || 'Click to generate preview'}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Footer */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={!name}>
          Save Rule
        </Button>
      </div>
    </div>
  );
}

// Rule Card Component
function RuleCard({
  rule,
  onToggle,
  onEdit,
  onDelete,
}: {
  rule: Rule;
  onToggle: (id: string, active: boolean) => void;
  onEdit: (rule: Rule) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <Card className={cn(!rule.is_active && "opacity-60")}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">{rule.name}</CardTitle>
              {rule.is_active ? (
                <Badge variant="default" className="text-xs">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Active
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-xs">
                  <XCircle className="h-3 w-3 mr-1" />
                  Inactive
                </Badge>
              )}
            </div>
            {rule.description && (
              <CardDescription className="mt-1">{rule.description}</CardDescription>
            )}
          </div>
          <Switch
            checked={rule.is_active}
            onCheckedChange={(checked) => onToggle(rule.id, checked)}
          />
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2">
          <div className="text-xs">
            <span className="text-muted-foreground">Conditions:</span>
            <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-x-auto">
              {JSON.stringify(rule.condition, null, 2)}
            </pre>
          </div>
          <div className="text-xs">
            <span className="text-muted-foreground">Actions:</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {rule.actions.map((action, idx) => (
                <Badge key={idx} variant="outline" className="text-xs">
                  {action.type}
                </Badge>
              ))}
            </div>
          </div>
        </div>
        
        <div className="flex gap-2 mt-4">
          <Button variant="outline" size="sm" className="flex-1" onClick={() => onEdit(rule)}>
            <Edit2 className="h-3 w-3 mr-1" />
            Edit
          </Button>
          <Button variant="outline" size="sm" className="flex-1" onClick={() => onDelete(rule.id)}>
            <Trash2 className="h-3 w-3 mr-1" />
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function RulesPage() {
  const { data: rules, loading, error, toggleRule, deleteRule, refetch } = useRules();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);

  const handleSaveRule = useCallback((ruleData: Partial<Rule>) => {
    // In production, this would call the API
    console.log('Saving rule:', ruleData);
    setDialogOpen(false);
    setEditingRule(null);
    refetch();
  }, [refetch]);

  const handleEdit = useCallback((rule: Rule) => {
    setEditingRule(rule);
    setDialogOpen(true);
  }, []);

  const handleNewRule = useCallback(() => {
    setEditingRule(null);
    setDialogOpen(true);
  }, []);

  const handleCancel = useCallback(() => {
    setDialogOpen(false);
    setEditingRule(null);
  }, []);

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Automation Rules</h1>
          <p className="text-muted-foreground mt-1">
            Create and manage rules to automate your workflows
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={handleNewRule}>
              <Plus className="h-4 w-4 mr-2" />
              New Rule
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingRule ? 'Edit Rule' : 'Create New Rule'}</DialogTitle>
              <DialogDescription>
                Build automation rules using the visual JSONLogic builder
              </DialogDescription>
            </DialogHeader>
            <RuleBuilder
              initialRule={editingRule || undefined}
              onSave={handleSaveRule}
              onCancel={handleCancel}
            />
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Rules</CardTitle>
            <Network className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rules?.length ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
            <Play className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {rules?.filter(r => r.is_active).length ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Inactive</CardTitle>
            <Code className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">
              {rules?.filter(r => !r.is_active).length ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Executions Today</CardTitle>
            <Eye className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">-</div>
          </CardContent>
        </Card>
      </div>

      {/* Rules List */}
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-[300px]">
              <CardContent className="p-6 space-y-4">
                <div className="h-6 w-3/4 animate-pulse rounded bg-muted" />
                <div className="h-4 w-full animate-pulse rounded bg-muted" />
                <div className="h-24 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card className="p-8 text-center">
          <p className="text-destructive">Failed to load rules</p>
          <Button variant="outline" className="mt-4" onClick={refetch}>
            Retry
          </Button>
        </Card>
      ) : rules?.length === 0 ? (
        <Card className="p-12 text-center">
          <Network className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold">No rules yet</h3>
          <p className="text-muted-foreground mt-1 mb-4">
            Create your first automation rule to get started
          </p>
          <Button onClick={handleNewRule}>
            <Plus className="h-4 w-4 mr-2" />
            Create Rule
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {rules.map((rule) => (
            <RuleCard
              key={rule.id}
              rule={rule}
              onToggle={toggleRule}
              onEdit={handleEdit}
              onDelete={deleteRule}
            />
          ))}
        </div>
      )}
    </div>
  );
}
