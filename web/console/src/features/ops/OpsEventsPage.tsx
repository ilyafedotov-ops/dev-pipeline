import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Clock, Activity, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { LoadingState } from '@/components/ui/LoadingState';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, ColumnDef } from '@/components/DataTable';
import { useRecentEvents } from './hooks';

export function OpsEventsPage() {
  const [limit, setLimit] = useState(50);
  const { data: events, isLoading, error } = useRecentEvents({ limit });

  if (isLoading) {
    return <LoadingState message="Loading events..." />;
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600 mb-4">Failed to load events</p>
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
      key: 'event_type',
      header: 'Type',
      cell: (type) => (
        <span className="rounded bg-bg-muted px-2 py-1 text-xs font-medium text-fg">
          {type}
        </span>
      ),
      className: 'w-48',
    },
    {
      key: 'message',
      header: 'Message',
      cell: (message) => (
        <span className="text-sm text-fg line-clamp-2">{message}</span>
      ),
    },
    {
      key: 'project_id',
      header: 'Project',
      cell: (projectId, row) =>
        projectId ? (
          <Link
            to="/projects/$projectId"
            params={{ projectId: String(projectId) }}
            className="text-sm text-blue-600 hover:underline"
          >
            {row.project_name || `#${projectId}`}
          </Link>
        ) : (
          <span className="text-sm text-fg-muted">—</span>
        ),
      className: 'w-32',
    },
    {
      key: 'protocol_run_id',
      header: 'Protocol',
      cell: (protocolId, row) =>
        protocolId ? (
          <Link
            to="/protocols/$protocolId"
            params={{ protocolId: String(protocolId) }}
            className="text-sm text-blue-600 hover:underline"
          >
            {row.protocol_name || `#${protocolId}`}
          </Link>
        ) : (
          <span className="text-sm text-fg-muted">—</span>
        ),
      className: 'w-32',
    },
    {
      key: 'created_at',
      header: 'Time',
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Events</h1>
          <p className="text-gray-600">System activity feed and event log</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-md border border-border bg-bg-panel px-3 py-2 text-sm"
          >
            <option value={50}>Last 50</option>
            <option value={100}>Last 100</option>
            <option value={200}>Last 200</option>
            <option value={500}>Last 500</option>
          </select>
        </div>
      </div>

      {events && events.length > 0 ? (
        <>
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-fg-muted" />
              <span className="text-fg-muted">Total Events:</span>
              <span className="font-medium text-fg">{events.length}</span>
            </div>
          </div>
          <DataTable columns={columns} data={events} />
        </>
      ) : (
        <EmptyState
          title="No events yet"
          description="System events will appear here as protocols run and actions are performed."
          icon={<AlertCircle className="h-12 w-12 text-gray-400" />}
        />
      )}
    </div>
  );
}
