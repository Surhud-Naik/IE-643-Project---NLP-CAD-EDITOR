import React from 'react';
import { Copy, Check, GitCommit } from 'lucide-react';

interface DiffViewerProps {
  patchText?: string;
  linesTouched?: number;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ patchText, linesTouched = 0 }) => {
  const [copied, setCopied] = React.useState(false);

  if (!patchText) {
    return (
      <div className="glass-card" style={{ padding: '1.25rem', textAlign: 'center', color: 'var(--text-faint)' }}>
        No code patch generated yet. Submit an edit instruction to inspect the predicted diff.
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(patchText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = patchText.split('\n');
  let currentSection: 'NONE' | 'SEARCH' | 'REPLACE' = 'NONE';

  return (
    <div className="glass-card" style={{ overflow: 'hidden' }}>
      {/* Diff Header */}
      <div style={{
        padding: '0.65rem 1rem',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(15, 23, 42, 0.5)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <GitCommit size={16} color="var(--accent-blue)" />
          <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Predicted Code Patch</span>
          {linesTouched > 0 && (
            <span className="badge badge-cyan" style={{ fontSize: '0.7rem' }}>
              {linesTouched} {linesTouched === 1 ? 'line' : 'lines'} modified
            </span>
          )}
        </div>

        <button
          onClick={handleCopy}
          className="btn-outline"
          style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
        >
          {copied ? <Check size={13} color="var(--accent-emerald)" /> : <Copy size={13} />}
          <span>{copied ? 'Copied' : 'Copy Patch'}</span>
        </button>
      </div>

      {/* Diff Body */}
      <div className="diff-container" style={{ padding: '0.75rem 0', maxHeight: '320px' }}>
        {lines.map((line, idx) => {
          const trimmed = line.trim();

          if (trimmed.startsWith('<<<<<<< SEARCH')) {
            currentSection = 'SEARCH';
            return (
              <div key={idx} className="diff-line diff-line-search-header">
                {line}
              </div>
            );
          } else if (trimmed.startsWith('=======')) {
            currentSection = 'REPLACE';
            return (
              <div key={idx} className="diff-line diff-line-separator">
                {line}
              </div>
            );
          } else if (trimmed.startsWith('>>>>>>> REPLACE')) {
            currentSection = 'NONE';
            return (
              <div key={idx} className="diff-line diff-line-replace-header">
                {line}
              </div>
            );
          }

          if (currentSection === 'SEARCH') {
            return (
              <div key={idx} className="diff-line diff-line-search">
                <span style={{ userSelect: 'none', marginRight: '0.5rem', opacity: 0.6 }}>-</span>
                {line}
              </div>
            );
          } else if (currentSection === 'REPLACE') {
            return (
              <div key={idx} className="diff-line diff-line-replace">
                <span style={{ userSelect: 'none', marginRight: '0.5rem', opacity: 0.6 }}>+</span>
                {line}
              </div>
            );
          } else {
            return (
              <div key={idx} className="diff-line diff-line-context">
                <span style={{ userSelect: 'none', marginRight: '0.5rem', opacity: 0.3 }}> </span>
                {line}
              </div>
            );
          }
        })}
      </div>
    </div>
  );
};
