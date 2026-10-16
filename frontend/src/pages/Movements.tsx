// Movimientos: filter by period, account, flow types, category and text; the
// headline, breakdown and chart summarize exactly the filtered movements.
// Transactions table with editable categories and internal transfer tracing.

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";

import {
  useCategories,
  useTransactionLegs,
  useTransactions,
  useTransactionsSummary,
  useUpdateCategory,
} from "../api/client";
import type { FlowType, Transaction } from "../api/types";
import { MonthlyBarChart, type SeriesSpec } from "../components/charts";
import { Card, ErrorState, Legend, LoadingState, RangeSelector } from "../components/ui";
import { formatDate, formatEur, formatSignedEur } from "../lib/format";
import { ACCOUNT_LABELS, FLOW_TYPE_LABELS, labelWallet } from "../lib/labels";
import {
  activeFlowSeries,
  describeTotal,
  shareOfAbsoluteTotal,
  toggleFlowType,
} from "../lib/movements";
import { matchingRange, type RangeKey, rangeStartDate } from "../lib/ranges";

const PAGE_SIZE = 50;

// Same entities and colors as the cash flow chart of the Resumen page
const FLOW_SERIES: Record<"inflow_eur" | "outflow_eur", SeriesSpec> = {
  inflow_eur: { key: "inflow_eur", label: "Entradas", color: "var(--series-3)" },
  outflow_eur: { key: "outflow_eur", label: "Salidas", color: "var(--series-4)" },
};

