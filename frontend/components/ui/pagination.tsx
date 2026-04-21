"use client";

import { useState } from "react";

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
}

interface PaginationProps {
  /** Current page (1-indexed) */
  page: number;
  /** Items per page */
  pageSize: number;
  /** Total number of items */
  total: number;
  /** Page change handler */
  onPageChange: (page: number) => void;
  /** Page size change handler */
  onPageSizeChange?: (pageSize: number) => void;
  /** Available page size options */
  pageSizeOptions?: number[];
  /** Show page size selector */
  showPageSize?: boolean;
  /** Show total count */
  showTotal?: boolean;
  /** Compact mode (fewer buttons) */
  compact?: boolean;
  /** Container className */
  className?: string;
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  showPageSize = true,
  showTotal = true,
  compact = false,
  className,
}: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  const canGoPrev = page > 1;
  const canGoNext = page < totalPages;

  // Generate page numbers to show
  const getPageNumbers = () => {
    const pages: (number | "ellipsis")[] = [];
    
    if (compact || totalPages <= 7) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (page <= 3) {
        // Near start: 1 2 3 4 5 ... N
        for (let i = 2; i <= Math.min(5, totalPages - 1); i++) {
          pages.push(i);
        }
        if (totalPages > 5) pages.push("ellipsis");
      } else if (page >= totalPages - 2) {
        // Near end: 1 ... N-4 N-3 N-2 N-1 N
        pages.push("ellipsis");
        for (let i = Math.max(2, totalPages - 4); i <= totalPages - 1; i++) {
          pages.push(i);
        }
      } else {
        // Middle: 1 ... P-1 P P+1 ... N
        pages.push("ellipsis");
        pages.push(page - 1);
        pages.push(page);
        pages.push(page + 1);
        pages.push("ellipsis");
      }

      // Always show last page
      if (totalPages > 1) {
        pages.push(totalPages);
      }
    }

    return pages;
  };

  if (totalPages <= 1 && !showPageSize && !showTotal) {
    return null;
  }

  return (
    <div className={cn("flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between", className)}>
      {/* Item count */}
      {showTotal && (
        <div className="text-muted-foreground text-sm">
          {total > 0 ? (
            <>
              Showing <span className="font-medium">{startItem}</span> to{" "}
              <span className="font-medium">{endItem}</span> of{" "}
              <span className="font-medium">{total}</span> results
            </>
          ) : (
            "No results"
          )}
        </div>
      )}

      <div className="flex items-center gap-4">
        {/* Page size selector */}
        {showPageSize && onPageSizeChange && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-sm">Show</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => onPageSizeChange(Number(value))}
            >
              <SelectTrigger className="h-8 w-[70px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pageSizeOptions.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Page navigation */}
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => onPageChange(1)}
              disabled={!canGoPrev}
              title="First page"
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => onPageChange(page - 1)}
              disabled={!canGoPrev}
              title="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            {/* Page numbers */}
            <div className="hidden items-center gap-1 sm:flex">
              {getPageNumbers().map((p, i) =>
                p === "ellipsis" ? (
                  <span key={`ellipsis-${i}`} className="px-2 text-muted-foreground">
                    ...
                  </span>
                ) : (
                  <Button
                    key={p}
                    variant={p === page ? "default" : "outline"}
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onPageChange(p)}
                  >
                    {p}
                  </Button>
                )
              )}
            </div>

            {/* Mobile page indicator */}
            <span className="px-2 text-sm sm:hidden">
              {page} / {totalPages}
            </span>

            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => onPageChange(page + 1)}
              disabled={!canGoNext}
              title="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => onPageChange(totalPages)}
              disabled={!canGoNext}
              title="Last page"
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Hook for managing pagination state.
 */
export function usePagination(initialPageSize = 20) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(1); // Reset to first page when page size changes
  };

  const reset = () => {
    setPage(1);
  };

  return {
    page,
    pageSize,
    setPage: handlePageChange,
    setPageSize: handlePageSizeChange,
    reset,
    // Calculated values for API calls
    offset: (page - 1) * pageSize,
    limit: pageSize,
  };
}
