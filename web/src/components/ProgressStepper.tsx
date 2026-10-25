import React, { useState } from 'react';
import { Check, Loader2, AlertCircle, ChevronDown, ChevronUp, XCircle } from 'lucide-react';

interface ProgressStepperProps {
  status: string;
  attempt: number;
  maxAttempts: number;
  message: string;
  error?: string;
  rawPatch?: string;
  onCancel?: () => void;
}

export const ProgressStepper: React.FC<ProgressStepperProps> = ({
  status,
  attempt,
  maxAttempts,
  message,
  error,
  rawPatch,
  onCancel
}) => {
  const [showRaw, setShowRaw] = useState(false);

  const steps = [
    { key: 'VALIDATING', label: 'Sandbox Pre-flight' },
    { key: 'GENERATING', label: `Patch Generation (${attempt}/${maxAttempts})` },
    { key: 'APPLYING', label: 'Patch Application' },
    { key: 'EXECUTING', label: 'CadQuery Evaluation' }
  ];

  const getStepIndex = (st: string) => {
    switch (st) {
      case 'QUEUED': return 0;
      case 'VALIDATING': return 0;
      case 'GENERATING': return 1;
      case 'APPLYING': return 2;
      case 'EXECUTING': return 3;
      case 'COMPLETED': return 4;
      default: return -1;
    }
  };

  const currentIndex = getStepIndex(status);
  const isFailed = status === 'FAILED';
  const isCompleted = status === 'COMPLETED';

  return (
    <div className="glass-card" style={{ padding: '1rem 1.25rem' }}>
      {/* Stepper Progress Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative', marginBottom: '0.85rem' }}>
        {steps.map((step, idx) => {
          let stepState: 'pending' | 'active' | 'done' | 'failed' = 'pending';
          if (isCompleted || currentIndex > idx) {
            stepState = 'done';
          } else if (currentIndex === idx) {
            stepState = isFailed ? 'failed' : 'active';
          }

          return (
            <div key={step.key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, position: 'relative', zIndex: 1 }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: stepState === 'done'
                  ? 'var(--accent-emerald)'
                  : stepState === 'active'
                  ? 'var(--accent-blue)'
                  : stepState === 'failed'
                  ? 'var(--accent-rose)'
                  : 'var(--bg-secondary)',
                border: `2px solid ${stepState === 'active' ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                color: '#ffffff',
                transition: 'all 0.25s ease'
              }}>
                {stepState === 'done' ? (
                  <Check size={16} strokeWidth={3} />
                ) : stepState === 'active' ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : stepState === 'failed' ? (
                  <XCircle size={16} />
                ) : (
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-faint)' }}>{idx + 1}</span>
                )}
              </div>
              <span style={{
                fontSize: '0.725rem',
                fontWeight: stepState === 'active' ? 700 : 500,
                color: stepState === 'active' ? 'var(--accent-cyan)' : stepState === 'done' ? 'var(--text-main)' : 'var(--text-faint)',
                marginTop: '0.35rem',
                textAlign: 'center'
              }}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Message and Cancel Action */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingTop: '0.5rem',
        borderTop: '1px solid var(--border-color)',
        fontSize: '0.85rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: isFailed ? 'var(--accent-rose)' : 'var(--text-muted)' }}>
          {status !== 'COMPLETED' && !isFailed && <Loader2 size={14} className="animate-spin" color="var(--accent-blue)" />}
          <span>{message || 'Processing CAD edit...'}</span>
        </div>

        {status !== 'COMPLETED' && !isFailed && onCancel && (
          <button
            onClick={onCancel}
            className="btn-outline"
            style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', color: 'var(--accent-rose)', borderColor: 'rgba(244, 63, 94, 0.4)' }}
          >
            Cancel
          </button>
        )}
      </div>

      {/* Error Details */}
      {isFailed && error && (
        <div style={{
          marginTop: '0.85rem',
          background: 'rgba(244, 63, 94, 0.1)',
          border: '1px solid rgba(244, 63, 94, 0.3)',
          borderRadius: '8px',
          padding: '0.75rem',
          fontSize: '0.85rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', color: 'var(--accent-rose)' }}>
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 600 }}>Editing Attempt Unsuccessful</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.2rem' }}>{error}</div>
            </div>
          </div>

          {rawPatch && (
            <div style={{ marginTop: '0.6rem' }}>
              <button
                onClick={() => setShowRaw(!showRaw)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--accent-blue)',
                  fontSize: '0.75rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  cursor: 'pointer'
                }}
              >
                <span>{showRaw ? 'Hide raw model output' : 'View raw model output'}</span>
                {showRaw ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showRaw && (
                <pre style={{
                  marginTop: '0.4rem',
                  padding: '0.5rem',
                  background: 'rgba(0, 0, 0, 0.4)',
                  borderRadius: '6px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  whiteSpace: 'pre-wrap',
                  maxHeight: '150px',
                  overflowY: 'auto'
                }}>
                  {rawPatch}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
