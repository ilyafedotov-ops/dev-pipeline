// AgentConfigManager - Component for managing AI agent configurations
// Allows viewing, editing, and creating agent configurations

import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardContent, Button, Input, Select, Badge, LoadingState, ErrorState } from '../common';

// ============ Types ============

// Extended AgentConfig for UI (extends base type with display properties)
interface AgentConfig {
    agent_id: string | number;
    name?: string;
    model?: string;
    default_model?: string;
    timeout_seconds?: number;
    max_retries?: number;
    sandbox_enabled?: boolean;
    capabilities?: string[];
}

interface AgentConfigManagerProps {
    projectId?: number;
    onSelect?: (config: AgentConfig) => void;
    className?: string;
}

interface ConfigFormData {
    name: string;
    model: string;
    timeout_seconds: number;
    max_retries: number;
    sandbox_enabled: boolean;
    capabilities: string[];
}

// ============ Constants ============

const AVAILABLE_MODELS = [
    'gpt-4',
    'gpt-4-turbo',
    'gpt-3.5-turbo',
    'claude-3-opus',
    'claude-3-sonnet',
    'claude-3-haiku',
    'gemini-pro',
    'gemini-flash',
];

const CAPABILITY_OPTIONS = [
    'code_generation',
    'code_review',
    'testing',
    'documentation',
    'debugging',
    'refactoring',
    'architecture',
    'security',
];

const MODEL_COSTS: Record<string, string> = {
    'gpt-4': '$$$',
    'gpt-4-turbo': '$$',
    'gpt-3.5-turbo': '$',
    'claude-3-opus': '$$$',
    'claude-3-sonnet': '$$',
    'claude-3-haiku': '$',
    'gemini-pro': '$$',
    'gemini-flash': '$',
};

// ============ ConfigCard Component ============

interface ConfigCardProps {
    config: AgentConfig;
    onEdit?: () => void;
    onDelete?: () => void;
    onSelect?: () => void;
    selected?: boolean;
}

function ConfigCard({ config, onEdit, onDelete, onSelect, selected = false }: ConfigCardProps) {
    return (
        <div
            className={`config-card ${selected ? 'config-card-selected' : ''}`}
            onClick={onSelect}
        >
            <div className="config-card-header">
                <h4 className="config-name">{config.name || `Config ${config.agent_id}`}</h4>
                {selected && <span className="config-checkmark">✓</span>}
            </div>

            <div className="config-model">
                <span className="model-name">{config.model || 'default'}</span>
                <span className="model-cost">{MODEL_COSTS[config.model || ''] || '$'}</span>
            </div>

            <div className="config-settings">
                <div className="config-setting">
                    <span className="setting-label">Timeout:</span>
                    <span className="setting-value">{config.timeout_seconds || 300}s</span>
                </div>
                <div className="config-setting">
                    <span className="setting-label">Retries:</span>
                    <span className="setting-value">{config.max_retries || 3}</span>
                </div>
                <div className="config-setting">
                    <span className="setting-label">Sandbox:</span>
                    <span className="setting-value">{config.sandbox_enabled ? '✓' : '✗'}</span>
                </div>
            </div>

            {config.capabilities && config.capabilities.length > 0 && (
                <div className="config-capabilities">
                    {config.capabilities.slice(0, 3).map((cap, idx) => (
                        <Badge key={idx} variant="info">{cap}</Badge>
                    ))}
                    {config.capabilities.length > 3 && (
                        <span className="capabilities-more">+{config.capabilities.length - 3}</span>
                    )}
                </div>
            )}

            <div className="config-card-actions">
                {onEdit && (
                    <Button variant="secondary" onClick={(e: React.MouseEvent) => { e.stopPropagation(); onEdit(); }}>
                        Edit
                    </Button>
                )}
                {onDelete && (
                    <Button variant="secondary" onClick={(e: React.MouseEvent) => { e.stopPropagation(); onDelete(); }}>
                        Delete
                    </Button>
                )}
            </div>
        </div>
    );
}

// ============ ConfigForm Component ============

interface ConfigFormProps {
    initialData?: Partial<ConfigFormData>;
    onSave: (data: ConfigFormData) => void;
    onCancel: () => void;
    saving?: boolean;
}

