// TaskDAGViewer - Interactive DAG visualization for task dependencies
// Uses SVG for rendering and animation

import { useRef, useMemo, useCallback } from 'react';
import type { Task, DAGDefinition, StepStatus } from '../../types';

// ============ Types ============

interface TaskNode extends Task {
    x?: number;
    y?: number;
}

interface DAGViewerProps {
    tasks: Task[];
    dag: DAGDefinition;
    onTaskClick?: (taskId: string) => void;
    selectedTaskId?: string;
    className?: string;
}

// ============ Status Colors ============

const STATUS_COLORS: Record<StepStatus | 'default', string> = {
    pending: '#6b7280',   // gray
    running: '#3b82f6',   // blue
    completed: '#22c55e', // green
    failed: '#ef4444',    // red
    blocked: '#f59e0b',   // amber
    default: '#6b7280',
};

const STATUS_ICONS: Record<StepStatus | 'default', string> = {
    pending: '⏳',
    running: '🔄',
    completed: '✅',
    failed: '❌',
    blocked: '🚫',
    default: '⏳',
};

// ============ DAG Layout Algorithm ============

function computeLayout(tasks: Task[], dag: DAGDefinition): TaskNode[] {
    const nodeMap = new Map<string, TaskNode>();
    tasks.forEach(task => {
        nodeMap.set(task.id, { ...task, x: 0, y: 0 });
    });

    // Calculate depth for each node (longest path from root)
    const depths = new Map<string, number>();
    const inDegree = new Map<string, number>();

    dag.nodes.forEach(id => {
        inDegree.set(id, 0);
        depths.set(id, 0);
    });

    dag.edges.forEach(([, to]) => {
        inDegree.set(to, (inDegree.get(to) || 0) + 1);
    });

    // Find roots (nodes with no incoming edges)
    const roots = dag.nodes.filter(id => inDegree.get(id) === 0);
    const queue = [...roots];

    while (queue.length > 0) {
        const nodeId = queue.shift()!;
        const nodeDepth = depths.get(nodeId) || 0;

        // Find outgoing edges
        dag.edges
            .filter(([from]) => from === nodeId)
            .forEach(([, to]) => {
                const newDepth = nodeDepth + 1;
                if (newDepth > (depths.get(to) || 0)) {
                    depths.set(to, newDepth);
                }

                const remaining = (inDegree.get(to) || 0) - 1;
                inDegree.set(to, remaining);

                if (remaining === 0) {
                    queue.push(to);
                }
            });
    }

    // Group nodes by depth
    const levelGroups = new Map<number, string[]>();
    depths.forEach((depth, nodeId) => {
        if (!levelGroups.has(depth)) {
            levelGroups.set(depth, []);
        }
        levelGroups.get(depth)!.push(nodeId);
    });

    // Assign positions
    const nodeWidth = 140;
    const nodeHeight = 60;
    const horizontalGap = 40;
    const verticalGap = 80;

    levelGroups.forEach((nodeIds, depth) => {
        const levelWidth = nodeIds.length * nodeWidth + (nodeIds.length - 1) * horizontalGap;
        const startX = -levelWidth / 2 + nodeWidth / 2;

        nodeIds.forEach((nodeId, index) => {
            const node = nodeMap.get(nodeId);
            if (node) {
                node.x = startX + index * (nodeWidth + horizontalGap);
                node.y = depth * (nodeHeight + verticalGap);
            }
        });
    });

    return Array.from(nodeMap.values());
}

// ============ TaskDAGViewer Component ============

