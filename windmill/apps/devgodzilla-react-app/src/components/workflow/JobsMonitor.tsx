// JobsMonitor - Component for monitoring job executions
// Shows running jobs, recent history, and real-time status updates

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardHeader, CardContent, Badge, ProgressBar, Button, LoadingState, ErrorState } from '../common';

// ============ Types ============

interface Job {
    id: number;
    protocol_id: number;
    status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
    started_at?: string;
    completed_at?: string;
    duration_ms?: number;
    progress?: number;
    current_step?: string;
    error?: string;
}

interface JobsMonitorProps {
    protocolId?: number;
    projectId?: number;
    limit?: number;
    showHistory?: boolean;
    className?: string;
}

// ============ Constants ============

const STATUS_COLORS: Record<string, string> = {
    queued: '#6b7280',
    running: '#3b82f6',
    completed: '#22c55e',
    failed: '#ef4444',
    cancelled: '#9ca3af',
};

const STATUS_ICONS: Record<string, string> = {
    queued: '⏳',
    running: '🔄',
    completed: '✅',
    failed: '❌',
    cancelled: '🚫',
};

// ============ JobCard Component ============

interface JobCardProps {
    job: Job;
    onClick?: () => void;
    expanded?: boolean;
}

function JobCard({ job, onClick, expanded = false }: JobCardProps) {
    const statusColor = STATUS_COLORS[job.status] || '#6b7280';
    const statusIcon = STATUS_ICONS[job.status] || '⏳';

    const formatDuration = (ms?: number) => {
        if (!ms) return '—';
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
    };

    const formatTime = (dateStr?: string) => {
        if (!dateStr) return '—';
        const date = new Date(dateStr);
        return date.toLocaleTimeString();
    };

    return (
        <div
            className={`job-card job-status-${job.status} ${expanded ? 'job-card-expanded' : ''}`}
            onClick={onClick}
        >
            <div className="job-card-header">
                <div className="job-info">
                    <span className="job-icon" style={{ color: statusColor }}>
                        {statusIcon}
                    </span>
                    <div className="job-details">
                        <span className="job-id">Job #{job.id}</span>
                        <span className="job-protocol">Protocol #{job.protocol_id}</span>
                    </div>
                </div>
                <Badge
                    variant={job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'info'}
                >
                    {job.status}
                </Badge>
            </div>

            {job.status === 'running' && (
                <div className="job-progress">
                    <ProgressBar value={job.progress || 0} />
                    {job.current_step && (
                        <span className="job-current-step">{job.current_step}</span>
                    )}
                </div>
            )}

            <div className="job-card-footer">
                <span className="job-time">
                    Started: {formatTime(job.started_at)}
                </span>
                <span className="job-duration">
                    Duration: {formatDuration(job.duration_ms)}
                </span>
            </div>

            {expanded && job.error && (
                <div className="job-error">
                    <span className="error-label">Error:</span>
                    <pre className="error-message">{job.error}</pre>
                </div>
            )}
        </div>
    );
}

// ============ RunningJobsPanel Component ============

interface RunningJobsPanelProps {
    jobs: Job[];
    onJobClick?: (job: Job) => void;
}

