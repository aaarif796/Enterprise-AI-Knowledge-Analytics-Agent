import type { Citation } from '../types';

export default function Citations({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) return null;
  return (
    <div className="citations">
      <div className="citations-title">Sources ({citations.length})</div>
      {citations.map((c, i) => (
        <div className="citation" key={i}>
          <span className="citation-type badge-{c.type}">{c.type}</span>
          <div className="citation-body">
            <div className="citation-title">
              {c.url ? (
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.title || `Source ${i + 1}`}
                </a>
              ) : (
                <span>{c.title || `Source ${i + 1}`}</span>
              )}
              {c.score != null && (
                <span className="citation-score">{(c.score * 100).toFixed(0)}%</span>
              )}
            </div>
            {c.snippet && <p className="citation-snippet">{c.snippet}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
