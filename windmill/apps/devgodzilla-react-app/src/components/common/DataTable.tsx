// Data Table Component
// Reusable table with sorting, filtering, and row actions

import { ReactNode, useState, useMemo } from 'react';

// ============ Types ============

export interface Column<T> {
    key: keyof T | string;
    header: string;
    width?: string;
    render?: (row: T, index: number) => ReactNode;
    sortable?: boolean;
    align?: 'left' | 'center' | 'right';
}

interface DataTableProps<T> {
    columns: Column<T>[];
    data: T[];
    keyField: keyof T;
    onRowClick?: (row: T) => void;
    emptyMessage?: string;
    loading?: boolean;
    className?: string;
}

type SortDirection = 'asc' | 'desc' | null;

// ============ DataTable Component ============

export function DataTable<T extends Record<string, unknown>>({
    columns,
    data,
    keyField,
    onRowClick,
    emptyMessage = 'No data available',
    loading = false,
    className = '',
}: DataTableProps<T>) {
    const [sortColumn, setSortColumn] = useState<string | null>(null);
    const [sortDirection, setSortDirection] = useState<SortDirection>(null);

    const handleSort = (columnKey: string) => {
        if (sortColumn === columnKey) {
            if (sortDirection === 'asc') {
                setSortDirection('desc');
            } else if (sortDirection === 'desc') {
                setSortColumn(null);
                setSortDirection(null);
            }
        } else {
            setSortColumn(columnKey);
            setSortDirection('asc');
        }
    };

    const sortedData = useMemo(() => {
        if (!sortColumn || !sortDirection) return data;

        return [...data].sort((a, b) => {
            const aVal = a[sortColumn];
            const bVal = b[sortColumn];

            if (aVal === bVal) return 0;
            if (aVal === null || aVal === undefined) return 1;
            if (bVal === null || bVal === undefined) return -1;

            const comparison = aVal < bVal ? -1 : 1;
            return sortDirection === 'asc' ? comparison : -comparison;
        });
    }, [data, sortColumn, sortDirection]);

    const getSortIcon = (columnKey: string) => {
        if (sortColumn !== columnKey) return '↕';
        if (sortDirection === 'asc') return '↑';
        if (sortDirection === 'desc') return '↓';
        return '↕';
    };

    const getValue = (row: T, key: string): unknown => {
        if (key.includes('.')) {
            const keys = key.split('.');
            let value: unknown = row;
            for (const k of keys) {
                if (value && typeof value === 'object' && k in value) {
                    value = (value as Record<string, unknown>)[k];
                } else {
                    return undefined;
                }
            }
            return value;
        }
        return row[key];
    };

    if (loading) {
        return (
            <div className={`wm-card ${className}`}>
                <div className="loading-state">Loading...</div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className={`wm-card ${className}`}>
                <div className="empty-state">{emptyMessage}</div>
            </div>
        );
    }

    return (
        <div className={`wm-card table-container ${className}`} style={{ overflow: 'hidden' }}>
            <table className="data-table">
                <thead>
                    <tr>
                        {columns.map(col => (
                            <th
                                key={String(col.key)}
                                style={{
                                    width: col.width,
                                    textAlign: col.align || 'left',
                                    cursor: col.sortable ? 'pointer' : undefined,
                                }}
                                onClick={col.sortable ? () => handleSort(String(col.key)) : undefined}
                            >
                                {col.header}
                                {col.sortable && (
                                    <span className="sort-icon"> {getSortIcon(String(col.key))}</span>
                                )}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {sortedData.map((row, index) => (
                        <tr
                            key={String(row[keyField])}
                            onClick={onRowClick ? () => onRowClick(row) : undefined}
                            className={onRowClick ? 'clickable-row' : ''}
                        >
                            {columns.map(col => (
                                <td
                                    key={String(col.key)}
                                    style={{ textAlign: col.align || 'left' }}
                                >
                                    {col.render
                                        ? col.render(row, index)
                                        : String(getValue(row, String(col.key)) ?? '—')}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ============ Simple List Component ============

interface ListItemProps {
    children: ReactNode;
    onClick?: () => void;
    hover?: boolean;
    className?: string;
}

export function ListItem({ children, onClick, hover = true, className = '' }: ListItemProps) {
    return (
        <div
            className={`list-item ${hover ? 'list-item-hover' : ''} ${className}`}
            onClick={onClick}
            style={{ cursor: onClick ? 'pointer' : undefined }}
        >
            {children}
        </div>
    );
}

interface ListProps {
    children: ReactNode;
    className?: string;
}

export function List({ children, className = '' }: ListProps) {
    return <div className={`list ${className}`}>{children}</div>;
}
