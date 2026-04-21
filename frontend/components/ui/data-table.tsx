"use client";

import { Fragment, type ReactNode, type Ref,useMemo, useState } from "react";

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, Download, Filter, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  onRowClick?: (row: TData) => void;
  className?: string;
  enableSearch?: boolean;
  searchPlaceholder?: string;
  enableExport?: boolean;
  exportFilename?: string;
  enableColumnFilters?: boolean;
  searchAccessor?: (row: TData) => string;
  toolbarLeadingContent?: ReactNode;
  toolbarTrailingContent?: ReactNode;
  tableContainerClassName?: string;
  tableContainerRef?: Ref<HTMLDivElement>;
  stickyHeader?: boolean;
  emptyMessage?: string;
  isRowExpanded?: (row: TData) => boolean;
  renderExpandedContent?: (row: TData) => ReactNode;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  onRowClick,
  className,
  enableSearch = false,
  searchPlaceholder = "Search...",
  enableExport = false,
  exportFilename = "export.csv",
  enableColumnFilters = false,
  searchAccessor,
  toolbarLeadingContent,
  toolbarTrailingContent,
  tableContainerClassName,
  tableContainerRef,
  stickyHeader = false,
  emptyMessage = "No results.",
  isRowExpanded,
  renderExpandedContent,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [search, setSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});

  const filterableColumns = useMemo(() => {
    return columns
      .map((col) => {
        const accessorKey = (col as unknown as { accessorKey?: unknown }).accessorKey;
        if (typeof accessorKey !== "string") return null;
        const id = (col as unknown as { id?: unknown }).id;
        const columnId = typeof id === "string" ? id : accessorKey;
        return { columnId, accessorKey };
      })
      .filter((value): value is { columnId: string; accessorKey: string } => value != null);
  }, [columns]);

  const accessorKeyByColumnId = useMemo(() => {
    return new Map(filterableColumns.map((column) => [column.columnId, column.accessorKey] as const));
  }, [filterableColumns]);

  const getRowValue = (row: unknown, accessorKey: string) => {
    if (!row || typeof row !== "object") return undefined;
    if (!accessorKey.includes(".")) return (row as Record<string, unknown>)[accessorKey];
    return accessorKey.split(".").reduce<unknown>((acc, key) => {
      if (!acc || typeof acc !== "object") return undefined;
      return (acc as Record<string, unknown>)[key];
    }, row);
  };

  const filteredData = useMemo(() => {
    const query = search.trim().toLowerCase();
    const activeColumnFilters = Object.entries(columnFilters)
      .map(([columnId, value]) => ({ columnId, value: value.trim().toLowerCase() }))
      .filter((filter) => filter.value.length > 0);

    if (!query && activeColumnFilters.length === 0) return data;

    return data.filter((row) => {
      if (activeColumnFilters.length > 0) {
        for (const filter of activeColumnFilters) {
          const accessorKey = accessorKeyByColumnId.get(filter.columnId);
          if (!accessorKey) continue;
          const value = getRowValue(row, accessorKey);
          const asString =
            typeof value === "string"
              ? value
              : value == null
                ? ""
                : typeof value === "number" || typeof value === "boolean"
                  ? String(value)
                  : JSON.stringify(value);
          if (!asString.toLowerCase().includes(filter.value)) {
            return false;
          }
        }
      }

      if (!query) return true;
      try {
        const haystack = searchAccessor ? searchAccessor(row) : JSON.stringify(row);
        return haystack.toLowerCase().includes(query);
      } catch {
        return false;
      }
    });
  }, [accessorKeyByColumnId, columnFilters, data, search, searchAccessor]);

  const table = useReactTable({
    data: filteredData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    state: {
      sorting,
    },
  });

  const exportToCsv = () => {
    const exportCols = columns
      .map((col) => {
        const accessorKey = (col as unknown as { accessorKey?: unknown }).accessorKey;
        if (typeof accessorKey !== "string") return null;
        const header = (col as unknown as { header?: unknown }).header;
        return {
          accessorKey,
          header: typeof header === "string" ? header : accessorKey,
        };
      })
      .filter((column): column is { accessorKey: string; header: string } => column != null);

    const escape = (value: unknown) => {
      if (value == null) return "";
      const asString = typeof value === "string" ? value : JSON.stringify(value);
      if (/[",\n]/.test(asString)) {
        return `"${asString.replaceAll('"', '""')}"`;
      }
      return asString;
    };

    if (exportCols.length === 0) {
      const blob = new Blob([JSON.stringify(filteredData, null, 2)], {
        type: "application/json;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = exportFilename.replace(/\.csv$/i, ".json");
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      return;
    }

    const rows = filteredData as unknown as Array<Record<string, unknown>>;
    const headerLine = exportCols.map((column) => escape(column.header)).join(",");
    const dataLines = rows.map((row) =>
      exportCols.map((column) => escape(row[column.accessorKey])).join(",")
    );
    const csv = [headerLine, ...dataLines].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFilename || "export.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={cn("rounded-md border", className)}>
      {(enableSearch || enableExport || enableColumnFilters || toolbarLeadingContent || toolbarTrailingContent) && (
        <div className="bg-muted/30 flex flex-wrap items-center justify-between gap-2 border-b p-2">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {toolbarLeadingContent}
            {enableSearch ? (
              <div className="relative w-full sm:w-80">
                <Search className="text-muted-foreground absolute top-2.5 left-2 h-4 w-4" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={searchPlaceholder || "Search..."}
                  className="pl-8"
                />
                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="text-muted-foreground hover:text-foreground absolute top-2.5 right-2"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {toolbarTrailingContent}
            {enableColumnFilters && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowFilters((value) => !value)}
                className={cn(showFilters && "bg-muted")}
              >
                <Filter className="mr-2 h-4 w-4" />
                Filters
              </Button>
            )}
            {(enableSearch || enableColumnFilters) && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setColumnFilters({});
                }}
                disabled={!search && Object.keys(columnFilters).length === 0}
              >
                Clear
              </Button>
            )}
            {enableExport && (
              <Button
                variant="outline"
                size="sm"
                onClick={exportToCsv}
                disabled={filteredData.length === 0}
              >
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            )}
          </div>
        </div>
      )}

      <div ref={tableContainerRef} className={tableContainerClassName}>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={cn(
                      stickyHeader && "bg-background sticky top-0 z-10 shadow-[0_1px_0_hsl(var(--border))]"
                    )}
                  >
                    {header.isPlaceholder ? null : (
                      <button
                        type="button"
                        className={cn(
                          "flex w-full items-center gap-1 text-left",
                          header.column.getCanSort() && "cursor-pointer select-none"
                        )}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getCanSort() && (
                          <ArrowUpDown className="text-muted-foreground ml-auto h-3 w-3 shrink-0" />
                        )}
                      </button>
                    )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
            {enableColumnFilters && showFilters && (
              <TableRow>
                {(table.getHeaderGroups()[table.getHeaderGroups().length - 1]?.headers ?? []).map(
                  (header) => {
                    const accessorKey = (
                      header.column.columnDef as unknown as { accessorKey?: unknown }
                    ).accessorKey;
                    const canFilter = typeof accessorKey === "string";
                    return (
                      <TableHead key={`${header.id}-filter`} className="py-2">
                        {canFilter ? (
                          <Input
                            value={columnFilters[header.column.id] || ""}
                            onChange={(e) =>
                              setColumnFilters((prev) => ({
                                ...prev,
                                [header.column.id]: e.target.value,
                              }))
                            }
                            placeholder="Filter..."
                            className="h-7 text-xs"
                          />
                        ) : null}
                      </TableHead>
                    );
                  }
                )}
              </TableRow>
            )}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => {
                const expanded = isRowExpanded?.(row.original) ?? false;
                return (
                  <Fragment key={row.id}>
                    <TableRow
                      data-state={row.getIsSelected() && "selected"}
                      className={cn(onRowClick && "hover:bg-muted/50 cursor-pointer")}
                      onClick={() => onRowClick?.(row.original)}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </TableCell>
                      ))}
                    </TableRow>
                    {expanded && renderExpandedContent ? (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={columns.length} className="bg-muted/15 p-0">
                          {renderExpandedContent(row.original)}
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </Fragment>
                );
              })
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export function SortableHeader({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-1">{children}</div>;
}
