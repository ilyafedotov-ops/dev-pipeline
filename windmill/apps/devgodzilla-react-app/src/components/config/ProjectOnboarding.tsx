// ProjectOnboarding - Multi-step wizard for new project setup
// Handles repository config, classification selection, and review

import { useState, useCallback } from 'react';
import { api } from '../../api/client';
import { Button, Input, Card } from '../common';

// ============ Types ============

interface ProjectOnboardingProps {
    onComplete: (projectId: number) => void;
    onCancel: () => void;
}

interface ProjectData {
    name: string;
    git_url: string;
    base_branch: string;
    description: string;
    classification: string;
}

interface Classification {
    key: string;
    name: string;
    description: string;
    icon: string;
}

// ============ Classifications ============

const CLASSIFICATIONS: Classification[] = [
    {
        key: 'default',
        name: 'Default',
        description: 'Standard development settings with balanced governance',
        icon: '⚙️',
    },
    {
        key: 'startup-fast',
        name: 'Startup Fast',
        description: 'Speed over formality - minimal gates, rapid iteration',
        icon: '🚀',
    },
    {
        key: 'team-standard',
        name: 'Team Standard',
        description: 'Balanced approach with code review and testing gates',
        icon: '👥',
    },
    {
        key: 'enterprise-compliance',
        name: 'Enterprise',
        description: 'Maximum compliance - all gates required, full audit',
        icon: '🏢',
    },
];

// ============ Step Components ============

interface StepProps {
    data: ProjectData;
    onChange: (data: Partial<ProjectData>) => void;
    onNext: () => void;
    onBack?: () => void;
    loading?: boolean;
}

// Step 1: Repository Setup
function RepositoryStep({ data, onChange, onNext }: StepProps) {
    const isValid = data.name.trim().length > 0;

    return (
        <div className="onboarding-step">
            <h2 className="step-title">Repository Setup</h2>
            <p className="step-description">
                Enter your project details to get started
            </p>

            <div className="step-form">
                <Input
                    label="Project Name *"
                    placeholder="my-awesome-project"
                    value={data.name}
                    onChange={(e) => onChange({ name: e.target.value })}
                    helperText="A unique name for your project"
                />

                <Input
                    label="Git Repository URL"
                    placeholder="https://github.com/username/repo"
                    value={data.git_url}
                    onChange={(e) => onChange({ git_url: e.target.value })}
                    helperText="Optional - repository will be cloned if provided"
                />

                <Input
                    label="Base Branch"
                    placeholder="main"
                    value={data.base_branch}
                    onChange={(e) => onChange({ base_branch: e.target.value })}
                    helperText="Default branch for development"
                />

                <div className="form-group">
                    <label className="form-label">Description</label>
                    <textarea
                        className="form-input"
                        placeholder="Brief description of your project..."
                        value={data.description}
                        onChange={(e) => onChange({ description: e.target.value })}
                        rows={3}
                    />
                </div>
            </div>

            <div className="step-actions">
                <Button variant="primary" onClick={onNext} disabled={!isValid}>
                    Next →
                </Button>
            </div>
        </div>
    );
}

// Step 2: Classification Selection
function ClassificationStep({ data, onChange, onNext, onBack }: StepProps) {
    return (
        <div className="onboarding-step">
            <h2 className="step-title">Project Classification</h2>
            <p className="step-description">
                Choose a governance preset that matches your project's needs
            </p>

            <div className="classification-grid">
                {CLASSIFICATIONS.map((c) => (
                    <button
                        key={c.key}
                        className={`classification-card ${data.classification === c.key ? 'classification-selected' : ''}`}
                        onClick={() => onChange({ classification: c.key })}
                    >
                        <span className="classification-icon">{c.icon}</span>
                        <div className="classification-content">
                            <h3 className="classification-name">{c.name}</h3>
                            <p className="classification-description">{c.description}</p>
                        </div>
                        {data.classification === c.key && (
                            <span className="classification-check">✓</span>
                        )}
                    </button>
                ))}
            </div>

            <div className="step-actions">
                <Button variant="secondary" onClick={onBack}>
                    ← Back
                </Button>
                <Button variant="primary" onClick={onNext}>
                    Next →
                </Button>
            </div>
        </div>
    );
}

