"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export type Vendor = {
  id: string;
  name: string;
  client_id: string;
  vat_number: string | null;
  iban: string | null;
  category: string | null;
  metadata: Record<string, unknown> | null;
};

type Props = {
  vendors: Vendor[];
  apiUrl: string;
};

export function VendorForm({ vendors, apiUrl }: Props) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [iban, setIban] = useState("");
  const [category, setCategory] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const body: Record<string, string> = { name };
      if (vatNumber.trim()) body.vat_number = vatNumber.trim();
      if (iban.trim()) body.iban = iban.trim();
      if (category.trim()) body.category = category.trim();

      const res = await fetch(`${apiUrl}/api/vendors/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        setError(`Failed to add vendor (${res.status}): ${text}`);
        return;
      }

      setName("");
      setVatNumber("");
      setIban("");
      setCategory("");
      router.refresh();
    } catch (err) {
      setError(`Error: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      const res = await fetch(`${apiUrl}/api/vendors/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        console.error(`Delete failed: ${res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      console.error("Delete error:", err);
    }
  }

  return (
    <>
      {vendors.map((vendor) => (
        <tr key={vendor.id}>
          <td className="td-primary">{vendor.name}</td>
          <td className="td-mono">{vendor.vat_number ?? "—"}</td>
          <td className="td-mono">{vendor.iban ?? "—"}</td>
          <td>{vendor.category ?? "—"}</td>
          <td className="td-action">
            <button
              onClick={() => handleDelete(vendor.id)}
              className="btn btn-danger btn-sm"
            >
              Delete
            </button>
          </td>
        </tr>
      ))}

      <tr>
        <td colSpan={5}>
          <div className="card">
            <form
              onSubmit={handleAdd}
              style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "16px" }}
            >
              <div>
                <label className="input-label">Name *</label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Vendor name"
                  className="input"
                />
              </div>
              <div>
                <label className="input-label">VAT number</label>
                <input
                  value={vatNumber}
                  onChange={(e) => setVatNumber(e.target.value)}
                  placeholder="SK1234567890"
                  className="input"
                />
              </div>
              <div>
                <label className="input-label">IBAN</label>
                <input
                  value={iban}
                  onChange={(e) => setIban(e.target.value)}
                  placeholder="SK00 0000 0000 0000 0000 0000"
                  className="input"
                />
              </div>
              <div>
                <label className="input-label">Category</label>
                <input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="e.g. utilities"
                  className="input"
                />
              </div>
              <button type="submit" disabled={submitting} className="btn btn-accent">
                {submitting ? "Adding..." : "Add vendor"}
              </button>
            </form>
            {error && (
              <p style={{ marginTop: "8px", color: "var(--error)", fontSize: "13px" }}>{error}</p>
            )}
          </div>
        </td>
      </tr>
    </>
  );
}