export default function Movements() {
  // The period is two dates; presets only fill them in
  const [dateFrom, setDateFrom] = useState(rangeStartDate("6M") ?? "");
  const [dateTo, setDateTo] = useState("");
  const [account, setAccount] = useState("");
  const [flowTypes, setFlowTypes] = useState<FlowType[]>(["expense"]);
  const [category, setCategory] = useState("");
  const [searchText, setSearchText] = useState("");
  const [page, setPage] = useState(0);
  const [tracedKey, setTracedKey] = useState<string | null>(null);

  // One set of filters drives the table and every summary on the page
  const filters = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    account: account || undefined,
    flow_type: flowTypes,
    category: category || undefined,
    q: searchText || undefined,
  };
  const total = useTransactionsSummary({ ...filters, group_by: "total" });
  const byCategory = useTransactionsSummary({ ...filters, group_by: "category" });
  const byMonth = useTransactionsSummary({ ...filters, group_by: "month" });
  const categories = useCategories();
  const transactions = useTransactions({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE });

  // Any filter change goes back to the first page
  const withPageReset =
    <T,>(setter: (value: T) => void) =>
    (value: T) => {
      setter(value);
      setPage(0);
    };

  const selectPreset = (range: RangeKey) => {
    setDateFrom(rangeStartDate(range) ?? "");
    setDateTo("");
    setPage(0);
  };

  const totalRow = total.data?.[0];
  const headline = describeTotal(flowTypes, totalRow);
  const monthlySeries = activeFlowSeries(totalRow).map((key) => FLOW_SERIES[key]);
  const categoryRows = byCategory.data ?? [];
  const maxCategoryNet = Math.max(...categoryRows.map((row) => Math.abs(row.net_eur)), 1);

  return (
    <>
      <p className="page-title">{headline.label}</p>
      <div className="hero-row">
        <h1 className="hero-value">
          {headline.isSigned ? formatSignedEur(headline.value) : formatEur(headline.value)}
        </h1>
        {totalRow && (
          <span className="muted">
            Entradas {formatEur(totalRow.inflow_eur)} · Salidas {formatEur(totalRow.outflow_eur)} ·{" "}
            {totalRow.transactions} movimientos
          </span>
        )}
      </div>

      <div className="filters">
        <RangeSelector value={matchingRange(dateFrom, dateTo)} onChange={selectPreset} />
        <label className="date-field">
          Desde
          <input
            type="date"
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(event) => withPageReset(setDateFrom)(event.target.value)}
          />
        </label>
        <label className="date-field">
          Hasta
          <input
            type="date"
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(event) => withPageReset(setDateTo)(event.target.value)}
          />
        </label>
        <select aria-label="Cuenta" value={account} onChange={(event) => withPageReset(setAccount)(event.target.value)}>
          <option value="">Todas las cuentas</option>
          {Object.entries(ACCOUNT_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <select aria-label="Categoría" value={category} onChange={(event) => withPageReset(setCategory)(event.target.value)}>
          <option value="">Todas las categorías</option>
          {categories.data?.categories.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Buscar comercio o concepto…"
          value={searchText}
          onChange={(event) => withPageReset(setSearchText)(event.target.value)}
        />
      </div>

      <div className="filters" role="group" aria-label="Tipos de movimiento">
        <button
          type="button"
          className={`chip${flowTypes.length === 0 ? " active" : ""}`}
          aria-pressed={flowTypes.length === 0}
          onClick={() => withPageReset(setFlowTypes)([])}
        >
          Todos
        </button>
        {(Object.entries(FLOW_TYPE_LABELS) as [FlowType, string][]).map(([flowType, label]) => (
          <button
            key={flowType}
            type="button"
            className={`chip${flowTypes.includes(flowType) ? " active" : ""}`}
            aria-pressed={flowTypes.includes(flowType)}
            onClick={() => withPageReset(setFlowTypes)(toggleFlowType(flowTypes, flowType))}
          >
            {flowTypes.includes(flowType) ? "✓ " : ""}
            {label}
          </button>
        ))}
      </div>

      <div className="stack">
        <div className="grid grid-2">
          <Card title="Por categoría" subtitle="Neto de cada categoría · pulsa una para filtrar">
            {byCategory.isLoading ? (
              <LoadingState />
            ) : categoryRows.length === 0 ? (
              <p className="muted">Sin movimientos con estos filtros.</p>
            ) : (
              <div className="bar-list">
                {categoryRows.map((row) => (
                  <div
                    key={row.category}
                    className="bar-row clickable"
                    role="button"
                    tabIndex={0}
                    onClick={() => withPageReset(setCategory)(row.category ?? "")}
                    onKeyDown={(event) => event.key === "Enter" && withPageReset(setCategory)(row.category ?? "")}
                    title={`${row.transactions} movimientos · entradas ${formatEur(row.inflow_eur)} · salidas ${formatEur(row.outflow_eur)}`}
                  >
                    <div className="bar-row-head">
                      <span>{row.category}</span>
                      <span>
                        {formatSignedEur(row.net_eur)}{" "}
                        <span className="muted">· {Math.round(shareOfAbsoluteTotal(row, categoryRows) * 100)} %</span>
                      </span>
                    </div>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{
                          width: `${(Math.abs(row.net_eur) / maxCategoryNet) * 100}%`,
                          background: row.net_eur >= 0 ? FLOW_SERIES.inflow_eur.color : FLOW_SERIES.outflow_eur.color,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Por mes" subtitle="Entradas y salidas de los movimientos filtrados">
            {monthlySeries.length > 1 && <Legend items={monthlySeries} />}
            <MonthlyBarChart
              data={(byMonth.data ?? []) as unknown as Record<string, unknown>[]}
              series={monthlySeries}
            />
          </Card>
        </div>

        <Card
          title="Movimientos"
          subtitle="Cambia la categoría directamente; ⇄ muestra la otra parte de un traspaso"
        >
          {transactions.error ? (
            <ErrorState error={transactions.error} />
          ) : (
            <TransactionsTable
              rows={transactions.data?.items ?? []}
              categories={categories.data?.categories ?? []}
              onTrace={setTracedKey}
            />
          )}
          <div className="pagination">
            <span>
              {transactions.data?.total ?? 0} movimientos · página {page + 1} de{" "}
              {Math.max(1, Math.ceil((transactions.data?.total ?? 0) / PAGE_SIZE))}
            </span>
            <button className="button" disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button>
            <button
              className="button"
              disabled={(page + 1) * PAGE_SIZE >= (transactions.data?.total ?? 0)}
              onClick={() => setPage(page + 1)}
            >
              Siguiente
            </button>
          </div>
        </Card>
      </div>

      {tracedKey && <TransferPanel transactionKey={tracedKey} onClose={() => setTracedKey(null)} />}
    </>
  );
}

function TransactionsTable({
  rows,
  categories,
  onTrace,
}: {
  rows: Transaction[];
  categories: string[];
  onTrace: (transactionKey: string) => void;
}) {
  const updateCategory = useUpdateCategory();

  const columns = useMemo<ColumnDef<Transaction>[]>(
    () => [
      { header: "Fecha", accessorKey: "date", cell: ({ getValue }) => <span className="secondary">{formatDate(getValue<string>())}</span> },
      {
        header: "Cuenta",
        id: "wallet",
        cell: ({ row }) => <span className="secondary">{labelWallet(row.original.account, row.original.sub_account)}</span>,
      },
      {
        header: "Concepto",
        accessorKey: "description",
        cell: ({ row }) => (
          <div className="truncate" title={row.original.details ?? undefined}>
            {row.original.description}
          </div>
        ),
      },
      {
        header: "Categoría",
        accessorKey: "category",
        cell: ({ row }) => (
          <select
            aria-label="Categoría del movimiento"
            value={row.original.category}
            onChange={(event) =>
              updateCategory.mutate({ transactionKey: row.original.transaction_key, category: event.target.value })
            }
          >
            {[...new Set([...categories, row.original.category])].map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        ),
      },
      {
        header: "Tipo",
        accessorKey: "flow_type",
        cell: ({ row }) => <span className="badge">{FLOW_TYPE_LABELS[row.original.flow_type]}</span>,
      },
      {
        header: "",
        id: "transfer",
        cell: ({ row }) =>
          row.original.transfer_id ? (
            <button className="transfer-link" title="Ver la otra parte del traspaso" onClick={() => onTrace(row.original.transaction_key)}>
              ⇄
            </button>
          ) : null,
      },
      {
        header: () => <span style={{ display: "block", textAlign: "right" }}>Importe</span>,
        accessorKey: "amount_eur",
        cell: ({ row }) => (
          <div className="num">
            {formatSignedEur(row.original.amount_eur)}
            {row.original.currency !== "EUR" && (
              <div className="muted" style={{ fontSize: 11 }}>
                {row.original.amount.toLocaleString("es-ES")} {row.original.currency}
              </div>
            )}
          </div>
        ),
      },
    ],
    [categories, onTrace, updateCategory],
  );

  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="table-wrap">
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.original.transaction_key}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TransferPanel({ transactionKey, onClose }: { transactionKey: string; onClose: () => void }) {
  const legs = useTransactionLegs(transactionKey);
  // Show the money leaving first, then where it arrived
  const sortedLegs = [...(legs.data ?? [])].sort((a, b) => a.amount - b.amount);

  return (
    <div className="panel-backdrop" onClick={onClose}>
      <aside className="panel" onClick={(event) => event.stopPropagation()} aria-label="Traspaso interno">
        <div className="card-header">
          <h2 className="card-title">Traspaso {sortedLegs[0]?.transfer_id}</h2>
          <button className="button" onClick={onClose}>Cerrar</button>
        </div>
        {legs.isLoading && <LoadingState />}
        {sortedLegs.map((leg, index) => (
          <div key={leg.transaction_key}>
            {index > 0 && <div className="leg-arrow">↓</div>}
            <div className="leg">
              <p className="kpi-label">{index === 0 ? "Sale de" : "Llega a"}</p>
              <p className="card-title">{labelWallet(leg.account, leg.sub_account)}</p>
              <p className="secondary" style={{ margin: "4px 0" }}>{leg.description}</p>
              <p style={{ margin: 0 }}>
                <strong>{formatSignedEur(leg.amount_eur)}</strong>{" "}
                <span className="muted">· {formatDate(leg.date)}</span>
              </p>
            </div>
          </div>
        ))}
        {sortedLegs.length === 1 && (
          <p className="muted">No se encontró la otra parte: puede ser anterior a los extractos o de una cuenta que no se sigue.</p>
        )}
      </aside>
    </div>
  );
}