function RunningJobsPanel({ jobs, onJobClick }: RunningJobsPanelProps) {
    const runningJobs = jobs.filter(j => j.status === 'running' || j.status === 'queued');

    if (runningJobs.length === 0) {
        return (
            <Card className="running-jobs-panel">
                <CardContent>
                    <div className="no-running-jobs">
                        <span className="no-jobs-icon">💤</span>
                        <p>No jobs currently running</p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="running-jobs-panel">
            <CardHeader>
                <span className="running-indicator">🔴</span>
                Running Jobs ({runningJobs.length})
            </CardHeader>
            <CardContent>
                <div className="running-jobs-list">
                    {runningJobs.map(job => (
                        <JobCard
                            key={job.id}
                            job={job}
                            onClick={() => onJobClick?.(job)}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ============ JobHistory Component ============

interface JobHistoryProps {
    jobs: Job[];
    onJobClick?: (job: Job) => void;
}

function JobHistory({ jobs, onJobClick }: JobHistoryProps) {
    const completedJobs = jobs.filter(j =>
        j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled'
    );

    const stats = useMemo(() => {
        const completed = completedJobs.filter(j => j.status === 'completed').length;
        const failed = completedJobs.filter(j => j.status === 'failed').length;
        const avgDuration = completedJobs.length > 0
            ? completedJobs.reduce((sum, j) => sum + (j.duration_ms || 0), 0) / completedJobs.length
            : 0;

        return { completed, failed, avgDuration };
    }, [completedJobs]);

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${Math.round(ms)}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        return `${Math.floor(ms / 60000)}m`;
    };

    return (
        <Card className="job-history">
            <CardHeader>
                Job History ({completedJobs.length})
            </CardHeader>
            <CardContent>
                <div className="history-stats">
                    <div className="history-stat">
                        <span className="stat-value stat-success">{stats.completed}</span>
                        <span className="stat-label">Completed</span>
                    </div>
                    <div className="history-stat">
                        <span className="stat-value stat-error">{stats.failed}</span>
                        <span className="stat-label">Failed</span>
                    </div>
                    <div className="history-stat">
                        <span className="stat-value">{formatDuration(stats.avgDuration)}</span>
                        <span className="stat-label">Avg Duration</span>
                    </div>
                </div>

                <div className="history-list">
                    {completedJobs.slice(0, 10).map(job => (
                        <JobCard
                            key={job.id}
                            job={job}
                            onClick={() => onJobClick?.(job)}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ============ Main JobsMonitor Component ============

export function JobsMonitor({
    protocolId,
    projectId,
    limit = 20,
    showHistory = true,
    className = ''
}: JobsMonitorProps) {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedJob, setSelectedJob] = useState<Job | null>(null);

    const loadJobs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // In real implementation, fetch from API
            // For now, use sample data
            const sampleJobs: Job[] = [
                {
                    id: 101,
                    protocol_id: 1,
                    status: 'running',
                    started_at: new Date(Date.now() - 45000).toISOString(),
                    progress: 65,
                    current_step: 'Running tests',
                },
                {
                    id: 100,
                    protocol_id: 1,
                    status: 'completed',
                    started_at: new Date(Date.now() - 120000).toISOString(),
                    completed_at: new Date(Date.now() - 60000).toISOString(),
                    duration_ms: 60000,
                },
                {
                    id: 99,
                    protocol_id: 2,
                    status: 'failed',
                    started_at: new Date(Date.now() - 300000).toISOString(),
                    completed_at: new Date(Date.now() - 280000).toISOString(),
                    duration_ms: 20000,
                    error: 'Test assertion failed: expected 200 but got 500',
                },
                {
                    id: 98,
                    protocol_id: 1,
                    status: 'completed',
                    started_at: new Date(Date.now() - 600000).toISOString(),
                    completed_at: new Date(Date.now() - 550000).toISOString(),
                    duration_ms: 50000,
                },
                {
                    id: 97,
                    protocol_id: 3,
                    status: 'queued',
                    started_at: new Date().toISOString(),
                },
            ];

            setJobs(sampleJobs);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load jobs');
        } finally {
            setLoading(false);
        }
    }, [protocolId, projectId, limit]);

    useEffect(() => {
        loadJobs();
        // In real implementation, set up SSE for real-time updates
        const interval = setInterval(loadJobs, 10000); // Polling fallback
        return () => clearInterval(interval);
    }, [loadJobs]);

    if (loading) {
        return (
            <Card className={`jobs-monitor ${className}`}>
                <LoadingState text="Loading jobs..." />
            </Card>
        );
    }

    if (error) {
        return (
            <Card className={`jobs-monitor ${className}`}>
                <ErrorState message={error} retry={loadJobs} />
            </Card>
        );
    }

    return (
        <div className={`jobs-monitor ${className}`}>
            <RunningJobsPanel
                jobs={jobs}
                onJobClick={setSelectedJob}
            />

            {showHistory && (
                <JobHistory
                    jobs={jobs}
                    onJobClick={setSelectedJob}
                />
            )}

            {/* Job Detail Modal */}
            {selectedJob && (
                <div className="job-detail-overlay" onClick={() => setSelectedJob(null)}>
                    <div className="job-detail" onClick={e => e.stopPropagation()}>
                        <div className="job-detail-header">
                            <h2>Job #{selectedJob.id}</h2>
                            <button
                                className="job-detail-close"
                                onClick={() => setSelectedJob(null)}
                            >
                                ×
                            </button>
                        </div>
                        <JobCard job={selectedJob} expanded />
                        <div className="job-detail-actions">
                            <Button
                                variant="secondary"
                                onClick={() => setSelectedJob(null)}
                            >
                                Close
                            </Button>
                            {selectedJob.status === 'running' && (
                                <Button variant="secondary">
                                    Cancel Job
                                </Button>
                            )}
                            {selectedJob.status === 'failed' && (
                                <Button variant="primary">
                                    Retry Job
                                </Button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ============ Compact Job Badge ============

interface JobBadgeProps {
    runningCount: number;
    queuedCount: number;
    onClick?: () => void;
}

export function JobBadge({ runningCount, queuedCount, onClick }: JobBadgeProps) {
    const total = runningCount + queuedCount;

    if (total === 0) {
        return null;
    }

    return (
        <span
            className={`job-badge ${onClick ? 'job-badge-clickable' : ''}`}
            onClick={onClick}
        >
            {runningCount > 0 && <span className="job-badge-running">🔄 {runningCount}</span>}
            {queuedCount > 0 && <span className="job-badge-queued">⏳ {queuedCount}</span>}
        </span>
    );
}

export default JobsMonitor;
