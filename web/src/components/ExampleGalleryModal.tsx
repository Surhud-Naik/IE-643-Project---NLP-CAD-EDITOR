import React from 'react';
import type { ExampleItem } from '../types';
import { X, Sparkles, ArrowRight } from 'lucide-react';

interface ExampleGalleryModalProps {
  isOpen: boolean;
  onClose: () => void;
  examples: ExampleItem[];
  onSelect: (example: ExampleItem) => void;
}

export const ExampleGalleryModal: React.FC<ExampleGalleryModalProps> = ({
  isOpen,
  onClose,
  examples,
  onSelect
}) => {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '1.5rem'
    }}>
      <div className="glass-card" style={{
        maxWidth: '900px',
        width: '100%',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: 'var(--shadow-md)'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '1rem 1.5rem',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Sparkles size={20} color="var(--accent-cyan)" />
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Built-in CAD Examples Gallery</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Select a pre-configured parametric CadQuery model and paired instruction
              </p>
            </div>
          </div>
          <button onClick={onClose} className="btn-outline" style={{ padding: '0.4rem' }}>
            <X size={18} />
          </button>
        </div>

        {/* Examples Grid */}
        <div style={{
          padding: '1.25rem 1.5rem',
          overflowY: 'auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
          gap: '1rem'
        }}>
          {examples.map((ex) => (
            <div
              key={ex.id}
              style={{
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all 0.2s ease',
                cursor: 'pointer'
              }}
              onClick={() => {
                onSelect(ex);
                onClose();
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-blue)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-color)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>{ex.category}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                    {ex.id}
                  </span>
                </div>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                  {ex.title}
                </h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                  {ex.description}
                </p>
                <div style={{
                  background: 'rgba(0, 0, 0, 0.4)',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  fontSize: '0.775rem',
                  fontStyle: 'italic',
                  color: 'var(--accent-cyan)',
                  borderLeft: '3px solid var(--accent-blue)',
                  marginBottom: '0.75rem'
                }}>
                  "{ex.instruction}"
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.4rem', color: 'var(--accent-blue)', fontSize: '0.8rem', fontWeight: 600 }}>
                <span>Load Model</span>
                <ArrowRight size={14} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
