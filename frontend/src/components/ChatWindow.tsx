import { useState } from 'react';
import Message from './Message';
import { sendChat } from '../services/api';
import type { ChatMessage } from '../types';

interface Props {
  modelOverride: string;
}

export default function ChatWindow({ modelOverride }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sessionId] = useState(() =>
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : String(Date.now())
  );

  const submit = async () => {
    const text = input.trim();
    if (!text || busy) return;

    const userMsg: ChatMessage = { role: 'user', content: text };
    const aiMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      streaming: true,
    };
    setMessages((m) => [...m, userMsg, aiMsg]);
    setInput('');
    setBusy(true);

    const overrides: Record<string, string> = modelOverride
      ? { final_synth: modelOverride }
      : {};
    try {
      const reply = await sendChat({ message: text, session_id: sessionId, task_overrides: overrides });
      setMessages((m) =>
        m.map((msg) =>
          msg === aiMsg ? { ...reply, streaming: false } : msg
        )
      );
    } catch (e) {
      setMessages((m) =>
        m.map((msg) =>
          msg === aiMsg
            ? { ...msg, content: `Error: ${(e as Error).message}`, streaming: false }
            : msg
        )
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-history">
        {messages.length === 0 && (
          <div className="empty">
            <p>Ask anything — analytics, documents, or live web.</p>
            <p className="hint">
              Try: <i>“what are total sales by customer?”</i> or ingest a document
              in the sidebar.
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <Message message={msg} key={i} />
        ))}
        {busy && messages[messages.length - 1]?.content === '' && (
          <div className="message assistant">
            <div className="avatar">🤖</div>
            <div className="bubble typing">Running agents…</div>
          </div>
        )}
      </div>
      <div className="composer">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Type your question… (Enter to send)"
          rows={2}
        />
        <button onClick={submit} disabled={busy || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
