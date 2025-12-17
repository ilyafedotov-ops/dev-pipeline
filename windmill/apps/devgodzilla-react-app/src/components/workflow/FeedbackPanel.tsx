// FeedbackPanel - Displays feedback loop events and handles clarifications
// Shows blocking issues, clarification requests, and resolution actions

import { useState, useEffect, useCallback } from 'react';
import type { FeedbackEvent, Clarification } from '../../types';
import { api } from '../../api/client';
import { Card, CardHeader, CardContent, Button, Badge, LoadingState, ErrorState } from '../common';

// ============ Types ============

interface FeedbackPanelProps {
    protocolId: number;
    onClarificationAnswer?: (clarificationId: number, answer: string) => void;
    className?: string;
}

// ============ Action Icons ============

const ACTION_ICONS: Record<string, string> = {
    clarify: '❓',
    clarification_created: '❓',
    re_plan: '📋',
    re_specify: '📝',
    retry: '🔄',
};

const ACTION_COLORS: Record<string, string> = {
    clarify: '#f59e0b',
    clarification_created: '#f59e0b',
    re_plan: '#3b82f6',
    re_specify: '#8b5cf6',
    retry: '#6b7280',
};

// ============ ClarificationCard Component ============

interface ClarificationCardProps {
    clarification: Clarification;
    onAnswer: (answer: string) => void;
    loading?: boolean;
}

function ClarificationCard({ clarification, onAnswer, loading = false }: ClarificationCardProps) {
    const [customAnswer, setCustomAnswer] = useState('');
    const [showCustom, setShowCustom] = useState(false);

    const handleOptionClick = (option: string) => {
        onAnswer(option);
    };

    const handleCustomSubmit = () => {
        if (customAnswer.trim()) {
            onAnswer(customAnswer.trim());
        }
    };

    return (
        <div className={`clarification-card ${clarification.blocking ? 'clarification-blocking' : ''}`}>
            <div className="clarification-header">
                <span className="clarification-icon">❓</span>
                <div className="clarification-info">
                    <h4 className="clarification-question">{clarification.question}</h4>
                    <span className="clarification-key">Key: {clarification.key}</span>
                </div>
                {clarification.blocking && (
                    <Badge variant="error">BLOCKING</Badge>
                )}
            </div>

            {clarification.status === 'open' && (
                <div className="clarification-actions">
                    {/* Recommended option */}
                    {clarification.recommended && (
                        <div className="clarification-recommended">
                            <span className="recommended-label">Recommended:</span>
                            <Button
                                variant="primary"
                                onClick={() => handleOptionClick(clarification.recommended!.value)}
                                disabled={loading}
                            >
                                {clarification.recommended.value}
                            </Button>
                            <span className="recommended-reason">{clarification.recommended.reason}</span>
                        </div>
                    )}

                    {/* Option buttons */}
                    {clarification.options && clarification.options.length > 0 && (
                        <div className="clarification-options">
                            {clarification.options
                                .filter(opt => opt !== clarification.recommended?.value)
                                .map((option, idx) => (
                                    <Button
                                        key={idx}
                                        variant="secondary"
                                        onClick={() => handleOptionClick(option)}
                                        disabled={loading}
                                    >
                                        {option}
                                    </Button>
                                ))}
                        </div>
                    )}

                    {/* Custom answer */}
                    <div className="clarification-custom">
                        {showCustom ? (
                            <div className="custom-input-group">
                                <input
                                    type="text"
                                    value={customAnswer}
                                    onChange={(e) => setCustomAnswer(e.target.value)}
                                    placeholder="Enter custom answer..."
                                    className="form-input"
                                />
                                <Button
                                    variant="primary"
                                    onClick={handleCustomSubmit}
                                    disabled={!customAnswer.trim() || loading}
                                >
                                    Submit
                                </Button>
                                <Button variant="secondary" onClick={() => setShowCustom(false)}>
                                    Cancel
                                </Button>
                            </div>
                        ) : (
                            <Button variant="ghost" onClick={() => setShowCustom(true)}>
                                Enter custom answer...
                            </Button>
                        )}
                    </div>
                </div>
            )}

            {clarification.status === 'answered' && clarification.answer && (
                <div className="clarification-answer">
                    <span className="answer-label">Answer:</span>
                    <span className="answer-value">{clarification.answer}</span>
                </div>
            )}
        </div>
    );
}

