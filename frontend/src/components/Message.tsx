import type { ChatMessage } from '../types';
import Citations from './Citations';
import ConfidenceBar from './ConfidenceBar';

interface Props {
  message: ChatMessage;
}

export default function Message({ message }: Props) {
  const isUser = message.role === 'user';
  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="avatar">{isUser ? '🧑' : '🤖'}</div>
      <div className="bubble">
        {message.content ? (
          <div className="content" style={{ whiteSpace: 'pre-wrap' }}>
            {message.content}
          </div>
        ) : (
          <div className="typing">Thinking…</div>
        )}

        {!isUser && message.evaluation && (
          <div className="evaluations">
            <ConfidenceBar value={message.evaluation.faithfulness} label="Faithfulness" />
            <ConfidenceBar value={message.evaluation.relevance} label="Relevance" />
            <ConfidenceBar value={message.evaluation.correctness} label="Correctness" />
          </div>
        )}

        {!isUser && message.routedModels && (
          <div className="routed">
            <div className="routed-title">Models used</div>
            {Object.entries(message.routedModels).map(([task, model]) => (
              <span className="routed-tag" key={task}>
                {task}: <b>{model}</b>
              </span>
            ))}
          </div>
        )}

        {!isUser && message.citations && <Citations citations={message.citations} />}
      </div>
    </div>
  );
}
