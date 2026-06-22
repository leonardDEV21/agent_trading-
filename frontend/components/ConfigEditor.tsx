"use client";

import { useState } from "react";

// JSON editor for a single named config. Lets a trader change risk/strategy/
// kronos thresholds WITHOUT editing source (validated server-side on save).
export function ConfigEditor({
  name,
  value,
  onSave,
  saving,
}: {
  name: string;
  value: unknown;
  onSave: (name: string, payload: any) => void;
  saving?: boolean;
}) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState<string | null>(null);

  const handleSave = () => {
    try {
      const parsed = JSON.parse(text);
      setError(null);
      onSave(name, parsed);
    } catch (e: any) {
      setError(`Invalid JSON: ${e.message}`);
    }
  };

  return (
    <div className="panel">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold capitalize">{name}</h3>
        <button className="btn" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
      {error && <p className="text-accent-down text-xs mb-2">{error}</p>}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        className="w-full h-72 bg-base-bg border border-base-border rounded-md p-3 text-xs font-mono"
      />
    </div>
  );
}
