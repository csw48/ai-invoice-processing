"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthHeaders } from "../../lib/api-auth";

const ALL_FIELDS = [
  { key: "vendor_name", label: "Vendor name" },
  { key: "vendor_vat", label: "Vendor VAT number" },
  { key: "vendor_iban", label: "Vendor IBAN" },
  { key: "invoice_number", label: "Invoice number" },
  { key: "invoice_date", label: "Invoice date" },
  { key: "due_date", label: "Due date" },
  { key: "line_items", label: "Line items" },
  { key: "subtotal", label: "Subtotal" },
  { key: "vat_amount", label: "VAT amount" },
  { key: "total_amount", label: "Total amount" },
  { key: "currency", label: "Currency" },
  { key: "po_number", label: "PO number" },
  { key: "cost_center", label: "Cost center" },
];

const CONNECTORS = [
  { value: "json", label: "JSON", desc: "Raw JSON export" },
  { value: "csv", label: "CSV", desc: "Flat spreadsheet row" },
  { value: "pohoda", label: "Pohoda XML", desc: "RADVYD format for Pohoda" },
  { value: "webhook", label: "Webhook", desc: "POST to your endpoint" },
];

type Config = {
  client_id: string;
  name: string;
  country_code: string | null;
  fields_required: string[];
  fields_optional: string[];
  validation_rules: Record<string, string>;
  output_connector: string;
  connector_config: Record<string, string>;
  language: string;
  confidence_threshold: number;
};

const DEFAULT_CONFIG: Config = {
  client_id: "",
  name: "Demo Firma s.r.o.",
  country_code: null,
  fields_required: ["vendor_name", "invoice_number", "invoice_date", "total_amount"],
  fields_optional: ["po_number", "cost_center"],
  validation_rules: {},
  output_connector: "json",
  connector_config: {},
  language: "auto",
  confidence_threshold: 0.75,
};

