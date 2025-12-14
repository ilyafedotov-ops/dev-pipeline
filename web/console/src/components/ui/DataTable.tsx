
import React from 'react';
import { cn } from '@/lib/cn';

export interface Column<T> {
    header: string | React.ReactNode;
    accessorKey?: keyof T;
    cell?: (item: T) => React.ReactNode;
    className?: string;
}

interface DataTableProps<T> {
    data: T[];
    columns: Column<T>[];
    emptyMessage?: string;
    onRowClick?: (item: T) => void;
    className?: string;
}

export function DataTable<T>({
    data,
    columns,
    emptyMessage = 'No data available',
    onRowClick,
    className,
}: DataTableProps<T>) {
    return (
        <div className={cn('w-full overflow-auto', className)}>
            <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-bg-muted/50">
                    <tr>
                        {columns.map((col, idx) => (
                            <th
                                key={idx}
                                className={cn(
                                    'h-10 px-4 py-2 font-medium text-fg-muted',
                                    col.className
                                )}
                            >
                                {col.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-border">
                    {data.length === 0 ? (
                        <tr>
                            <td
                                colSpan={columns.length}
                                className="px-4 py-8 text-center text-fg-muted"
                            >
                                {emptyMessage}
                            </td>
                        </tr>
                    ) : (
                        data.map((item, rowIdx) => (
                            <tr
                                key={rowIdx}
                                onClick={() => onRowClick?.(item)}
                                className={cn(
                                    'transition-colors hover:bg-bg-muted/30',
                                    onRowClick && 'cursor-pointer'
                                )}
                            >
                                {columns.map((col, colIdx) => (
                                    <td key={colIdx} className={cn('p-4', col.className)}>
                                        {col.cell
                                            ? col.cell(item)
                                            : col.accessorKey
                                                ? (item[col.accessorKey] as React.ReactNode)
                                                : null}
                                    </td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}