function ConfigForm({ initialData, onSave, onCancel, saving = false }: ConfigFormProps) {
    const [formData, setFormData] = useState<ConfigFormData>({
        name: initialData?.name || '',
        model: initialData?.model || 'gpt-4',
        timeout_seconds: initialData?.timeout_seconds || 300,
        max_retries: initialData?.max_retries || 3,
        sandbox_enabled: initialData?.sandbox_enabled ?? true,
        capabilities: initialData?.capabilities || [],
    });

    const updateField = <K extends keyof ConfigFormData>(
        field: K,
        value: ConfigFormData[K]
    ) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const toggleCapability = (cap: string) => {
        setFormData(prev => ({
            ...prev,
            capabilities: prev.capabilities.includes(cap)
                ? prev.capabilities.filter(c => c !== cap)
                : [...prev.capabilities, cap],
        }));
    };

    const handleSubmit = () => {
        onSave(formData);
    };

    return (
        <div className="config-form">
            <div className="form-group">
                <label className="form-label">Configuration Name</label>
                <Input
                    value={formData.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    placeholder="e.g., Fast Review Agent"
                />
            </div>

            <div className="form-row">
                <div className="form-group">
                    <label className="form-label">Model</label>
                    <Select
                        value={formData.model}
                        onChange={(e) => updateField('model', e.target.value)}
                        options={AVAILABLE_MODELS.map(m => ({ value: m, label: `${m} ${MODEL_COSTS[m] || ''}` }))}
                    />
                </div>

                <div className="form-group">
                    <label className="form-label">Timeout (seconds)</label>
                    <Input
                        type="number"
                        value={formData.timeout_seconds}
                        onChange={(e) => updateField('timeout_seconds', parseInt(e.target.value) || 300)}
                        min={30}
                        max={3600}
                    />
                </div>
            </div>

            <div className="form-row">
                <div className="form-group">
                    <label className="form-label">Max Retries</label>
                    <Input
                        type="number"
                        value={formData.max_retries}
                        onChange={(e) => updateField('max_retries', parseInt(e.target.value) || 3)}
                        min={0}
                        max={10}
                    />
                </div>

                <div className="form-group">
                    <label className="form-label">Sandbox</label>
                    <label className="checkbox-label">
                        <input
                            type="checkbox"
                            checked={formData.sandbox_enabled}
                            onChange={(e) => updateField('sandbox_enabled', e.target.checked)}
                        />
                        Enable sandbox execution
                    </label>
                </div>
            </div>

            <div className="form-group">
                <label className="form-label">Capabilities</label>
                <div className="capabilities-grid">
                    {CAPABILITY_OPTIONS.map(cap => (
                        <label key={cap} className="capability-checkbox">
                            <input
                                type="checkbox"
                                checked={formData.capabilities.includes(cap)}
                                onChange={() => toggleCapability(cap)}
                            />
                            <span>{cap.replace('_', ' ')}</span>
                        </label>
                    ))}
                </div>
            </div>

            <div className="form-actions">
                <Button variant="secondary" onClick={onCancel} disabled={saving}>
                    Cancel
                </Button>
                <Button variant="primary" onClick={handleSubmit} disabled={saving || !formData.name}>
                    {saving ? 'Saving...' : 'Save Configuration'}
                </Button>
            </div>
        </div>
    );
}

// ============ Main AgentConfigManager Component ============

export function AgentConfigManager({ projectId, onSelect, className = '' }: AgentConfigManagerProps) {
    const [configs, setConfigs] = useState<AgentConfig[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedConfig, setSelectedConfig] = useState<AgentConfig | null>(null);
    const [showForm, setShowForm] = useState(false);
    const [editingConfig, setEditingConfig] = useState<AgentConfig | null>(null);
    const [saving, setSaving] = useState(false);

    const loadConfigs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // Sample configurations for demo
            const sampleConfigs: AgentConfig[] = [
                {
                    agent_id: 1,
                    name: 'Default Agent',
                    model: 'gpt-4',
                    timeout_seconds: 300,
                    max_retries: 3,
                    sandbox_enabled: true,
                    capabilities: ['code_generation', 'testing', 'debugging'],
                },
                {
                    agent_id: 2,
                    name: 'Fast Review',
                    model: 'gpt-3.5-turbo',
                    timeout_seconds: 120,
                    max_retries: 2,
                    sandbox_enabled: false,
                    capabilities: ['code_review', 'documentation'],
                },
                {
                    agent_id: 3,
                    name: 'Deep Analysis',
                    model: 'claude-3-opus',
                    timeout_seconds: 600,
                    max_retries: 5,
                    sandbox_enabled: true,
                    capabilities: ['architecture', 'security', 'refactoring'],
                },
            ];

            setConfigs(sampleConfigs);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load configurations');
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        loadConfigs();
    }, [loadConfigs]);

    const handleSave = async (data: ConfigFormData) => {
        setSaving(true);
        try {
            // In real implementation, save to API
            const newConfig: AgentConfig = {
                agent_id: editingConfig?.agent_id || Date.now(),
                ...data,
            };

            if (editingConfig) {
                setConfigs(prev => prev.map(c => c.agent_id === editingConfig.agent_id ? newConfig : c));
            } else {
                setConfigs(prev => [...prev, newConfig]);
            }

            setShowForm(false);
            setEditingConfig(null);
        } catch (e) {
            console.error('Failed to save config:', e);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (config: AgentConfig) => {
        if (!confirm(`Delete configuration "${config.name}"?`)) return;

        try {
            setConfigs(prev => prev.filter(c => c.agent_id !== config.agent_id));
        } catch (e) {
            console.error('Failed to delete config:', e);
        }
    };

    const handleSelect = (config: AgentConfig) => {
        setSelectedConfig(config);
        onSelect?.(config);
    };

    if (loading) {
        return (
            <Card className={`agent-config-manager ${className}`}>
                <LoadingState text="Loading configurations..." />
            </Card>
        );
    }

    if (error) {
        return (
            <Card className={`agent-config-manager ${className}`}>
                <ErrorState message={error} retry={loadConfigs} />
            </Card>
        );
    }

    return (
        <div className={`agent-config-manager ${className}`}>
            <Card>
                <CardHeader
                    action={
                        <Button variant="primary" onClick={() => setShowForm(true)}>
                            + New Configuration
                        </Button>
                    }
                >
                    Agent Configurations
                </CardHeader>
                <CardContent>
                    {showForm || editingConfig ? (
                        <ConfigForm
                            initialData={editingConfig || undefined}
                            onSave={handleSave}
                            onCancel={() => { setShowForm(false); setEditingConfig(null); }}
                            saving={saving}
                        />
                    ) : (
                        <div className="configs-grid">
                            {configs.map(config => (
                                <ConfigCard
                                    key={config.agent_id}
                                    config={config}
                                    selected={selectedConfig?.agent_id === config.agent_id}
                                    onSelect={() => handleSelect(config)}
                                    onEdit={() => setEditingConfig(config)}
                                    onDelete={() => handleDelete(config)}
                                />
                            ))}
                            {configs.length === 0 && (
                                <div className="no-configs">
                                    <p>No configurations yet</p>
                                    <Button variant="primary" onClick={() => setShowForm(true)}>
                                        Create First Configuration
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

export default AgentConfigManager;