export default function ConfigPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const authHeaders = useAuthHeaders();
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [webhookTest, setWebhookTest] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiUrl}/api/config`, { headers: await authHeaders() });
        setConfig(await res.json());
      } catch {
        // leave defaults
      } finally {
        setLoading(false);
      }
    })();
    // authHeaders is recreated each render; apiUrl is the real dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl]);

  function setField(key: string, required: boolean) {
    setConfig((prev) => {
      const isReq = prev.fields_required.includes(key);
      const isOpt = prev.fields_optional.includes(key);

      if (required) {
        return {
          ...prev,
          fields_required: isReq ? prev.fields_required : [...prev.fields_required, key],
          fields_optional: prev.fields_optional.filter((f) => f !== key),
        };
      } else {
        return {
          ...prev,
          fields_required: prev.fields_required.filter((f) => f !== key),
          fields_optional: isOpt ? prev.fields_optional : [...prev.fields_optional, key],
        };
      }
    });
  }

  function clearField(key: string) {
    setConfig((prev) => ({
      ...prev,
      fields_required: prev.fields_required.filter((f) => f !== key),
      fields_optional: prev.fields_optional.filter((f) => f !== key),
    }));
  }

  async function testWebhook() {
    if (!config.connector_config.webhook_url) return;
    setWebhookTest("testing");
    try {
      const res = await fetch(`${apiUrl}/api/webhooks/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(await authHeaders()) },
        body: JSON.stringify({ url: config.connector_config.webhook_url, secret: config.connector_config.webhook_secret ?? "" }),
      });
      setWebhookTest(res.ok ? "ok" : "fail");
    } catch {
      setWebhookTest("fail");
    }
    setTimeout(() => setWebhookTest("idle"), 4000);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...(await authHeaders()) },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error("Save failed");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("Could not save config. Is the API running?");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="page"><div className="empty-state">Loading config…</div></main>;

  return (
    <main className="page">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "32px" }}>
        <div>
          <Link href="/" className="page-back">← Dashboard</Link>
          <h1 className="page-title fade-up-1">Configuration</h1>
          <p className="page-sub fade-up-2">Control how invoices are extracted, validated, and exported.</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", paddingTop: "28px" }}>
          {saved && <span style={{ color: "var(--accent)", fontSize: "13px", fontWeight: 500 }}>Saved</span>}
          {error && <span style={{ color: "var(--error)", fontSize: "13px" }}>{error}</span>}
          <button className="btn btn-accent" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gap: "20px" }}>
        {/* Company */}
        <section className="card fade-up-1">
          <h2 className="card-title">Company</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px", marginTop: "20px" }}>
            <label className="field-label">
              Company name
              <input
                className="field-input"
                value={config.name}
                onChange={(e) => setConfig((p) => ({ ...p, name: e.target.value }))}
              />
            </label>
            <label className="field-label">
              Language
              <select
                className="field-input"
                value={config.language}
                onChange={(e) => setConfig((p) => ({ ...p, language: e.target.value }))}
              >
                <option value="auto">Auto-detect</option>
                <option value="sk">Slovak</option>
                <option value="en">English</option>
                <option value="de">German</option>
                <option value="cs">Czech</option>
              </select>
            </label>
            <label className="field-label">
              Country code
              <select
                className="field-input"
                value={config.country_code ?? ""}
                onChange={(e) => setConfig((p) => ({ ...p, country_code: e.target.value || null }))}
              >
                <option value="">Auto-detect</option>
                <option value="SK">Slovakia (SK)</option>
                <option value="CZ">Czech Republic (CZ)</option>
                <option value="DE">Germany (DE)</option>
                <option value="AT">Austria (AT)</option>
                <option value="HU">Hungary (HU)</option>
                <option value="PL">Poland (PL)</option>
              </select>
            </label>
          </div>
        </section>

        {/* Field mapping */}
        <section className="card fade-up-2">
          <h2 className="card-title">Field mapping</h2>
          <p style={{ fontSize: "13px", color: "var(--muted)", marginTop: "4px", marginBottom: "20px" }}>
            Required fields block approval if missing. Optional fields are extracted when present.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 80px 80px 80px", gap: "0", borderRadius: "var(--r-md)", overflow: "hidden", border: "1px solid var(--border)" }}>
            <div style={{ padding: "9px 16px", background: "var(--surface-raised)", fontSize: "11px", fontWeight: 600, letterSpacing: "0.05em", color: "var(--muted)", textTransform: "uppercase" }}>Field</div>
            <div style={{ padding: "9px 16px", background: "var(--surface-raised)", fontSize: "11px", fontWeight: 600, letterSpacing: "0.05em", color: "var(--muted)", textTransform: "uppercase", textAlign: "center" }}>Required</div>
            <div style={{ padding: "9px 16px", background: "var(--surface-raised)", fontSize: "11px", fontWeight: 600, letterSpacing: "0.05em", color: "var(--muted)", textTransform: "uppercase", textAlign: "center" }}>Optional</div>
            <div style={{ padding: "9px 16px", background: "var(--surface-raised)", fontSize: "11px", fontWeight: 600, letterSpacing: "0.05em", color: "var(--muted)", textTransform: "uppercase", textAlign: "center" }}>Off</div>
            {ALL_FIELDS.map(({ key, label }, i) => {
              const isReq = config.fields_required.includes(key);
              const isOpt = config.fields_optional.includes(key);
              const isOff = !isReq && !isOpt;
              const rowBg = i % 2 === 0 ? "var(--surface)" : "var(--surface-raised)";
              return [
                <div key={`${key}-label`} style={{ padding: "11px 16px", background: rowBg, borderTop: "1px solid var(--border-subtle)", fontSize: "13px", fontWeight: 500 }}>{label}</div>,
                <div key={`${key}-req`} style={{ padding: "11px 16px", background: rowBg, borderTop: "1px solid var(--border-subtle)", display: "flex", justifyContent: "center", alignItems: "center" }}>
                  <input type="radio" name={key} checked={isReq} onChange={() => setField(key, true)} style={{ accentColor: "var(--accent)" }} />
                </div>,
                <div key={`${key}-opt`} style={{ padding: "11px 16px", background: rowBg, borderTop: "1px solid var(--border-subtle)", display: "flex", justifyContent: "center", alignItems: "center" }}>
                  <input type="radio" name={key} checked={isOpt} onChange={() => setField(key, false)} style={{ accentColor: "var(--accent)" }} />
                </div>,
                <div key={`${key}-off`} style={{ padding: "11px 16px", background: rowBg, borderTop: "1px solid var(--border-subtle)", display: "flex", justifyContent: "center", alignItems: "center" }}>
                  <input type="radio" name={key} checked={isOff} onChange={() => clearField(key)} style={{ accentColor: "var(--muted)" }} />
                </div>,
              ];
            })}
          </div>
        </section>

        {/* Validation */}
        <section className="card fade-up-3">
          <h2 className="card-title">Validation</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "20px" }}>
            <label className="field-label">
              Confidence threshold
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "8px" }}>
                <input
                  type="range"
                  min={0.5}
                  max={1}
                  step={0.05}
                  value={config.confidence_threshold}
                  onChange={(e) => setConfig((p) => ({ ...p, confidence_threshold: parseFloat(e.target.value) }))}
                  style={{ flex: 1, accentColor: "var(--accent)" }}
                />
                <span style={{ fontFamily: "var(--font-jbm)", fontSize: "13px", fontWeight: 500, minWidth: "36px" }}>
                  {Math.round(config.confidence_threshold * 100)}%
                </span>
              </div>
              <p style={{ fontSize: "12px", color: "var(--muted)", marginTop: "6px" }}>
                Fields below this score are flagged for manual review.
              </p>
            </label>
            <label className="field-label">
              VAT format regex
              <input
                className="field-input"
                value={config.validation_rules.vat_format ?? ""}
                placeholder="e.g. SK[0-9]{10}"
                onChange={(e) => setConfig((p) => ({
                  ...p,
                  validation_rules: { ...p.validation_rules, vat_format: e.target.value },
                }))}
              />
            </label>
            <label className="field-label">
              Date format
              <input
                className="field-input"
                value={config.validation_rules.date_format ?? ""}
                placeholder="e.g. DD.MM.YYYY"
                onChange={(e) => setConfig((p) => ({
                  ...p,
                  validation_rules: { ...p.validation_rules, date_format: e.target.value },
                }))}
              />
            </label>
            <label className="field-label">
              Allowed currencies
              <input
                className="field-input"
                value={config.validation_rules.allowed_currencies ?? ""}
                placeholder="e.g. EUR,CZK"
                onChange={(e) => setConfig((p) => ({
                  ...p,
                  validation_rules: { ...p.validation_rules, allowed_currencies: e.target.value },
                }))}
              />
            </label>
          </div>
        </section>

        {/* Output connector */}
        <section className="card fade-up-4">
          <h2 className="card-title">Output connector</h2>
          <p style={{ fontSize: "13px", color: "var(--muted)", marginTop: "4px", marginBottom: "20px" }}>
            Where approved invoices are sent.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "12px" }}>
            {CONNECTORS.map(({ value, label, desc }) => (
              <button
                key={value}
                onClick={() => setConfig((p) => ({ ...p, output_connector: value }))}
                style={{
                  padding: "16px",
                  borderRadius: "var(--r-md)",
                  border: config.output_connector === value ? "2px solid var(--accent)" : "1px solid var(--border)",
                  background: config.output_connector === value ? "var(--accent-dim)" : "var(--surface)",
                  textAlign: "left",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ fontWeight: 600, fontSize: "13px", color: config.output_connector === value ? "var(--accent)" : "var(--text)" }}>{label}</div>
                <div style={{ fontSize: "12px", color: "var(--muted)", marginTop: "4px" }}>{desc}</div>
              </button>
            ))}
          </div>

          {config.output_connector === "pohoda" && (
            <div style={{ marginTop: "20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label className="field-label">
                Company ICO
                <input
                  className="field-input"
                  value={config.connector_config.ico ?? ""}
                  placeholder="12345678"
                  onChange={(e) => setConfig((p) => ({ ...p, connector_config: { ...p.connector_config, ico: e.target.value } }))}
                />
              </label>
              <label className="field-label">
                Export path
                <input
                  className="field-input"
                  value={config.connector_config.export_path ?? ""}
                  placeholder="/exports/pohoda/"
                  onChange={(e) => setConfig((p) => ({ ...p, connector_config: { ...p.connector_config, export_path: e.target.value } }))}
                />
              </label>
            </div>
          )}

          {config.output_connector === "webhook" && (
            <div style={{ marginTop: "20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label className="field-label">
                Webhook URL
                <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                  <input
                    className="field-input"
                    style={{ flex: 1, marginTop: 0 }}
                    value={config.connector_config.webhook_url ?? ""}
                    placeholder="https://your-system.com/invoices/inbound"
                    onChange={(e) => setConfig((p) => ({ ...p, connector_config: { ...p.connector_config, webhook_url: e.target.value } }))}
                  />
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={testWebhook}
                    disabled={!config.connector_config.webhook_url || webhookTest === "testing"}
                    style={{ whiteSpace: "nowrap", alignSelf: "center", color: webhookTest === "ok" ? "var(--success)" : webhookTest === "fail" ? "var(--error)" : undefined }}
                  >
                    {webhookTest === "testing" ? "Testing…" : webhookTest === "ok" ? "✓ OK" : webhookTest === "fail" ? "✗ Failed" : "Test"}
                  </button>
                </div>
                <p style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>Must be a public https endpoint.</p>
              </label>
              <label className="field-label">
                Signing secret (HMAC-SHA256)
                <input
                  className="field-input"
                  type="password"
                  value={config.connector_config.webhook_secret ?? ""}
                  placeholder="leave blank to skip signing"
                  onChange={(e) => setConfig((p) => ({ ...p, connector_config: { ...p.connector_config, webhook_secret: e.target.value } }))}
                />
                <p style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>Signature sent in X-Factura-Signature header.</p>
              </label>
            </div>
          )}

          {(config.output_connector === "csv" || config.output_connector === "pohoda" || config.output_connector === "json") && (
            <div style={{ marginTop: "20px", maxWidth: "320px" }}>
              <label className="field-label">
                Home currency
                <select
                  className="field-input"
                  value={config.connector_config.home_currency ?? "EUR"}
                  onChange={(e) => setConfig((p) => ({ ...p, connector_config: { ...p.connector_config, home_currency: e.target.value } }))}
                >
                  <option value="EUR">EUR — Euro</option>
                  <option value="CZK">CZK — Czech Koruna</option>
                  <option value="HUF">HUF — Hungarian Forint</option>
                  <option value="PLN">PLN — Polish Zloty</option>
                  <option value="USD">USD — US Dollar</option>
                  <option value="GBP">GBP — British Pound</option>
                </select>
                <p style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                  Invoices in a different currency are flagged as foreign-currency exports.
                </p>
              </label>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
