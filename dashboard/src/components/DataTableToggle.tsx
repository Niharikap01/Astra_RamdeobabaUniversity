/**
 * Shared DataTableToggle Component
 * Allows any chart to be toggled between graphic visualization and tabular data with CSV export.
 */

import React, { useState } from "react";
import { BarChart3, Download, Table as TableIcon } from "lucide-react";

export interface ColumnDef {
  key: string;
  label: string;
  format?: (val: any, row: any) => string;
}

interface DataTableToggleProps {
  rows: Record<string, any>[];
  cols: ColumnDef[];
  title?: string;
  filename?: string;
  children: React.ReactNode;
  className?: string;
}

export const DataTableToggle: React.FC<DataTableToggleProps> = ({
  rows,
  cols,
  title,
  filename = "nightwatch_telemetry.csv",
  children,
  className = "",
}) => {
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");

  const handleDownloadCsv = () => {
    if (!rows || rows.length === 0) return;

    const headers = cols.map((c) => `"${c.label.replace(/"/g, '""')}"`).join(",");
    const csvRows = rows.map((r) =>
      cols
        .map((c) => {
          const rawVal = r[c.key];
          const val = c.format ? c.format(rawVal, r) : rawVal != null ? String(rawVal) : "";
          return `"${val.replace(/"/g, '""')}"`;
        })
        .join(",")
    );

    const csvContent = [headers, ...csvRows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header Bar with View Toggle & CSV Download */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          {title && <h4 className="text-xs font-semibold text-slate-300 font-sans tracking-wide">{title}</h4>}
          <span className="text-[10px] text-slate-500 font-mono">
            {rows.length} {rows.length === 1 ? "record" : "records"}
          </span>
        </div>

        <div className="flex items-center gap-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800">
          <button
            onClick={() => setViewMode("chart")}
            className={`p-1 px-2 rounded text-xs flex items-center gap-1 transition-colors ${
              viewMode === "chart"
                ? "bg-slate-800 text-cyan-400 font-medium shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Chart View"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-[11px]">Chart</span>
          </button>

          <button
            onClick={() => setViewMode("table")}
            className={`p-1 px-2 rounded text-xs flex items-center gap-1 transition-colors ${
              viewMode === "table"
                ? "bg-slate-800 text-cyan-400 font-medium shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Table View"
          >
            <TableIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-[11px]">Table</span>
          </button>

          <button
            onClick={handleDownloadCsv}
            disabled={rows.length === 0}
            className="p-1 px-2 rounded text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800 flex items-center gap-1 transition-colors disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-[11px]">CSV</span>
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0">
        {viewMode === "chart" ? (
          children
        ) : (
          <div className="w-full h-full overflow-auto rounded-lg border border-slate-800 bg-slate-950/60 max-h-80">
            {rows.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">No data points available for table view.</div>
            ) : (
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-900/95 border-b border-slate-800 text-[11px] font-mono uppercase text-slate-400 z-10">
                  <tr>
                    {cols.map((c) => (
                      <th key={c.key} className="p-2.5 font-semibold tracking-wider">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {rows.map((r, rIdx) => (
                    <tr
                      key={rIdx}
                      className={rIdx % 2 === 0 ? "bg-transparent hover:bg-slate-800/30" : "bg-slate-900/30 hover:bg-slate-800/40"}
                    >
                      {cols.map((c) => {
                        const rawVal = r[c.key];
                        const displayVal = c.format ? c.format(rawVal, r) : rawVal != null ? String(rawVal) : "—";
                        return (
                          <td key={c.key} className="p-2.5 text-slate-300 whitespace-nowrap">
                            {displayVal}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
