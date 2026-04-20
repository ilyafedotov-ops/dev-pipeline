"use client";

export default function StepDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div style={{ padding: "2rem" }}>
      <h2 style={{ color: "red" }}>Step Detail Error</h2>
      <pre style={{ background: "#1a1a1a", padding: "1rem", borderRadius: "8px", overflow: "auto", maxWidth: "100%", color: "#ff6b6b" }}>
        {error.message}
      </pre>
      {error.stack && (
        <pre style={{ background: "#1a1a1a", padding: "1rem", borderRadius: "8px", overflow: "auto", maxWidth: "100%", color: "#999", marginTop: "1rem", fontSize: "12px" }}>
          {error.stack}
        </pre>
      )}
      {error.digest && (
        <p style={{ color: "#666", marginTop: "1rem" }}>Digest: {error.digest}</p>
      )}
      <button
        onClick={reset}
        style={{
          marginTop: "1rem",
          padding: "0.5rem 1rem",
          background: "#3b82f6",
          color: "white",
          border: "none",
          borderRadius: "4px",
          cursor: "pointer",
        }}
      >
        Try again
      </button>
    </div>
  );
}
