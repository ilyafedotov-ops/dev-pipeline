// UserStoryTracker - Visual tracker for user stories progress across phases
// Displays story cards with priorities and phase-based progress

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, Badge, ProgressBar, LoadingState, ErrorState } from '../common';

// ============ Types ============

interface UserStory {
    id: string;
    title: string;
    description: string;
    priority: 'P1' | 'P2' | 'P3';
    phase: string;
    status: 'backlog' | 'planned' | 'in_progress' | 'completed' | 'blocked';
    acceptance_criteria?: string[];
    tasks?: StoryTask[];
    created_at?: string;
}

interface StoryTask {
    id: string;
    description: string;
    completed: boolean;
}

interface UserStoryTrackerProps {
    protocolId?: number;
    projectId?: number;
    className?: string;
}

interface PhaseProgress {
    phase: string;
    total: number;
    completed: number;
    stories: UserStory[];
}

// ============ Constants ============

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
    P1: { bg: 'rgba(239, 68, 68, 0.1)', text: '#ef4444' },
    P2: { bg: 'rgba(245, 158, 11, 0.1)', text: '#f59e0b' },
    P3: { bg: 'rgba(107, 114, 128, 0.1)', text: '#6b7280' },
};

const STATUS_COLORS: Record<string, string> = {
    backlog: '#6b7280',
    planned: '#3b82f6',
    in_progress: '#f59e0b',
    completed: '#22c55e',
    blocked: '#ef4444',
};

const STATUS_LABELS: Record<string, string> = {
    backlog: 'Backlog',
    planned: 'Planned',
    in_progress: 'In Progress',
    completed: 'Completed',
    blocked: 'Blocked',
};

// ============ StoryCard Component ============

interface StoryCardProps {
    story: UserStory;
    onClick?: () => void;
    compact?: boolean;
}

function StoryCard({ story, onClick, compact = false }: StoryCardProps) {
    const priorityStyle = PRIORITY_COLORS[story.priority] || PRIORITY_COLORS.P3;
    const completedTasks = story.tasks?.filter(t => t.completed).length || 0;
    const totalTasks = story.tasks?.length || 0;

    return (
        <div
            className={`story-card ${compact ? 'story-card-compact' : ''} story-status-${story.status}`}
            onClick={onClick}
        >
            <div className="story-card-header">
                <span className="story-id">{story.id}</span>
                <span
                    className="story-priority"
                    style={{ backgroundColor: priorityStyle.bg, color: priorityStyle.text }}
                >
                    {story.priority}
                </span>
            </div>

            <h4 className="story-title">{story.title}</h4>

            {!compact && (
                <p className="story-description">{story.description}</p>
            )}

            <div className="story-card-footer">
                <span
                    className="story-status"
                    style={{ color: STATUS_COLORS[story.status] }}
                >
                    {STATUS_LABELS[story.status]}
                </span>

                {totalTasks > 0 && (
                    <span className="story-tasks-count">
                        {completedTasks}/{totalTasks} tasks
                    </span>
                )}
            </div>

            {!compact && totalTasks > 0 && (
                <div className="story-progress">
                    <ProgressBar
                        value={totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0}
                    />
                </div>
            )}
        </div>
    );
}

// ============ PhaseColumn Component ============

interface PhaseColumnProps {
    phase: PhaseProgress;
    onStoryClick?: (story: UserStory) => void;
}

function PhaseColumn({ phase, onStoryClick }: PhaseColumnProps) {
    const progressPercent = phase.total > 0
        ? Math.round((phase.completed / phase.total) * 100)
        : 0;

    return (
        <div className="phase-column">
            <div className="phase-header">
                <h3 className="phase-name">{phase.phase}</h3>
                <span className="phase-count">{phase.stories.length}</span>
            </div>

            <div className="phase-progress">
                <ProgressBar value={progressPercent} />
                <span className="phase-progress-text">{progressPercent}%</span>
            </div>

            <div className="phase-stories">
                {phase.stories.map(story => (
                    <StoryCard
                        key={story.id}
                        story={story}
                        compact
                        onClick={() => onStoryClick?.(story)}
                    />
                ))}
                {phase.stories.length === 0 && (
                    <div className="phase-empty">No stories</div>
                )}
            </div>
        </div>
    );
}

// ============ StoryDetailModal Component ============

interface StoryDetailProps {
    story: UserStory;
    onClose: () => void;
    onTaskToggle?: (taskId: string, completed: boolean) => void;
}