// Step 3: Review & Create
function ReviewStep({ data, onNext, onBack, loading }: StepProps) {
    const classification = CLASSIFICATIONS.find((c) => c.key === data.classification);

    return (
        <div className="onboarding-step">
            <h2 className="step-title">Review Configuration</h2>
            <p className="step-description">
                Review your project settings before creation
            </p>

            <Card className="review-card" padding>
                <dl className="review-list">
                    <div className="review-item">
                        <dt>Name</dt>
                        <dd>{data.name}</dd>
                    </div>
                    <div className="review-item">
                        <dt>Git URL</dt>
                        <dd>{data.git_url || <em>Not specified</em>}</dd>
                    </div>
                    <div className="review-item">
                        <dt>Branch</dt>
                        <dd><code className="code-text">{data.base_branch}</code></dd>
                    </div>
                    <div className="review-item">
                        <dt>Description</dt>
                        <dd>{data.description || <em>No description</em>}</dd>
                    </div>
                    <div className="review-item">
                        <dt>Classification</dt>
                        <dd>
                            <span className="review-classification">
                                {classification?.icon} {classification?.name}
                            </span>
                        </dd>
                    </div>
                </dl>
            </Card>

            <div className="onboarding-effects">
                <h4>This will:</h4>
                <ul>
                    {data.git_url && <li>Clone repository to workspace</li>}
                    <li>Initialize <code>.specify/</code> directory structure</li>
                    <li>Create <code>constitution.md</code> with {classification?.name} rules</li>
                    <li>Enqueue <code>project_setup_job</code> via Windmill</li>
                </ul>
            </div>

            <div className="step-actions">
                <Button variant="secondary" onClick={onBack} disabled={loading}>
                    ← Back
                </Button>
                <Button variant="primary" onClick={onNext} loading={loading}>
                    {loading ? 'Creating...' : 'Create Project'}
                </Button>
            </div>
        </div>
    );
}

// ============ Main ProjectOnboarding Component ============

export function ProjectOnboarding({ onComplete, onCancel }: ProjectOnboardingProps) {
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [data, setData] = useState<ProjectData>({
        name: '',
        git_url: '',
        base_branch: 'main',
        description: '',
        classification: 'default',
    });

    const updateData = useCallback((updates: Partial<ProjectData>) => {
        setData((prev) => ({ ...prev, ...updates }));
    }, []);

    const handleCreate = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await api.projects.create({
                name: data.name.trim(),
                git_url: data.git_url.trim() || undefined,
                base_branch: data.base_branch.trim(),
                description: data.description.trim() || undefined,
                project_classification: data.classification,
            });

            if (result.project) {
                onComplete(result.project.id);
            } else {
                throw new Error('Failed to create project');
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to create project');
            setLoading(false);
        }
    };

    const stepProps: StepProps = {
        data,
        onChange: updateData,
        onNext: () => {
            if (step < 3) {
                setStep(step + 1);
            } else {
                handleCreate();
            }
        },
        onBack: () => setStep(step - 1),
        loading,
    };

    return (
        <div className="project-onboarding">
            {/* Progress Indicator */}
            <div className="onboarding-progress">
                {[1, 2, 3].map((s) => (
                    <div
                        key={s}
                        className={`progress-step ${step >= s ? 'progress-step-active' : ''} ${step === s ? 'progress-step-current' : ''}`}
                    >
                        <span className="progress-number">{s}</span>
                        <span className="progress-label">
                            {s === 1 && 'Repository'}
                            {s === 2 && 'Classification'}
                            {s === 3 && 'Review'}
                        </span>
                    </div>
                ))}
            </div>

            {/* Error Display */}
            {error && (
                <div className="error-state" style={{ marginBottom: '1rem' }}>
                    {error}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setError(null)}
                        style={{ marginLeft: '1rem' }}
                    >
                        Dismiss
                    </Button>
                </div>
            )}

            {/* Step Content */}
            <div className="onboarding-content">
                {step === 1 && <RepositoryStep {...stepProps} />}
                {step === 2 && <ClassificationStep {...stepProps} />}
                {step === 3 && <ReviewStep {...stepProps} />}
            </div>

            {/* Cancel Button */}
            <div className="onboarding-footer">
                <Button variant="ghost" onClick={onCancel} disabled={loading}>
                    Cancel
                </Button>
            </div>
        </div>
    );
}

export default ProjectOnboarding;
