import React from 'react';
import { X, HelpCircle, CheckCircle, ShieldAlert } from 'lucide-react';

interface ConventionHelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ConventionHelpModal: React.FC<ConventionHelpModalProps> = ({
  isOpen,
  onClose
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
        maxWidth: '800px',
        width: '100%',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: 'var(--shadow-md)'
      }}>
        {/* Header */}
        <div style={{
          padding: '1rem 1.5rem',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <HelpCircle size={20} color="var(--accent-blue)" />
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>CadQuery Script Convention & Guidelines</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                How to structure parametric CAD code for natural language editing
              </p>
            </div>
          </div>
          <button onClick={onClose} className="btn-outline" style={{ padding: '0.4rem' }}>
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.25rem', fontSize: '0.875rem', lineHeight: '1.6' }}>
          <div>
            <h4 style={{ fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '0.35rem' }}>
              Why Edit Programs Instead of Raw STEP/STL Meshes?
            </h4>
            <p style={{ color: 'var(--text-muted)' }}>
              Raw CAD formats like STEP or STL represent evaluated boundary representations (B-Reps) or tessellated triangles without parametric relationships. They contain no variable definitions or construction history. By targeting <strong>CadQuery Python scripts</strong>, the AI model edits explicit numeric constants and features directly, preserving design intent and allowing deterministic mathematical verification.
            </p>
          </div>

          <div>
            <h4 style={{ fontWeight: 700, color: 'var(--accent-emerald)', marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <CheckCircle size={16} /> Program Structure Convention
            </h4>
            <p style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Every submitted script must satisfy two simple structural requirements:
            </p>
            <ol style={{ paddingLeft: '1.25rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <li><strong>Top-Level Parameters Block:</strong> Define numeric parameters as capitalized constants (e.g. <code>LENGTH = 40.0</code>, <code>HOLE_DIA = 6.0</code>) at the start of the script.</li>
              <li><strong>Final Solid in <code>result</code>:</strong> Build the 3D solid geometry into a top-level variable named <code>result</code>.</li>
            </ol>
          </div>

          <div style={{ background: 'rgba(0, 0, 0, 0.5)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-faint)' }}># Example Standard Convention Script</span><br />
            <span style={{ color: 'var(--accent-indigo)' }}>import</span> cadquery <span style={{ color: 'var(--accent-indigo)' }}>as</span> cq<br /><br />
            <span style={{ color: 'var(--text-faint)' }}># --- PARAMETERS ---</span><br />
            LENGTH = <span style={{ color: 'var(--accent-amber)' }}>50.0</span><br />
            WIDTH = <span style={{ color: 'var(--accent-amber)' }}>30.0</span><br />
            HOLE_DIA = <span style={{ color: 'var(--accent-amber)' }}>8.0</span><br /><br />
            <span style={{ color: 'var(--text-faint)' }}># --- GEOMETRY CONSTRUCTION ---</span><br />
            result = (<br />
            &nbsp;&nbsp;cq.Workplane(<span style={{ color: 'var(--accent-emerald)' }}>"XY"</span>)<br />
            &nbsp;&nbsp;.box(LENGTH, WIDTH, <span style={{ color: 'var(--accent-amber)' }}>10.0</span>)<br />
            &nbsp;&nbsp;.faces(<span style={{ color: 'var(--accent-emerald)' }}>"&gt;Z"</span>).workplane().hole(HOLE_DIA)<br />
            )
          </div>

          <div>
            <h4 style={{ fontWeight: 700, color: 'var(--accent-rose)', marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <ShieldAlert size={16} /> Sandboxed Security & Restrictions
            </h4>
            <p style={{ color: 'var(--text-muted)' }}>
              All code executes in an isolated sandbox. Only <code>cadquery</code>, <code>cq</code>, and <code>math</code> may be imported. System calls, file I/O (<code>open</code>), code evaluation (<code>eval</code>, <code>exec</code>), and networking are strictly intercepted and rejected.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
