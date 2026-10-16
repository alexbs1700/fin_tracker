// Upload bank extracts: every file is validated first and replaces the
// current extract only when the user confirms a valid report.

import { useState } from "react";

import { useExtracts, useReplaceExtract, useValidateExtract } from "../api/client";
import type { ExtractReport, ExtractStatus } from "../api/types";
import { describeSummary, replaceButtonLabel, rowDifference } from "../lib/extracts";
import { formatDate } from "../lib/format";
import { LoadingState } from "./ui";

export default function ExtractsPanel({ onClose }: { onClose: () => void }) {
  const extracts = useExtracts();

  return (
    <div className="panel-backdrop" onClick={onClose}>
      <aside className="panel panel-wide" onClick={(event) => event.stopPropagation()} aria-label="Cargar extractos">
        <div className="card-header">
          <div>
            <h2 className="card-title">Extractos bancarios</h2>
            <p className="card-subtitle">
              Cada fichero se valida con las reglas del banco antes de sustituir el actual, que se guarda como copia
              de seguridad.
            </p>
          </div>
          <button className="button" onClick={onClose}>Cerrar</button>
        </div>
        {extracts.isLoading && <LoadingState />}
        {extracts.data?.map((status) => <BankExtract key={status.bank} status={status} />)}
      </aside>
    </div>
  );
}

function BankExtract({ status }: { status: ExtractStatus }) {
  const [file, setFile] = useState<File | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const validate = useValidateExtract();
  const replace = useReplaceExtract();
  const report: ExtractReport | undefined = replace.data?.report.is_valid === false
    ? replace.data.report
    : validate.data;

  const chooseFile = (chosenFile: File | null) => {
    setFile(chosenFile);
    setSuccessMessage(null);
    replace.reset();
    if (chosenFile) validate.mutate({ bank: status.bank, file: chosenFile });
    else validate.reset();
  };

  const confirmReplace = async () => {
    if (!file) return;
    const result = await replace.mutateAsync({ bank: status.bank, file });
    if (!result.report.is_valid) return;
    setSuccessMessage(
      result.backup_file
        ? `Extracto actualizado. Copia del anterior: backups/${result.backup_file}`
        : "Extracto cargado.",
    );
    setFile(null);
    validate.reset();
  };

  return (
    <div className="leg" style={{ marginBottom: 12 }}>
      <div className="card-header" style={{ marginBottom: 8 }}>
        <div>
          <p className="card-title">{status.label}</p>
          <p className="card-subtitle">
            {describeSummary(status.summary)}
            {status.modified_at && ` · subido el ${formatDate(status.modified_at.slice(0, 10))}`}
          </p>
        </div>
        <label className="button">
          Elegir {status.extension}
          <input
            type="file"
            accept={status.extension}
            className="sr-only"
            onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            // Same file twice in a row must trigger a new validation
            onClick={(event) => ((event.target as HTMLInputElement).value = "")}
          />
        </label>
      </div>

      {validate.isPending && <p className="secondary">Validando {file?.name}…</p>}
      {validate.error && <p className="status-text critical">✕ {validate.error.message}</p>}
      {successMessage && <p className="status-text good">✓ {successMessage}</p>}

      {report && file && (
        <div className="report">
          <p className="secondary" style={{ margin: "0 0 6px" }}>
            <strong>{file.name}</strong>
            {report.summary && ` · ${describeSummary(report.summary)}`}
            {rowDifference(report) !== null &&
              ` (${rowDifference(report)! >= 0 ? "+" : ""}${rowDifference(report)} frente al actual)`}
          </p>
          {report.errors.map((error) => (
            <p key={error} className="status-text critical">✕ Error: {error}</p>
          ))}
          {report.warnings.map((warning) => (
            <p key={warning} className="status-text warning">⚠ Aviso: {warning}</p>
          ))}
          {report.is_valid && report.warnings.length === 0 && (
            <p className="status-text good">✓ Compatible con las reglas de {status.label}.</p>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button
              className="button button-primary"
              disabled={!report.is_valid || replace.isPending}
              onClick={confirmReplace}
            >
              {replace.isPending ? "Sustituyendo…" : replaceButtonLabel(report)}
            </button>
            <button className="button" onClick={() => chooseFile(null)}>Cancelar</button>
          </div>
          {replace.error && <p className="status-text critical">✕ {replace.error.message}</p>}
        </div>
      )}
    </div>
  );
}