function StoryDetail({ story, onClose, onTaskToggle }: StoryDetailProps) {
    const priorityStyle = PRIORITY_COLORS[story.priority] || PRIORITY_COLORS.P3;
    const completedTasks = story.tasks?.filter(t => t.completed).length || 0;
    const totalTasks = story.tasks?.length || 0;

    return (
        <div className="story-detail-overlay" onClick={onClose}>
            <div className="story-detail" onClick={e => e.stopPropagation()}>
                <div className="story-detail-header">
                    <div className="story-detail-meta">
                        <span className="story-id">{story.id}</span>
                        <span
                            className="story-priority"
                            style={{ backgroundColor: priorityStyle.bg, color: priorityStyle.text }}
                        >
                            {story.priority}
                        </span>
                        <Badge
                            variant={story.status === 'completed' ? 'success' : story.status === 'blocked' ? 'error' : 'info'}
                        >
                            {STATUS_LABELS[story.status]}
                        </Badge>
                    </div>
                    <button className="story-detail-close" onClick={onClose}>×</button>
                </div>

                <h2 className="story-detail-title">{story.title}</h2>
                <p className="story-detail-description">{story.description}</p>

                {story.acceptance_criteria && story.acceptance_criteria.length > 0 && (
                    <div className="story-criteria">
                        <h4>Acceptance Criteria</h4>
                        <ul>
                            {story.acceptance_criteria.map((criterion, idx) => (
                                <li key={idx}>{criterion}</li>
                            ))}
                        </ul>
                    </div>
                )}

                {story.tasks && story.tasks.length > 0 && (
                    <div className="story-tasks">
                        <h4>Tasks ({completedTasks}/{totalTasks})</h4>
                        <div className="story-tasks-list">
                            {story.tasks.map(task => (
                                <label key={task.id} className="story-task-item">
                                    <input
                                        type="checkbox"
                                        checked={task.completed}
                                        onChange={(e) => onTaskToggle?.(task.id, e.target.checked)}
                                    />
                                    <span className={task.completed ? 'task-completed' : ''}>
                                        {task.description}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </div>
                )}

                <div className="story-detail-footer">
                    <span className="story-phase">Phase: {story.phase}</span>
                    {story.created_at && (
                        <span className="story-date">
                            Created: {new Date(story.created_at).toLocaleDateString()}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}

// ============ Main UserStoryTracker Component ============

export function UserStoryTracker({ protocolId, projectId, className = '' }: UserStoryTrackerProps) {
    const [stories, setStories] = useState<UserStory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedStory, setSelectedStory] = useState<UserStory | null>(null);
    const [viewMode, setViewMode] = useState<'board' | 'list'>('board');

    const loadStories = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // In real implementation, fetch from API
            // For now, use sample data until API is ready
            const sampleStories: UserStory[] = [
                {
                    id: 'US-001',
                    title: 'User Authentication',
                    description: 'Implement user login and registration flow',
                    priority: 'P1',
                    phase: 'Foundation',
                    status: 'completed',
                    tasks: [
                        { id: 't1', description: 'Design login page', completed: true },
                        { id: 't2', description: 'Implement auth API', completed: true },
                        { id: 't3', description: 'Add session management', completed: true },
                    ],
                },
                {
                    id: 'US-002',
                    title: 'Dashboard Overview',
                    description: 'Create main dashboard with project statistics',
                    priority: 'P1',
                    phase: 'Foundation',
                    status: 'completed',
                    tasks: [
                        { id: 't4', description: 'Design dashboard layout', completed: true },
                        { id: 't5', description: 'Implement stats cards', completed: true },
                    ],
                },
                {
                    id: 'US-003',
                    title: 'Protocol Visualization',
                    description: 'Build interactive DAG viewer for task dependencies',
                    priority: 'P1',
                    phase: 'Core Features',
                    status: 'in_progress',
                    tasks: [
                        { id: 't6', description: 'Create DAG component', completed: true },
                        { id: 't7', description: 'Add node interactions', completed: true },
                        { id: 't8', description: 'Implement zoom/pan', completed: false },
                    ],
                },
                {
                    id: 'US-004',
                    title: 'Quality Dashboard',
                    description: 'Display constitutional gates and quality metrics',
                    priority: 'P2',
                    phase: 'Core Features',
                    status: 'in_progress',
                    tasks: [
                        { id: 't9', description: 'Design QA dashboard', completed: true },
                        { id: 't10', description: 'Add gate cards', completed: false },
                    ],
                },
                {
                    id: 'US-005',
                    title: 'Agent Configuration',
                    description: 'Allow users to configure AI agents per step',
                    priority: 'P2',
                    phase: 'Advanced',
                    status: 'planned',
                },
                {
                    id: 'US-006',
                    title: 'Real-time Updates',
                    description: 'Implement SSE for live status updates',
                    priority: 'P3',
                    phase: 'Advanced',
                    status: 'backlog',
                },
            ];

            setStories(sampleStories);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load stories');
        } finally {
            setLoading(false);
        }
    }, [protocolId, projectId]);

    useEffect(() => {
        loadStories();
    }, [loadStories]);

    // Group stories by phase
    const phaseProgress = useMemo((): PhaseProgress[] => {
        const phases = new Map<string, UserStory[]>();

        stories.forEach(story => {
            const existing = phases.get(story.phase) || [];
            phases.set(story.phase, [...existing, story]);
        });

        return Array.from(phases.entries()).map(([phase, phaseStories]) => ({
            phase,
            total: phaseStories.length,
            completed: phaseStories.filter(s => s.status === 'completed').length,
            stories: phaseStories,
        }));
    }, [stories]);

    // Calculate overall stats
    const stats = useMemo(() => {
        const total = stories.length;
        const completed = stories.filter(s => s.status === 'completed').length;
        const inProgress = stories.filter(s => s.status === 'in_progress').length;
        const blocked = stories.filter(s => s.status === 'blocked').length;

        return { total, completed, inProgress, blocked };
    }, [stories]);

    const handleTaskToggle = async (taskId: string, completed: boolean) => {
        if (!selectedStory) return;

        // Update locally
        setSelectedStory(prev => {
            if (!prev?.tasks) return prev;
            return {
                ...prev,
                tasks: prev.tasks.map(t =>
                    t.id === taskId ? { ...t, completed } : t
                ),
            };
        });

        // In real implementation, save to API
        console.log(`Task ${taskId} marked as ${completed ? 'completed' : 'incomplete'}`);
    };

    if (loading) {
        return (
            <Card className={`user-story-tracker ${className}`}>
                <LoadingState text="Loading user stories..." />
            </Card>
        );
    }

    if (error) {
        return (
            <Card className={`user-story-tracker ${className}`}>
                <ErrorState message={error} retry={loadStories} />
            </Card>
        );
    }

    return (
        <div className={`user-story-tracker ${className}`}>
            {/* Header with stats */}
            <Card className="tracker-header-card">
                <div className="tracker-header">
                    <div className="tracker-title">
                        <h2>User Stories</h2>
                        <span className="tracker-count">{stats.total} stories</span>
                    </div>
                    <div className="tracker-controls">
                        <div className="view-toggle">
                            <button
                                className={`view-btn ${viewMode === 'board' ? 'active' : ''}`}
                                onClick={() => setViewMode('board')}
                            >
                                📊 Board
                            </button>
                            <button
                                className={`view-btn ${viewMode === 'list' ? 'active' : ''}`}
                                onClick={() => setViewMode('list')}
                            >
                                📋 List
                            </button>
                        </div>
                    </div>
                </div>

                <div className="tracker-stats">
                    <div className="tracker-stat">
                        <span className="stat-value stat-completed">{stats.completed}</span>
                        <span className="stat-label">Completed</span>
                    </div>
                    <div className="tracker-stat">
                        <span className="stat-value stat-progress">{stats.inProgress}</span>
                        <span className="stat-label">In Progress</span>
                    </div>
                    <div className="tracker-stat">
                        <span className="stat-value stat-blocked">{stats.blocked}</span>
                        <span className="stat-label">Blocked</span>
                    </div>
                    <div className="tracker-stat">
                        <span className="stat-value">{stats.total - stats.completed}</span>
                        <span className="stat-label">Remaining</span>
                    </div>
                </div>

                <ProgressBar
                    value={stats.total > 0 ? (stats.completed / stats.total) * 100 : 0}
                    className="overall-progress"
                />
            </Card>

            {/* Board View */}
            {viewMode === 'board' && (
                <div className="tracker-board">
                    {phaseProgress.map(phase => (
                        <PhaseColumn
                            key={phase.phase}
                            phase={phase}
                            onStoryClick={setSelectedStory}
                        />
                    ))}
                </div>
            )}

            {/* List View */}
            {viewMode === 'list' && (
                <Card className="tracker-list">
                    <CardContent>
                        {stories.map(story => (
                            <StoryCard
                                key={story.id}
                                story={story}
                                onClick={() => setSelectedStory(story)}
                            />
                        ))}
                    </CardContent>
                </Card>
            )}

            {/* Story Detail Modal */}
            {selectedStory && (
                <StoryDetail
                    story={selectedStory}
                    onClose={() => setSelectedStory(null)}
                    onTaskToggle={handleTaskToggle}
                />
            )}
        </div>
    );
}

// ============ Compact User Story Badge ============

interface StoryBadgeProps {
    count: number;
    completed: number;
    onClick?: () => void;
}

export function UserStoryBadge({ count, completed, onClick }: StoryBadgeProps) {
    const percent = count > 0 ? Math.round((completed / count) * 100) : 0;

    return (
        <span
            className={`story-badge ${onClick ? 'story-badge-clickable' : ''}`}
            onClick={onClick}
        >
            📖 {completed}/{count} ({percent}%)
        </span>
    );
}

export default UserStoryTracker;
