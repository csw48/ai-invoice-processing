import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <main className="page" style={{ display: "flex", justifyContent: "center", paddingTop: "80px" }}>
      <SignUp
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
    </main>
  );
}