export function TaskDAGViewer({
    tasks,
    dag,
    onTaskClick,
    selectedTaskId,
    className = '',
}: DAGViewerProps) {
    const svgRef = useRef<SVGSVGElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Compute layout
    const layoutNodes = useMemo(() => computeLayout(tasks, dag), [tasks, dag]);

    // Calculate viewBox
    const viewBox = useMemo(() => {
        if (layoutNodes.length === 0) return '0 0 400 300';

        const padding = 80;
        const nodeWidth = 140;
        const nodeHeight = 50;

        const minX = Math.min(...layoutNodes.map(n => (n.x || 0) - nodeWidth / 2)) - padding;
        const maxX = Math.max(...layoutNodes.map(n => (n.x || 0) + nodeWidth / 2)) + padding;
        const minY = Math.min(...layoutNodes.map(n => (n.y || 0) - nodeHeight / 2)) - padding;
        const maxY = Math.max(...layoutNodes.map(n => (n.y || 0) + nodeHeight / 2)) + padding;

        return `${minX} ${minY} ${maxX - minX} ${maxY - minY}`;
    }, [layoutNodes]);

    // Handle node click
    const handleNodeClick = useCallback((taskId: string) => {
        onTaskClick?.(taskId);
    }, [onTaskClick]);

    if (tasks.length === 0) {
        return (
            <div className={`dag-viewer dag-empty ${className}`}>
                <div className="empty-state">
                    <span className="empty-icon">📊</span>
                    <p>No tasks to display</p>
                </div>
            </div>
        );
    }

    return (
        <div ref={containerRef} className={`dag-viewer ${className}`}>
            <svg ref={svgRef} viewBox={viewBox} className="dag-svg">
                {/* Marker for arrow heads */}
                <defs>
                    <marker
                        id="arrowhead"
                        markerWidth="10"
                        markerHeight="7"
                        refX="10"
                        refY="3.5"
                        orient="auto"
                    >
                        <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
                    </marker>
                </defs>

                {/* Edges */}
                <g className="dag-edges">
                    {dag.edges.map(([fromId, toId]) => {
                        const fromNode = layoutNodes.find(n => n.id === fromId);
                        const toNode = layoutNodes.find(n => n.id === toId);

                        if (!fromNode || !toNode) return null;

                        const fromX = fromNode.x || 0;
                        const fromY = (fromNode.y || 0) + 25; // bottom of node
                        const toX = toNode.x || 0;
                        const toY = (toNode.y || 0) - 25; // top of node

                        // Curved path
                        const midY = (fromY + toY) / 2;
                        const path = `M ${fromX} ${fromY} C ${fromX} ${midY}, ${toX} ${midY}, ${toX} ${toY}`;

                        return (
                            <path
                                key={`${fromId}-${toId}`}
                                d={path}
                                fill="none"
                                stroke="#9ca3af"
                                strokeWidth="2"
                                markerEnd="url(#arrowhead)"
                                className="dag-edge"
                            />
                        );
                    })}
                </g>

                {/* Nodes */}
                <g className="dag-nodes">
                    {layoutNodes.map(node => {
                        const status = node.status || 'pending';
                        const color = STATUS_COLORS[status] || STATUS_COLORS.default;
                        const icon = STATUS_ICONS[status] || STATUS_ICONS.default;
                        const isSelected = selectedTaskId === node.id;

                        return (
                            <g
                                key={node.id}
                                className={`dag-node ${isSelected ? 'dag-node-selected' : ''} ${status === 'running' ? 'dag-node-running' : ''}`}
                                transform={`translate(${node.x || 0}, ${node.y || 0})`}
                                onClick={() => handleNodeClick(node.id)}
                                style={{ cursor: onTaskClick ? 'pointer' : 'default' }}
                            >
                                {/* Node background */}
                                <rect
                                    x="-70"
                                    y="-25"
                                    width="140"
                                    height="50"
                                    rx="8"
                                    ry="8"
                                    fill={color}
                                    stroke={isSelected ? '#fff' : 'none'}
                                    strokeWidth={isSelected ? '3' : '0'}
                                    className="dag-node-bg"
                                />

                                {/* Task ID */}
                                <text
                                    x="-55"
                                    y="-5"
                                    fill="white"
                                    fontSize="12"
                                    fontWeight="600"
                                >
                                    {icon} {node.id}
                                </text>

                                {/* Task description (truncated) */}
                                <text
                                    x="-55"
                                    y="12"
                                    fill="rgba(255,255,255,0.8)"
                                    fontSize="10"
                                    className="dag-node-desc"
                                >
                                    {node.description.length > 18
                                        ? node.description.slice(0, 18) + '...'
                                        : node.description}
                                </text>

                                {/* Parallel indicator */}
                                {node.parallel && (
                                    <circle
                                        cx="55"
                                        cy="-15"
                                        r="8"
                                        fill="#fff"
                                        stroke={color}
                                        strokeWidth="2"
                                    />
                                )}
                            </g>
                        );
                    })}
                </g>
            </svg>

            {/* Legend */}
            <div className="dag-legend">
                {Object.entries(STATUS_COLORS)
                    .filter(([key]) => key !== 'default')
                    .map(([status, color]) => (
                        <div key={status} className="dag-legend-item">
                            <span className="dag-legend-dot" style={{ backgroundColor: color }} />
                            <span className="dag-legend-label">{status}</span>
                        </div>
                    ))}
            </div>
        </div>
    );
}

// ============ Compact DAG View (for cards) ============

interface CompactDAGProps {
    tasks: Task[];
    dag: DAGDefinition;
    className?: string;
}

export function CompactDAGView({ tasks, className = '' }: CompactDAGProps) {
    const statusCounts = useMemo(() => {
        const counts: Record<string, number> = {
            completed: 0,
            running: 0,
            pending: 0,
            failed: 0,
            blocked: 0,
        };

        tasks.forEach(task => {
            const status = task.status || 'pending';
            counts[status] = (counts[status] || 0) + 1;
        });

        return counts;
    }, [tasks]);

    const total = tasks.length;
    const completedPercent = total > 0 ? (statusCounts.completed / total) * 100 : 0;

    return (
        <div className={`compact-dag ${className}`}>
            <div className="compact-dag-bar">
                <div
                    className="compact-dag-fill"
                    style={{
                        width: `${completedPercent}%`,
                        backgroundColor: STATUS_COLORS.completed,
                    }}
                />
            </div>
            <div className="compact-dag-stats">
                <span className="compact-dag-stat">
                    <span style={{ color: STATUS_COLORS.completed }}>●</span> {statusCounts.completed}
                </span>
                <span className="compact-dag-stat">
                    <span style={{ color: STATUS_COLORS.running }}>●</span> {statusCounts.running}
                </span>
                <span className="compact-dag-stat">
                    <span style={{ color: STATUS_COLORS.pending }}>●</span> {statusCounts.pending}
                </span>
                {statusCounts.failed > 0 && (
                    <span className="compact-dag-stat">
                        <span style={{ color: STATUS_COLORS.failed }}>●</span> {statusCounts.failed}
                    </span>
                )}
            </div>
        </div>
    );
}

export default TaskDAGViewer;
