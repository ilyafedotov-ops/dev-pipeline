// QADashboard - Quality Assurance Dashboard Component
// Displays constitutional gates, checklist results, and findings

import { useState, useEffect, useCallback } from 'react';
import type { QualitySummary, GateResult, ChecklistItem } from '../../types';
import { api } from '../../api/client';
import { Card, CardHeader, CardContent, Badge, ProgressBar, LoadingState, ErrorState } from '../common';

// ============ Types ============

interface QADashboardProps {
    protocolId: number;
    className?: string;
}

// ============ Status Icons ============

const GATE_ICONS: Record<GateResult['status'], string> = {
    passed: '✅',
    warning: '⚠️',
    failed: '❌',
    skipped: '⏭️',
};

// ============ GateCard Component ============

interface GateCardProps {
    gate: GateResult;
    expanded?: boolean;
    onToggle?: () => void;
}

function GateCard({ gate, expanded = false, onToggle }: GateCardProps) {
    const hasFindings = gate.findings.length > 0;

    return (
        <div
            className={`gate-card gate-card-${gate.status} ${hasFindings ? 'gate-card-clickable' : ''}`}
            onClick={hasFindings ? onToggle : undefined}
        >
            <div className="gate-header">
                <span className="gate-icon">{GATE_ICONS[gate.status]}</span>
                <div className="gate-info">
                    <span className="gate-article">Article {gate.article}</span>
                    <span className="gate-name">{gate.name}</span>
                </div>
                <Badge
                    variant={gate.status === 'passed' ? 'success' : gate.status === 'warning' ? 'warning' : 'error'}
                >
                    {gate.status.toUpperCase()}
                </Badge>
                {hasFindings && (
                    <span className="gate-expand">{expanded ? '▼' : '▶'}</span>
                )}
            </div>

            {expanded && hasFindings && (
                <div className="gate-findings">
                    {gate.findings.map((finding, idx) => (
                        <div key={idx} className="finding-item">
                            <div className="finding-header">
                                <code className="finding-code">{finding.code}</code>
                                <Badge variant={finding.severity === 'error' ? 'error' : 'warning'}>
                                    {finding.severity}
                                </Badge>
                            </div>
                            <p className="finding-message">{finding.message}</p>
                            {finding.step_id && (
                                <span className="finding-step">Step: {finding.step_id}</span>
                            )}
                            {finding.suggested_fix && (
                                <div className="finding-fix">
                                    <strong>Fix:</strong> {finding.suggested_fix}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ============ ChecklistSection Component ============

interface ChecklistSectionProps {
    items: ChecklistItem[];
    passed: number;
    total: number;
}

function ChecklistSection({ items, passed, total }: ChecklistSectionProps) {
    const percentage = total > 0 ? Math.round((passed / total) * 100) : 0;

    return (
        <div className="checklist-section">
            <div className="checklist-header">
                <h4>Checklist Progress</h4>
                <span className="checklist-progress">{passed} / {total}</span>
            </div>

            <ProgressBar
                value={percentage}
                variant={percentage === 100 ? 'success' : 'info'}
                showLabel
            />

            <div className="checklist-items">
                {items.map(item => (
                    <div
                        key={item.id}
                        className={`checklist-item ${item.passed ? 'checklist-item-passed' : ''}`}
                    >
                        <input
                            type="checkbox"
                            checked={item.passed}
                            disabled
                            className="checklist-checkbox"
                        />
                        <span className="checklist-description">{item.description}</span>
                        {item.required && (
                            <Badge variant="warning" className="checklist-required">Required</Badge>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ============ ScoreMeter Component ============

interface ScoreMeterProps {
    score: number; // 0-1
    status: 'passed' | 'warning' | 'failed';
}

function ScoreMeter({ score, status }: ScoreMeterProps) {
    const percentage = Math.round(score * 100);

    const statusColors = {
        passed: '#22c55e',
        warning: '#f59e0b',
        failed: '#ef4444',
    };

    return (
        <div className="score-meter">
            <svg viewBox="0 0 100 50" className="score-arc">
                {/* Background arc */}
                <path
                    d="M 10 50 A 40 40 0 0 1 90 50"
                    fill="none"
                    stroke="#e5e7eb"
                    strokeWidth="8"
                />
                {/* Score arc */}
                <path
                    d="M 10 50 A 40 40 0 0 1 90 50"
                    fill="none"
                    stroke={statusColors[status]}
                    strokeWidth="8"
                    strokeDasharray={`${percentage * 1.257} 125.7`}
                    className="score-arc-fill"
                />
            </svg>
            <div className="score-value">
                <span className="score-number">{percentage}%</span>
                <span className="score-label">Score</span>
            </div>
        </div>
    );
}

// ============ Main QADashboard Component ============

export function QADashboard({ protocolId, className = '' }: QADashboardProps) {
    const [summary, setSummary] = useState<QualitySummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedGates, setExpandedGates] = useState<Set<string>>(new Set());

    const loadQuality = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await api.quality.getSummary(protocolId);
            setSummary(result);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load quality data');
        } finally {
            setLoading(false);
        }
    }, [protocolId]);

    useEffect(() => {
        loadQuality();
    }, [loadQuality]);

    const toggleGate = (article: string) => {
        setExpandedGates(prev => {
            const next = new Set(prev);
            if (next.has(article)) {
                next.delete(article);
            } else {
                next.add(article);
            }
            return next;
        });
    };

    if (loading) {
        return (
            <Card className={`qa-dashboard ${className}`}>
                <LoadingState text="Loading quality data..." />
            </Card>
        );
    }

    if (error || !summary) {
        return (
            <Card className={`qa-dashboard ${className}`}>
                <ErrorState message={error || 'No quality data available'} retry={loadQuality} />
            </Card>
        );
    }

    const findingsCount = summary.gates.reduce((acc, gate) => acc + gate.findings.length, 0);

    return (
        <div className={`qa-dashboard ${className}`}>
            {/* Header with Score */}
            <Card className="qa-header-card">
                <div className="qa-header">
                    <div className="qa-header-left">
                        <h2>Quality Assurance</h2>
                        <p className="qa-constitution">
                            Constitution v{summary.constitution_version}
                        </p>
                    </div>
                    <div className="qa-header-right">
                        <ScoreMeter score={summary.score} status={summary.overall_status} />
                    </div>
                </div>

                {/* Summary Stats */}
                <div className="qa-stats">
                    <div className="qa-stat">
                        <span className="qa-stat-value">{summary.gates.filter(g => g.status === 'passed').length}</span>
                        <span className="qa-stat-label">Passed</span>
                    </div>
                    <div className="qa-stat qa-stat-warning">
                        <span className="qa-stat-value">{summary.warnings}</span>
                        <span className="qa-stat-label">Warnings</span>
                    </div>
                    <div className="qa-stat qa-stat-error">
                        <span className="qa-stat-value">{summary.blocking_issues}</span>
                        <span className="qa-stat-label">Blocking</span>
                    </div>
                    <div className="qa-stat">
                        <span className="qa-stat-value">{findingsCount}</span>
                        <span className="qa-stat-label">Findings</span>
                    </div>
                </div>
            </Card>

            {/* Constitutional Gates */}
            <Card>
                <CardHeader>Constitutional Gates</CardHeader>
                <CardContent className="gates-content">
                    {summary.gates.map(gate => (
                        <GateCard
                            key={gate.article}
                            gate={gate}
                            expanded={expandedGates.has(gate.article)}
                            onToggle={() => toggleGate(gate.article)}
                        />
                    ))}
                </CardContent>
            </Card>

            {/* Checklist */}
            <Card>
                <CardHeader>Verification Checklist</CardHeader>
                <CardContent>
                    <ChecklistSection
                        items={summary.checklist.items}
                        passed={summary.checklist.passed}
                        total={summary.checklist.total}
                    />
                </CardContent>
            </Card>
        </div>
    );
}

// ============ Compact QA Badge ============

interface QABadgeProps {
    status: 'passed' | 'warning' | 'failed';
    score?: number;
    onClick?: () => void;
}

export function QABadge({ status, score, onClick }: QABadgeProps) {
    const icons = {
        passed: '✅',
        warning: '⚠️',
        failed: '❌',
    };

    return (
        <span
            className={`qa-badge qa-badge-${status} ${onClick ? 'qa-badge-clickable' : ''}`}
            onClick={onClick}
        >
            {icons[status]} {score !== undefined ? `${Math.round(score * 100)}%` : status}
        </span>
    );
}

export default QADashboard;
