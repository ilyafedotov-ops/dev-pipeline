// AgentSelector - Component for assigning AI agents to steps
// Shows available agents with status and allows configuration overrides

import { useState, useEffect, useCallback } from 'react';
import type { Agent, AgentConfig, AgentAssignRequest } from '../../types';
import { api } from '../../api/client';
import { Button, Input, Select, LoadingState, ErrorState } from '../common';

// ============ Types ============

interface AgentSelectorProps {
    stepId: string;
    stepName: string;
    currentAgentId?: string;
    onAssign: (assignment: AgentAssignRequest) => void;
    onCancel: () => void;
}

// ============ AgentCard Component ============

interface AgentCardProps {
    agent: Agent;
    isSelected: boolean;
    onSelect: () => void;
}

function AgentCard({ agent, isSelected, onSelect }: AgentCardProps) {
    const isAvailable = agent.status === 'available';

    const statusColors = {
        available: '#22c55e',
        unavailable: '#6b7280',
        error: '#ef4444',
    };

    return (
        <button
            className={`agent-card ${isSelected ? 'agent-card-selected' : ''} ${!isAvailable ? 'agent-card-unavailable' : ''}`}
            onClick={isAvailable ? onSelect : undefined}
            disabled={!isAvailable}
        >
            <div className="agent-card-header">
                <span className="agent-name">{agent.name}</span>
                {isSelected && <span className="agent-checkmark">✓</span>}
            </div>

            <div className="agent-status">
                <span
                    className="agent-status-dot"
                    style={{ backgroundColor: statusColors[agent.status] }}
                />
                <span className="agent-status-text">
                    {agent.status === 'available' ? '🟢 Available' : '🔴 Unavailable'}
                </span>
            </div>

            <div className="agent-meta">
                <span className="agent-kind">{agent.kind.toUpperCase()}</span>
                {agent.default_model && (
                    <span className="agent-model">{agent.default_model}</span>
                )}
            </div>

            {agent.capabilities.length > 0 && (
                <div className="agent-capabilities">
                    {agent.capabilities.slice(0, 3).map(cap => (
                        <span key={cap} className="agent-capability">{cap}</span>
                    ))}
                    {agent.capabilities.length > 3 && (
                        <span className="agent-capability-more">+{agent.capabilities.length - 3}</span>
                    )}
                </div>
            )}
        </button>
    );
}

// ============ ConfigOverrideForm Component ============

interface ConfigOverrideFormProps {
    agent: Agent;
    config: Partial<AgentConfig>;
    onChange: (config: Partial<AgentConfig>) => void;
}