// ============ FeedbackEventCard Component ============

interface FeedbackEventCardProps {
    event: FeedbackEvent;
    onClarificationAnswer?: (clarificationId: number, answer: string) => void;
}

function FeedbackEventCard({ event, onClarificationAnswer }: FeedbackEventCardProps) {
    const icon = ACTION_ICONS[event.action_taken] || '📌';
    const color = ACTION_COLORS[event.action_taken] || '#6b7280';
    const timeAgo = formatTimeAgo(event.created_at);

    return (
        <div className={`feedback-event ${event.resolved ? 'feedback-resolved' : ''}`}>
            <div className="feedback-event-header">
                <span
                    className="feedback-event-icon"
                    style={{ backgroundColor: color }}
                >
                    {icon}
                </span>
                <div className="feedback-event-info">
                    <span className="feedback-action">{event.action_taken.replace('_', ' ')}</span>
                    <span className="feedback-time">{timeAgo}</span>
                </div>
                {event.resolved ? (
                    <Badge variant="success">RESOLVED</Badge>
                ) : (
                    <Badge variant="warning">PENDING</Badge>
                )}
            </div>

            {event.clarification && onClarificationAnswer && (
                <ClarificationCard
                    clarification={event.clarification}
                    onAnswer={(answer) => onClarificationAnswer(event.clarification!.id, answer)}
                />
            )}
        </div>
    );
}

// ============ Time Formatting ============

function formatTimeAgo(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

// ============ Main FeedbackPanel Component ============

export function FeedbackPanel({
    protocolId,
    onClarificationAnswer,
    className = '',
}: FeedbackPanelProps) {
    const [events, setEvents] = useState<FeedbackEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadFeedback = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await api.feedback.list(protocolId);
            setEvents(result.events || []);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load feedback');
        } finally {
            setLoading(false);
        }
    }, [protocolId]);

    useEffect(() => {
        loadFeedback();
    }, [loadFeedback]);

    const handleAnswer = async (clarificationId: number, answer: string) => {
        try {
            await api.clarifications.answer(clarificationId, answer);
            onClarificationAnswer?.(clarificationId, answer);
            // Reload to get updated state
            await loadFeedback();
        } catch (e) {
            console.error('Failed to submit answer:', e);
        }
    };

    const pendingCount = events.filter(e => !e.resolved).length;
    const blockingCount = events.filter(e => e.clarification?.blocking && e.clarification.status === 'open').length;

    if (loading) {
        return (
            <Card className={`feedback-panel ${className}`}>
                <LoadingState text="Loading feedback..." />
            </Card>
        );
    }

    if (error) {
        return (
            <Card className={`feedback-panel ${className}`}>
                <ErrorState message={error} retry={loadFeedback} />
            </Card>
        );
    }

    return (
        <Card className={`feedback-panel ${className}`}>
            <CardHeader
                action={
                    <div className="feedback-stats">
                        {blockingCount > 0 && (
                            <Badge variant="error">{blockingCount} blocking</Badge>
                        )}
                        {pendingCount > 0 && (
                            <Badge variant="warning">{pendingCount} pending</Badge>
                        )}
                    </div>
                }
            >
                Feedback Loop
            </CardHeader>
            <CardContent>
                {events.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">✨</span>
                        <p>No feedback events</p>
                    </div>
                ) : (
                    <div className="feedback-events">
                        {events.map(event => (
                            <FeedbackEventCard
                                key={event.id}
                                event={event}
                                onClarificationAnswer={handleAnswer}
                            />
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// ============ Compact Feedback Indicator ============

interface FeedbackIndicatorProps {
    pendingCount: number;
    blockingCount: number;
    onClick?: () => void;
}

export function FeedbackIndicator({ pendingCount, blockingCount, onClick }: FeedbackIndicatorProps) {
    if (pendingCount === 0 && blockingCount === 0) {
        return null;
    }

    return (
        <span
            className={`feedback-indicator ${onClick ? 'feedback-indicator-clickable' : ''}`}
            onClick={onClick}
        >
            {blockingCount > 0 ? (
                <span className="indicator-blocking">🔴 {blockingCount}</span>
            ) : (
                <span className="indicator-pending">🟡 {pendingCount}</span>
            )}
        </span>
    );
}

export default FeedbackPanel;
