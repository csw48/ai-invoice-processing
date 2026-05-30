import Link from "next/link";
import { VendorForm, type Vendor } from "../../components/vendor-form";

async function fetchVendors(apiUrl: string): Promise<Vendor[]> {
  try {
    const res = await fetch(`${apiUrl}/api/vendors/`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function VendorsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const vendors = await fetchVendors(apiUrl);

  return (
    <main className="page">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <Link href="/" className="page-back">← Dashboard</Link>
          <h1 className="page-title">Vendors</h1>
        </div>
        <span className="page-sub">
          {vendors.length} {vendors.length === 1 ? "vendor" : "vendors"}
        </span>
      </div>

      <div className="table-wrap fade-up" style={{ marginTop: "24px" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>VAT number</th>
              <th>IBAN</th>
              <th>Category</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {vendors.length === 0 && (
              <tr>
                <td colSpan={5}>
                  <div className="empty-state">
                    No vendors yet. Add one below to enable vendor matching.
                  </div>
                </td>
              </tr>
            )}
            <VendorForm vendors={vendors} apiUrl={apiUrl} />
          </tbody>
        </table>
      </div>
    </main>
  );
}