function ConfigOverrideForm({ agent, config, onChange }: ConfigOverrideFormProps) {
    return (
        <div className="config-override-form">
            <h4 className="config-title">Override Settings (Optional)</h4>

            <div className="config-grid">
                <Input
                    label="Model"
                    placeholder={agent.default_model || 'Default model'}
                    value={config.default_model || ''}
                    onChange={(e) => onChange({ ...config, default_model: e.target.value || undefined })}
                />

                <Input
                    label="Timeout (seconds)"
                    type="number"
                    placeholder="300"
                    value={config.timeout_seconds || ''}
                    onChange={(e) => onChange({
                        ...config,
                        timeout_seconds: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                />

                <Input
                    label="Max Retries"
                    type="number"
                    placeholder="3"
                    value={config.max_retries || ''}
                    onChange={(e) => onChange({
                        ...config,
                        max_retries: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                />

                <Select
                    label="Sandbox Mode"
                    options={[
                        { value: '', label: 'Default' },
                        { value: 'workspace-read', label: 'Read Only' },
                        { value: 'workspace-write', label: 'Read/Write' },
                        { value: 'full-access', label: 'Full Access' },
                    ]}
                    value={config.sandbox || ''}
                    onChange={(e) => onChange({
                        ...config,
                        sandbox: e.target.value as AgentConfig['sandbox'] || undefined
                    })}
                />
            </div>
        </div>
    );
}

// ============ Main AgentSelector Component ============

export function AgentSelector({
    stepId,
    stepName,
    currentAgentId,
    onAssign,
    onCancel,
}: AgentSelectorProps) {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedAgentId, setSelectedAgentId] = useState<string | null>(currentAgentId || null);
    const [configOverride, setConfigOverride] = useState<Partial<AgentConfig>>({});
    const [assigning, setAssigning] = useState(false);

    // Load agents
    const loadAgents = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await api.agents.list();
            setAgents(result.agents || []);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load agents');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAgents();
    }, [loadAgents]);

    // Handle assignment
    const handleAssign = async () => {
        if (!selectedAgentId) return;

        setAssigning(true);
        try {
            const assignment: AgentAssignRequest = {
                agent_id: selectedAgentId,
            };

            // Only include config_override if there are values
            const hasOverrides = Object.values(configOverride).some(v => v !== undefined && v !== '');
            if (hasOverrides) {
                assignment.config_override = configOverride;
            }

            onAssign(assignment);
        } finally {
            setAssigning(false);
        }
    };

    const selectedAgent = agents.find(a => a.id === selectedAgentId);

    if (loading) {
        return (
            <div className="agent-selector">
                <LoadingState text="Loading available agents..." />
            </div>
        );
    }

    if (error) {
        return (
            <div className="agent-selector">
                <ErrorState message={error} retry={loadAgents} />
            </div>
        );
    }

    return (
        <div className="agent-selector">
            <div className="agent-selector-header">
                <h3>Assign Agent to Step</h3>
                <p className="agent-selector-step">{stepId} - {stepName}</p>
            </div>

            {/* Agent Grid */}
            <div className="agent-grid">
                {agents.map(agent => (
                    <AgentCard
                        key={agent.id}
                        agent={agent}
                        isSelected={selectedAgentId === agent.id}
                        onSelect={() => {
                            setSelectedAgentId(agent.id);
                            setConfigOverride({});
                        }}
                    />
                ))}
            </div>

            {/* Config Override Form */}
            {selectedAgent && (
                <ConfigOverrideForm
                    agent={selectedAgent}
                    config={configOverride}
                    onChange={setConfigOverride}
                />
            )}

            {/* Capabilities Display */}
            {selectedAgent && selectedAgent.capabilities.length > 0 && (
                <div className="agent-capabilities-full">
                    <h4>Capabilities</h4>
                    <div className="capabilities-list">
                        {selectedAgent.capabilities.map(cap => (
                            <span key={cap} className="capability-tag">{cap}</span>
                        ))}
                    </div>
                </div>
            )}

            {/* Actions */}
            <div className="agent-selector-actions">
                <Button variant="secondary" onClick={onCancel}>
                    Cancel
                </Button>
                <Button
                    variant="primary"
                    onClick={handleAssign}
                    disabled={!selectedAgentId || assigning}
                    loading={assigning}
                >
                    {assigning ? 'Assigning...' : 'Assign Agent'}
                </Button>
            </div>
        </div>
    );
}

// ============ Inline Agent Badge ============

interface AgentBadgeProps {
    agentId: string;
    agentName?: string;
    onClick?: () => void;
}

export function AgentBadge({ agentId, agentName, onClick }: AgentBadgeProps) {
    return (
        <span
            className={`agent-badge ${onClick ? 'agent-badge-clickable' : ''}`}
            onClick={onClick}
        >
            🤖 {agentName || agentId}
        </span>
    );
}

// ============ Agent Status Indicator ============

interface AgentStatusProps {
    status: Agent['status'];
}

export function AgentStatus({ status }: AgentStatusProps) {
    const config = {
        available: { icon: '🟢', label: 'Available' },
        unavailable: { icon: '🔴', label: 'Unavailable' },
        error: { icon: '⚠️', label: 'Error' },
    };

    const { icon, label } = config[status] || config.unavailable;

    return (
        <span className="agent-status-indicator">
            {icon} {label}
        </span>
    );
}

export default AgentSelector;
