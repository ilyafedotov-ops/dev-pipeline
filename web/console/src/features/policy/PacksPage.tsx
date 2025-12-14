import { useState } from 'react';
import { Shield, Plus, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { LoadingState } from '@/components/ui/LoadingState';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, ColumnDef } from '@/components/DataTable';
import { usePolicyPacks, useCreatePolicyPack } from './hooks';
import { toast } from 'sonner';

export function PolicyPacksPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const { data: packs, isLoading, error } = usePolicyPacks();
  const createPack = useCreatePolicyPack();

  const [formData, setFormData] = useState({
    key: '',
    version: '1.0.0',
    name: '',
    description: '',
    pack: '{}',
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const packData = JSON.parse(formData.pack);
      await createPack.mutateAsync({
        ...formData,
        pack: packData,
      });
      toast.success('Policy pack created successfully');
      setShowCreateForm(false);
      setFormData({
        key: '',
        version: '1.0.0',
        name: '',
        description: '',
        pack: '{}',
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create policy pack');
    }
  };

  if (isLoading) {
    return <LoadingState message="Loading policy packs..." />;
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600 mb-4">Failed to load policy packs</p>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  const columns: ColumnDef<any>[] = [
    {
      key: 'id',
      header: 'ID',
      cell: (id) => (
        <span className="font-mono text-xs text-fg-muted">#{id}</span>
      ),
      className: 'w-16',
    },
    {
      key: 'key',
      header: 'Key',
      cell: (key) => (
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-fg-muted" />
          <span className="font-medium text-fg">{key}</span>
        </div>
      ),
      className: 'w-48',
    },
    {
      key: 'name',
      header: 'Name',
      cell: (name, row) => (
        <div>
          <div className="font-medium text-fg">{name}</div>
          {row.description && (
            <p className="mt-1 text-xs text-fg-muted line-clamp-1">{row.description}</p>
          )}
        </div>
      ),
    },
    {
      key: 'version',
      header: 'Version',
      cell: (version) => (
        <span className="rounded bg-bg-muted px-2 py-1 text-xs font-medium text-fg">
          {version}
        </span>
      ),
      className: 'w-24',
    },
    {
      key: 'status',
      header: 'Status',
      cell: (status) => {
        const isActive = status === 'active';
        return (
          <div className="flex items-center gap-1">
            {isActive ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <AlertCircle className="h-4 w-4 text-gray-400" />
            )}
            <span className={`text-sm ${isActive ? 'text-green-600' : 'text-fg-muted'}`}>
              {status}
            </span>
          </div>
        );
      },
      className: 'w-32',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Policy Packs</h1>
          <p className="text-gray-600">Manage policy packs and governance rules</p>
        </div>
        <Button onClick={() => setShowCreateForm(!showCreateForm)} variant="primary">
          <Plus className="h-4 w-4 mr-2" />
          Create Policy Pack
        </Button>
      </div>

      {showCreateForm && (
        <div className="rounded-lg border border-border bg-bg-panel p-6">
          <h2 className="text-lg font-semibold text-fg mb-4">Create New Policy Pack</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-fg mb-1">
                  Key
                </label>
                <input
                  type="text"
                  value={formData.key}
                  onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                  className="w-full rounded-md border border-border bg-bg-muted px-3 py-2 text-sm"
                  placeholder="e.g., default-policy"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg mb-1">
                  Version
                </label>
                <input
                  type="text"
                  value={formData.version}
                  onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                  className="w-full rounded-md border border-border bg-bg-muted px-3 py-2 text-sm"
                  placeholder="1.0.0"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-fg mb-1">
                Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full rounded-md border border-border bg-bg-muted px-3 py-2 text-sm"
                placeholder="Default Policy Pack"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-fg mb-1">
                Description
              </label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full rounded-md border border-border bg-bg-muted px-3 py-2 text-sm"
                placeholder="Optional description"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-fg mb-1">
                Policy Definition (JSON)
              </label>
              <textarea
                value={formData.pack}
                onChange={(e) => setFormData({ ...formData, pack: e.target.value })}
                className="w-full h-32 rounded-md border border-border bg-bg-muted px-3 py-2 text-sm font-mono"
                placeholder='{"defaults": {"models": {"exec": "codex-5.1-max"}}}'
                required
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" disabled={createPack.isPending}>
                {createPack.isPending ? 'Creating...' : 'Create'}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setShowCreateForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {packs && packs.length > 0 ? (
        <>
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-fg-muted" />
              <span className="text-fg-muted">Total Packs:</span>
              <span className="font-medium text-fg">{packs.length}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-fg-muted">Active:</span>
              <span className="font-medium text-green-600">
                {packs.filter((p) => p.status === 'active').length}
              </span>
            </div>
          </div>
          <DataTable columns={columns} data={packs} />
        </>
      ) : (
        <EmptyState
          title="No policy packs yet"
          description="Create your first policy pack to enforce governance rules across your projects."
          icon={<Shield className="h-12 w-12 text-gray-400" />}
          action={
            <Button onClick={() => setShowCreateForm(true)} variant="primary">
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Policy Pack
            </Button>
          }
        />
      )}
    </div>
  );
}
