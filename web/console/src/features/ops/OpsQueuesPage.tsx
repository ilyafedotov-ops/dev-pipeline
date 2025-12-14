import { useState } from 'react';
import { Layers, Activity, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { LoadingState } from '@/components/ui/LoadingState';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, ColumnDef } from '@/components/DataTable';
import { useQueues, useQueueJobs } from './hooks';

export function OpsQueuesPage() {
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const { data: queueStats, isLoading: statsLoading, error: statsError } = useQueues();
  const { data: jobs, isLoading: jobsLoading, error: jobsError } = useQueueJobs(selectedStatus || undefined);

  if (statsLoading || jobsLoading) {
    return <LoadingState message="Loading queue data..." />;
  }

  if (statsError || jobsError) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600 mb-4">Failed to load queue data</p>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  const jobColumns: ColumnDef<any>[] = [
    {
      key: 'id',
      header: 'Job ID',
      cell: (id) => (
        <span className="font-mono text-xs text-fg">{id.slice(0, 12)}...</span>
      ),
      className: 'w-32',
    },
    {
      key: 'job_type',
      header: 'Type',
      cell: (type) => (
        <span className="rounded bg-bg-muted px-2 py-1 text-xs font-medium text-fg">
          {type}
        </span>
      ),
      className: 'w-48',
    },
    {
      key: 'queue',
      header: 'Queue',
      cell: (queue) => (
        <span className="text-sm text-fg-muted">{queue}</span>
      ),
      className: 'w-24',
    },
    {
      key: 'status',
      header: 'Status',
      cell: (status) => {
        const getStatusColor = (s: string) => {
          switch (s) {
            case 'queued': return 'text-gray-600';
            case 'started': return 'text-blue-600';
            case 'finished': return 'text-green-600';
            case 'failed': return 'text-red-600';
            default: return 'text-gray-600';
          }
        };
        return (
          <span className={`text-sm font-medium ${getStatusColor(status)}`}>
            {status}
          </span>
        );
      },
      className: 'w-24',
    },
    {
      key: 'worker_id',
      header: 'Worker',
      cell: (workerId) => (
        <span className="font-mono text-xs text-fg-muted">
          {workerId || '—'}
        </span>
      ),
      className: 'w-32',
    },
    {
      key: 'enqueued_at',
      header: 'Enqueued',
      cell: (timestamp) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) {
          return 'Just now';
        } else if (diffMins < 60) {
          return `${diffMins}m ago`;
        } else if (diffMins < 1440) {
          return `${Math.floor(diffMins / 60)}h ago`;
        } else {
          return date.toLocaleDateString();
        }
      },
      className: 'w-24',
    },
  ];

  const totalQueued = queueStats?.reduce((sum, q) => sum + q.queued, 0) || 0;
  const totalStarted = queueStats?.reduce((sum, q) => sum + q.started, 0) || 0;
  const totalFailed = queueStats?.reduce((sum, q) => sum + q.failed, 0) || 0;
  const totalJobs = queueStats?.reduce((sum, q) => sum + q.total, 0) || 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Queues</h1>
          <p className="text-gray-600">Queue statistics and job monitoring</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-fg-muted">Total Jobs</p>
              <p className="mt-2 text-3xl font-semibold text-fg">{totalJobs}</p>
            </div>
            <div className="rounded-lg bg-blue-50 p-3 text-blue-600">
              <Layers className="h-5 w-5" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-fg-muted">Queued</p>
              <p className="mt-2 text-3xl font-semibold text-gray-600">{totalQueued}</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-3 text-gray-600">
              <Clock className="h-5 w-5" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-fg-muted">Running</p>
              <p className="mt-2 text-3xl font-semibold text-blue-600">{totalStarted}</p>
            </div>
            <div className="rounded-lg bg-blue-50 p-3 text-blue-600">
              <Activity className="h-5 w-5" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-fg-muted">Failed</p>
              <p className="mt-2 text-3xl font-semibold text-red-600">{totalFailed}</p>
            </div>
            <div className="rounded-lg bg-red-50 p-3 text-red-600">
              <XCircle className="h-5 w-5" />
            </div>
          </div>
        </div>
      </div>

      {queueStats && queueStats.length > 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-6">
          <h2 className="text-lg font-semibold text-fg mb-4">Queue Statistics</h2>
          <div className="space-y-3">
            {queueStats.map((queue) => (
              <div key={queue.queue} className="rounded-md border border-border bg-bg-muted p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-fg">{queue.queue}</span>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-fg-muted">Total: <span className="font-medium text-fg">{queue.total}</span></span>
                    <span className="text-gray-600">Queued: <span className="font-medium">{queue.queued}</span></span>
                    <span className="text-blue-600">Running: <span className="font-medium">{queue.started}</span></span>
                    <span className="text-red-600">Failed: <span className="font-medium">{queue.failed}</span></span>
                  </div>
                </div>
                <div className="h-2 bg-bg-panel rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500"
                    style={{ width: `${queue.healthy_percentage}%` }}
                  />
                </div>
                <div className="mt-1 text-xs text-fg-muted">
                  Health: {queue.healthy_percentage.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-bg-panel p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-fg">Jobs</h2>
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm"
          >
            <option value="">All Statuses</option>
            <option value="queued">Queued</option>
            <option value="started">Started</option>
            <option value="finished">Finished</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        {jobs && jobs.length > 0 ? (
          <DataTable columns={jobColumns} data={jobs} />
        ) : (
          <EmptyState
            title="No jobs found"
            description="Jobs will appear here as they are enqueued and processed."
          />
        )}
      </div>
    </div>
  );
}
