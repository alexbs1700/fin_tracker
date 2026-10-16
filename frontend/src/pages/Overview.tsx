// Resumen: total net worth, liquid vs invested over time, monthly cash flow, wallets

import { useState } from "react";

import { useMonthlyCashFlow, useNetWorth, useNetWorthHistory } from "../api/client";
import { MonthlyBarChart, StackedAreaChart, type SeriesSpec } from "../components/charts";
import MonthlyStatsCard from "../components/MonthlyStatsCard";
import { Card, Delta, ErrorState, KpiTile, Legend, LoadingState, RangeSelector } from "../components/ui";
import { formatEur, formatPercent } from "../lib/format";
import { labelWallet } from "../lib/labels";
import { computeChange, summarizeCashFlow } from "../lib/metrics";
import { type RangeKey, rangeFrequency, rangeStartDate } from "../lib/ranges";

const NET_WORTH_SERIES: SeriesSpec[] = [
  { key: "cash_eur", label: "Líquido", color: "var(--series-1)" },
  { key: "investments_eur", label: "Inversión", color: "var(--series-2)" },
];

// Income and expenses are different entities from cash / investments, so they
// take the next validated adjacent pair instead of reusing blue / orange
const CASH_FLOW_SERIES: SeriesSpec[] = [
  { key: "income_eur", label: "Ingresos", color: "var(--series-3)" },
  { key: "expenses_eur", label: "Gastos", color: "var(--series-4)" },
];

export default function Overview() {
  const [range, setRange] = useState<RangeKey>("1A");
  const dateFrom = rangeStartDate(range);

  const netWorth = useNetWorth();
  const history = useNetWorthHistory({ date_from: dateFrom, frequency: rangeFrequency(range) });
  const cashFlow = useMonthlyCashFlow({ date_from: dateFrom });

  if (netWorth.isLoading) return <LoadingState />;
  if (netWorth.error || !netWorth.data) return <ErrorState error={netWorth.error} />;

  const summary = netWorth.data;
  const totalChange = history.data ? computeChange(history.data, "total_eur") : null;
  const cashFlowTotals = cashFlow.data ? summarizeCashFlow(cashFlow.data) : null;
  const wallets = [...summary.cash_wallets].sort((a, b) => b.my_balance_eur - a.my_balance_eur);

  return (
    <>
      <p className="page-title">Patrimonio total</p>
      <div className="hero-row">
        <h1 className="hero-value">{formatEur(summary.total_eur)}</h1>
        {totalChange && <Delta value={totalChange.absolute} percent={totalChange.relative} />}
        {totalChange && <span className="muted">en el periodo</span>}
      </div>

      <div className="grid grid-kpis">
        <KpiTile
          label="Líquido"
          value={formatEur(summary.cash_eur)}
          hint={`${formatPercent(summary.cash_eur / summary.total_eur)} del total`}
        />
        <KpiTile
          label="Inversión"
          value={formatEur(summary.investments_eur)}
          hint={`${formatPercent(summary.investments_eur / summary.total_eur)} del total`}
        />
        <KpiTile
          label="Ahorro del periodo"
          value={formatEur(cashFlowTotals?.savingsEur)}
          hint={`Ingresos ${formatEur(cashFlowTotals?.incomeEur)} · Gastos ${formatEur(cashFlowTotals?.expensesEur)}`}
        />
        <KpiTile
          label="Tasa de ahorro"
          value={formatPercent(cashFlowTotals?.savingsRate)}
          hint={`Invertido en el periodo: ${formatEur(cashFlowTotals?.investedEur)}`}
        />
      </div>

      <div className="stack">
        <Card
          title="Evolución del patrimonio"
          subtitle="Líquido (cuentas) e inversión (Trade Republic) apilados"
          actions={<RangeSelector value={range} onChange={setRange} />}
        >
          <Legend items={NET_WORTH_SERIES} />
          {history.error ? (
            <ErrorState error={history.error} />
          ) : (
            <StackedAreaChart data={(history.data ?? []) as unknown as Record<string, unknown>[]} series={NET_WORTH_SERIES} />
          )}
        </Card>

        <MonthlyStatsCard />

        <div className="grid grid-2">
          <Card title="Flujo de caja mensual" subtitle="Sin traspasos internos ni compras de inversión">
            <Legend items={CASH_FLOW_SERIES} />
            <MonthlyBarChart
              data={(cashFlow.data ?? []) as unknown as Record<string, unknown>[]}
              series={CASH_FLOW_SERIES}
            />
          </Card>

          <Card title="Dónde está tu dinero" subtitle="Saldo actual por cuenta y cartera">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Cuenta</th>
                    <th className="num">Saldo</th>
                    <th className="num">En EUR</th>
                  </tr>
                </thead>
                <tbody>
                  {wallets.map((wallet) => {
                    const isExcluded = wallet.ownership_share === 0;
                    return (
                      <tr key={`${wallet.account}-${wallet.sub_account}`} className={isExcluded ? "muted" : ""}>
                        <td>
                          {labelWallet(wallet.account, wallet.sub_account)}
                          {isExcluded && <span className="badge" style={{ marginLeft: 8 }}>No cuenta</span>}
                        </td>
                        <td className="num secondary">
                          {wallet.balance.toLocaleString("es-ES", { maximumFractionDigits: 2 })} {wallet.currency}
                        </td>
                        <td className="num">{formatEur(wallet.my_balance_eur)}</td>
                      </tr>
                    );
                  })}
                  <tr>
                    <td className="secondary">Inversiones (valor de mercado)</td>
                    <td />
                    <td className="num">{formatEur(summary.investments_eur)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
