import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="page" style={{ display: "flex", justifyContent: "center", paddingTop: "80px" }}>
      <div style={{ textAlign: "center", marginBottom: "32px" }}>
        <SignIn
          appearance={{
            elements: {
              rootBox: { fontFamily: "var(--font-jakarta)" },
              card: {
                border: "1px solid var(--border)",
                boxShadow: "var(--shadow)",
                borderRadius: "var(--r-lg)",
              },
            },
          }}
        />
      </div>
    </main>
  );
}
