// Cartera: value vs invested over time, allocation, positions and realized gains

import { useState } from "react";

import { usePortfolio, usePortfolioHistory } from "../api/client";
import { TimeLineChart, type SeriesSpec } from "../components/charts";
import { Card, Delta, ErrorState, KpiTile, Legend, LoadingState, RangeSelector } from "../components/ui";
import { formatDate, formatEur, formatPercent, formatSignedEur } from "../lib/format";
import { ASSET_BUCKET_LABELS, labelAssetBucket } from "../lib/labels";
import { type RangeKey, rangeFrequency, rangeStartDate } from "../lib/ranges";

const VALUE_SERIES: SeriesSpec[] = [
  { key: "market_value_eur", label: "Valor de mercado", color: "var(--series-1)" },
  { key: "cost_basis_eur", label: "Invertido (coste FIFO)", color: "var(--text-secondary)", dashed: true },
];

// Buckets keep a fixed color whatever the current allocation looks like
const BUCKET_COLORS: Record<string, string> = Object.fromEntries(
  Object.keys(ASSET_BUCKET_LABELS).map((bucket, index) => [bucket, `var(--series-${index + 1})`]),
);

export default function Portfolio() {
  const [range, setRange] = useState<RangeKey>("TODO");
  const portfolio = usePortfolio();
  const history = usePortfolioHistory({
    date_from: rangeStartDate(range),
    frequency: rangeFrequency(range),
  });

  if (portfolio.isLoading) return <LoadingState />;
  if (portfolio.error || !portfolio.data) return <ErrorState error={portfolio.error} />;
  const summary = portfolio.data;

  return (
    <>
      <p className="page-title">Valor de la cartera</p>
      <div className="hero-row">
        <h1 className="hero-value">{formatEur(summary.market_value_eur)}</h1>
        <Delta value={summary.unrealized_gain_eur} percent={summary.unrealized_return} />
        <span className="muted">plusvalía latente</span>
      </div>

      <div className="grid grid-kpis">
        <KpiTile label="Invertido" value={formatEur(summary.cost_basis_eur)} hint="Coste FIFO con comisiones" />
        <KpiTile
          label="Plusvalía latente"
          value={formatSignedEur(summary.unrealized_gain_eur)}
          delta={<Delta percent={summary.unrealized_return} />}
        />
        <KpiTile
          label="Plusvalía realizada"
          value={formatSignedEur(summary.realized_gain_eur)}
          hint={`${summary.realized_gains.length} ventas`}
        />
        <KpiTile label="Posiciones abiertas" value={String(summary.positions.length)} />
      </div>

      <div className="stack">
        <Card
          title="Valor frente a lo invertido"
          subtitle="La distancia entre las dos líneas es tu plusvalía latente"
          actions={<RangeSelector value={range} onChange={setRange} />}
        >
          <Legend items={VALUE_SERIES} />
          {history.error ? (
            <ErrorState error={history.error} />
          ) : (
            <TimeLineChart data={(history.data ?? []) as unknown as Record<string, unknown>[]} series={VALUE_SERIES} />
          )}
        </Card>

        <div className="grid grid-2">
          <Card title="Distribución" subtitle="Por tipo de activo, a valor de mercado">
            <div className="bar-list">
              {Object.entries(summary.allocation)
                .sort(([, weightA], [, weightB]) => weightB - weightA)
                .map(([bucket, weight]) => (
                  <div key={bucket} className="bar-row">
                    <div className="bar-row-head">
                      <span>{labelAssetBucket(bucket)}</span>
                      <span>
                        {formatPercent(weight)}{" "}
                        <span className="muted">· {formatEur(weight * summary.market_value_eur)}</span>
                      </span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${weight * 100}%`, background: BUCKET_COLORS[bucket] ?? "var(--series-8)" }} />
                    </div>
                  </div>
                ))}
            </div>
          </Card>

          <Card title="Ventas" subtitle="Plusvalías realizadas con coste FIFO">
            {summary.realized_gains.length === 0 ? (
              <p className="muted">Sin ventas todavía.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Activo</th>
                      <th className="num">Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.realized_gains.map((sale) => (
                      <tr key={`${sale.asset_isin}-${sale.date}`}>
                        <td className="secondary">{formatDate(sale.date)}</td>
                        <td>{sale.asset_name}</td>
                        <td className="num"><Delta value={sale.realized_gain_eur} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <Card title="Posiciones">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Activo</th>
                  <th>Tipo</th>
                  <th className="num">Participaciones</th>
                  <th className="num">Precio</th>
                  <th className="num">Coste medio</th>
                  <th className="num">Valor</th>
                  <th className="num">Peso</th>
                  <th className="num">Plusvalía</th>
                </tr>
              </thead>
              <tbody>
                {summary.positions.map((position) => (
                  <tr key={position.asset_isin}>
                    <td>
                      {position.asset_name}
                      <div className="muted" style={{ fontSize: 11 }}>{position.ticker ?? position.asset_isin}</div>
                    </td>
                    <td><span className="badge">{labelAssetBucket(position.asset_bucket)}</span></td>
                    <td className="num secondary">{position.shares.toLocaleString("es-ES", { maximumFractionDigits: 4 })}</td>
                    <td className="num secondary">{formatEur(position.last_price_eur)}</td>
                    <td className="num secondary">{formatEur(position.average_cost_eur)}</td>
                    <td className="num">{formatEur(position.market_value_eur)}</td>
                    <td className="num secondary">{formatPercent(position.weight)}</td>
                    <td className="num"><Delta value={position.unrealized_gain_eur} percent={position.unrealized_return} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
