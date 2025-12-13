import React from 'react';
import { Link, useSearch } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import { apiFetchJson } from '@/api/client';
import { type Clarification, type ProtocolRun, type ProtocolRunCreate } from '@/api/types';
import { useSettingsSnapshot } from '@/app/settings/store';
import { useDocumentVisible } from '@/app/polling';

type StepKey = 'details' | 'review' | 'launch' | 'clarifications';

export function ProtocolsNewPage() {
  const settings = useSettingsSnapshot();
  const visible = useDocumentVisible();
  const pollEnabled = settings.polling.enabled && (!settings.polling.disableInBackground || visible);
  const search = useSearch({ from: '/protocols/new' });
  const projectId = search.projectId ? Number(search.projectId) : null;

  const [step, setStep] = React.useState<StepKey>('details');
  const [draft, setDraft] = React.useState<ProtocolRunCreate>({
    protocol_name: '',
    base_branch: 'main',
    description: '',
    status: 'pending',
  });
  const [created, setCreated] = React.useState<ProtocolRun | null>(null);
  const [autoStart, setAutoStart] = React.useState(true);

  const createProtocol = useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error('projectId missing');
      return await apiFetchJson<ProtocolRun>(`/projects/${projectId}/protocols`, {
        method: 'POST',
        body: JSON.stringify(draft),
      });
    },
    onSuccess: async (run) => {
      setCreated(run);
      toast.success(`Protocol created (#${run.id})`);
      if (autoStart) {
        await apiFetchJson(`/protocols/${run.id}/actions/start`, { method: 'POST' });
        toast.success('Planning enqueued');
      }
      setStep('clarifications');
    },
    onError: (err) => toast.error(String(err)),
  });

  const clarifications = useQuery({
    queryKey: ['protocols', created?.id, 'clarifications'],
    enabled: Boolean(created?.id),
    queryFn: async () => {
      return await apiFetchJson<Clarification[]>(`/protocols/${created!.id}/clarifications?status=open`);
    },
    refetchInterval: pollEnabled ? settings.polling.intervalsMs.recentEvents : false,
  });

  const answerClarification = useMutation({
    mutationFn: async (payload: { key: string; answer: string }) => {
      if (!created?.id) throw new Error('protocol not created');
      return await apiFetchJson<Clarification>(`/protocols/${created.id}/clarifications/${payload.key}`, {
        method: 'POST',
        body: JSON.stringify({ answer: payload.answer }),
      });
    },
    onSuccess: async () => {
      await clarifications.refetch();
      toast.success('Clarification answered');
    },
    onError: (err) => toast.error(String(err)),
  });

  const steps: Array<{ key: StepKey; label: string }> = [
    { key: 'details', label: 'Details' },
    { key: 'review', label: 'Review' },
    { key: 'launch', label: 'Launch' },
    { key: 'clarifications', label: 'Clarifications' },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Create Protocol</h1>
        <Link to="/projects" className="rounded-md border border-border bg-bg-panel px-3 py-2 text-sm hover:bg-bg-muted">
          Back
        </Link>
      </div>

      {!projectId && (
        <div className="rounded-md border border-border bg-bg-panel p-4 text-sm text-fg-muted">
          Missing <span className="text-fg">projectId</span>. Open this wizard from a Project page.
        </div>
      )}

      <div className="flex flex-wrap gap-2 rounded-md border border-border bg-bg-panel p-2">
        {steps.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setStep(s.key)}
            className={[
              'rounded-md px-3 py-2 text-sm',
              step === s.key ? 'bg-bg-muted text-fg' : 'text-fg-muted hover:bg-bg-muted hover:text-fg',
            ].join(' ')}
          >
            {s.label}
          </button>
        ))}
      </div>

      {step === 'details' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Protocol details</div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">Protocol name</span>
              <input
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                value={draft.protocol_name}
                onChange={(e) => setDraft({ ...draft, protocol_name: e.target.value })}
                placeholder="0001-feature-auth"
              />
            </label>
            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">Base branch</span>
              <input
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                value={draft.base_branch ?? 'main'}
                onChange={(e) => setDraft({ ...draft, base_branch: e.target.value })}
              />
            </label>
            <label className="grid gap-2 text-sm md:col-span-2">
              <span className="text-xs text-fg-muted">Description</span>
              <input
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                value={draft.description ?? ''}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </label>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
              onClick={() => setStep('review')}
              disabled={!draft.protocol_name}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {step === 'review' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Review</div>
          <div className="mt-1 text-xs text-fg-muted">
            Template selection + spec preview will be added; for now we create the run and enqueue planning.
          </div>
          <pre className="mt-4 overflow-auto rounded-md border border-border bg-bg-muted p-3 text-xs text-fg">
            {JSON.stringify(draft, null, 2)}
          </pre>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
              onClick={() => setStep('launch')}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {step === 'launch' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Launch</div>
          <div className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={autoStart} onChange={(e) => setAutoStart(e.target.checked)} />
            <span>Start planning immediately</span>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
              disabled={!projectId || !draft.protocol_name || createProtocol.isPending}
              onClick={() => createProtocol.mutate()}
            >
              {createProtocol.isPending ? 'Creating…' : 'Create protocol'}
            </button>
            {createProtocol.error ? (
              <div className="text-sm text-red-300">{String(createProtocol.error)}</div>
            ) : null}
          </div>
        </div>
      )}

      {step === 'clarifications' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Clarifications</div>
          <div className="mt-1 text-xs text-fg-muted">Answer blocking questions to unblock planning/execution.</div>

          {created ? (
            <div className="mt-3 text-sm">
              Created protocol{' '}
              <Link className="text-sky-300 hover:underline" to="/protocols/$protocolId" params={{ protocolId: String(created.id) }}>
                #{created.id}
              </Link>
            </div>
          ) : null}

          <div className="mt-4 space-y-3">
            {(clarifications.data ?? []).length === 0 ? (
              <div className="text-sm text-fg-muted">No open clarifications.</div>
            ) : (
              (clarifications.data ?? []).map((c) => (
                <div key={c.id} className="rounded-md border border-border bg-bg-muted p-3">
                  <div className="text-sm font-medium">
                    {c.blocking ? 'BLOCKING' : 'Info'} · {c.key}
                  </div>
                  <div className="mt-1 text-sm text-fg-muted">{c.question}</div>
                  <form
                    className="mt-3 flex gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = e.currentTarget;
                      const input = form.elements.namedItem('answer') as HTMLInputElement;
                      const val = input.value.trim();
                      if (!val) return;
                      answerClarification.mutate({ key: c.key, answer: val });
                      input.value = '';
                    }}
                  >
                    <input
                      name="answer"
                      className="min-w-0 flex-1 rounded-md border border-border bg-bg-panel px-3 py-2 text-sm"
                      placeholder="Answer…"
                    />
                    <button
                      type="submit"
                      className="rounded-md border border-border bg-bg-panel px-3 py-2 text-sm hover:bg-bg-muted"
                      disabled={answerClarification.isPending}
                    >
                      Submit
                    </button>
                  </form>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

