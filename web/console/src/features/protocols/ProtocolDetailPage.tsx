import { Link, useParams, useSearch } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import React from 'react';
import { toast } from 'sonner';

import { apiFetchJson } from '@/api/client';
import { type CISummary, type GitStatus } from '@/api/types';
import { loadWatchState, toggleWatchedProtocol } from '@/app/watch/store';

const tabs = [
  { key: 'steps', label: 'Steps' },
  { key: 'events', label: 'Events' },
  { key: 'runs', label: 'Runs' },
  { key: 'spec', label: 'Spec' },
  { key: 'policy', label: 'Policy' },
  { key: 'clarifications', label: 'Clarifications' },
] as const;

export function ProtocolDetailPage() {
  const { protocolId } = useParams({ from: '/protocols/$protocolId' });
  const search = useSearch({ from: '/protocols/$protocolId' });
  const activeTab = search.tab ?? 'steps';
  const id = Number(protocolId);
  const [watch, setWatch] = React.useState(() => loadWatchState());
  const isWatched = Number.isFinite(id) && watch.protocols.includes(id);

  const protocol = useQuery({
    queryKey: ['protocols', 'detail', id],
    queryFn: async () => await apiFetchJson<Record<string, unknown>>(`/protocols/${id}`),
    staleTime: 5_000,
    retry: 1,
  });

  const ci = useQuery({
    queryKey: ['protocols', id, 'ci', 'summary'],
    queryFn: async () => await apiFetchJson<CISummary>(`/protocols/${id}/ci/summary`),
    staleTime: 5_000,
    retry: 1,
  });

  const gitStatus = useQuery({
    queryKey: ['protocols', id, 'git', 'status'],
    queryFn: async () => await apiFetchJson<GitStatus>(`/protocols/${id}/git/status`),
    staleTime: 5_000,
    retry: 1,
  });

  const openPr = useMutation({
    mutationFn: async () => await apiFetchJson(`/protocols/${id}/actions/open_pr`, { method: 'POST' }),
    onSuccess: () => toast.success('Open PR/MR enqueued'),
    onError: (err) => toast.error(String(err)),
  });

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-bg-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs text-fg-muted">Protocol</div>
            <h1 className="text-lg font-semibold">{protocolId}</h1>
            <div className="mt-1 text-xs text-fg-muted">
              Status: <span className="text-fg">{String((protocol.data as any)?.status ?? '...')}</span> · Base:{' '}
              <span className="text-fg">{String((protocol.data as any)?.base_branch ?? 'main')}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
              onClick={() => {
                if (!Number.isFinite(id)) return;
                setWatch(toggleWatchedProtocol(id));
              }}
            >
              {isWatched ? 'Unwatch' : 'Watch'}
            </button>
            <button
              type="button"
              className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
              onClick={() => openPr.mutate()}
              disabled={openPr.isPending}
            >
              {openPr.isPending ? 'Enqueueing…' : 'Open PR/MR'}
            </button>
            {ci.data?.pr_url ? (
              <a
                className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
                href={ci.data.pr_url}
                target="_blank"
                rel="noreferrer"
              >
                View PR/MR
              </a>
            ) : null}
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-md border border-border bg-bg-muted p-3">
            <div className="text-xs text-fg-muted">CI</div>
            <div className="mt-1 text-sm">
              {(ci.data?.provider ?? '—') + ' · ' + (ci.data?.conclusion ?? ci.data?.status ?? '—')}
            </div>
            {ci.data?.check_name ? <div className="mt-1 text-xs text-fg-muted">{ci.data.check_name}</div> : null}
          </div>
          <div className="rounded-md border border-border bg-bg-muted p-3">
            <div className="text-xs text-fg-muted">Git</div>
            <div className="mt-1 text-sm">
              {gitStatus.data?.branch ?? '—'} · {gitStatus.data?.dirty ? 'dirty' : 'clean'}
            </div>
            {gitStatus.data?.head_sha ? (
              <div className="mt-1 font-mono text-xs text-fg-muted">{gitStatus.data.head_sha.slice(0, 12)}</div>
            ) : null}
          </div>
          <div className="rounded-md border border-border bg-bg-muted p-3">
            <div className="text-xs text-fg-muted">Changes</div>
            <div className="mt-1 text-sm">{(gitStatus.data?.changed_files ?? []).length} file(s)</div>
          </div>
        </div>

        {(gitStatus.data?.changed_files ?? []).length > 0 ? (
          <div className="mt-4">
            <div className="text-sm font-medium">Changed files</div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-fg-muted">
              {gitStatus.data!.changed_files.slice(0, 20).map((f) => (
                <li key={f} className="font-mono">
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2 rounded-md border border-border bg-bg-panel p-2">
        {tabs.map((t) => (
          <Link
            key={t.key}
            to="/protocols/$protocolId"
            params={{ protocolId }}
            search={{ tab: t.key }}
            className={[
              'rounded-md px-3 py-2 text-sm',
              activeTab === t.key ? 'bg-bg-muted text-fg' : 'text-fg-muted hover:bg-bg-muted hover:text-fg',
            ].join(' ')}
          >
            {t.label}
          </Link>
        ))}
      </div>

      {activeTab === 'steps' && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Steps table + inline actions.
        </div>
      )}
      {activeTab === 'events' && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Protocol events timeline + filters.
        </div>
      )}
      {activeTab === 'runs' && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Protocol runs list + links to Run detail.
        </div>
      )}
      {activeTab === 'spec' && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Spec viewer + validation status.
        </div>
      )}
      {activeTab === 'policy' && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Policy snapshot + findings.
        </div>
      )}
      {activeTab === 'clarifications' && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Protocol clarifications Q&A.
        </div>
      )}
    </div>
  );
}
