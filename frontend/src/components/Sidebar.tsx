import { useState } from 'react';

interface Props {
  onIngest: (text: string, name: string) => Promise<number>;
}

export default function Sidebar({ onIngest }: Props) {
  const [name, setName] = useState('knowledge-base');
  const [text, setText] = useState('');
  const [status, setStatus] = useState<string | null>(null);

  const submit = async () => {
    if (!text.trim()) return;
    setStatus('Ingesting…');
    try {
      const count = await onIngest(text, name);
      setStatus(`✅ Ingested ${count} chunk(s)`);
      setText('');
    } catch (e) {
      setStatus(`❌ ${(e as Error).message}`);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">🧠 Enterprise AI Agent</div>
      <div className="sidebar-section">
        <h3>Ingest knowledge</h3>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Source name"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste a document to add to the RAG knowledge base…"
          rows={8}
        />
        <button onClick={submit} disabled={!text.trim()}>
          Ingest to Vector DB
        </button>
        {status && <div className="ingest-status">{status}</div>}
      </div>
      <div className="sidebar-section">
        <h3>Architecture</h3>
        <p className="arch">
          Agent Router → RAG / SQL / Web → MCP Tool Layer → Response Agent →
          Evaluator → Final Response + Confidence + Citations
        </p>
      </div>
    </aside>
  );
}
