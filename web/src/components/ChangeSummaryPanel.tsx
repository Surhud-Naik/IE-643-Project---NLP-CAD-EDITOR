import React from 'react';
import type { ChangeSummary, GeometryMetrics } from '../types';
import { Zap, Activity, CheckCircle, Sliders, Box } from 'lucide-react';

interface ChangeSummaryPanelProps {
  changeSummary?: ChangeSummary;
  metrics?: GeometryMetrics;
}

export const ChangeSummaryPanel: React.FC<ChangeSummaryPanelProps> = ({
  changeSummary,
  metrics
}) => {
  if (!changeSummary && !metrics) return null;

  return (
    <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Parametric & Geometric Changes</h3>
        </div>

        {metrics?.validity && (
          <span className="badge badge-green">
            <CheckCircle size={12} /> Valid B-Rep Solid
          </span>
        )}
      </div>

      {/* Grid of Key Impact Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
        {/* Token Efficiency Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          borderRadius: '10px',
          padding: '0.85rem',
          border: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            <Zap size={14} color="var(--accent-amber)" />
            <span>Patch vs Regeneration</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
            {changeSummary ? `-${changeSummary.token_savings_pct}%` : 'N/A'}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
            {changeSummary ? `${changeSummary.output_tokens} patch tokens vs ${changeSummary.full_program_tokens} full tokens` : 'Compact localized diff'}
          </span>
        </div>

        {/* Volume Delta Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          borderRadius: '10px',
          padding: '0.85rem',
          border: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            <Box size={14} color="var(--accent-blue)" />
            <span>Volume Change</span>
          </div>
          <div style={{
            fontSize: '1.25rem',
            fontWeight: 800,
            color: (metrics?.volume_change_pct || 0) >= 0 ? 'var(--accent-cyan)' : 'var(--accent-amber)'
          }}>
            {metrics ? `${metrics.volume_change_pct >= 0 ? '+' : ''}${metrics.volume_change_pct}%` : '0%'}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
            {metrics ? `${metrics.original_volume} -> ${metrics.edited_volume} mm³` : 'Geometry volume'}
          </span>
        </div>

        {/* Change Magnitude (Chamfer Distance) Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          borderRadius: '10px',
          padding: '0.85rem',
          border: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            <Sliders size={14} color="var(--accent-indigo)" />
            <span>Change Magnitude</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)' }}>
            {metrics ? `${metrics.chamfer_distance_relative}` : '0.000'}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
            Norm. Chamfer Distance (Original vs Edited)
          </span>
        </div>

        {/* Volumetric IoU Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          borderRadius: '10px',
          padding: '0.85rem',
          border: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            <Box size={14} color="var(--accent-emerald)" />
            <span>Volumetric Overlap (IoU)</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
            {metrics ? `${(metrics.volumetric_iou * 100).toFixed(1)}%` : '100%'}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
            Intersection over Union
          </span>
        </div>
      </div>

      {/* Parameter Modifications List */}
      {changeSummary && changeSummary.parameters_changed.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.85rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Modified Parametric Constants:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {changeSummary.parameters_changed.map((p, idx) => (
              <div
                key={idx}
                style={{
                  background: 'rgba(6, 182, 212, 0.1)',
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                  borderRadius: '8px',
                  padding: '0.35rem 0.7rem',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem'
                }}
              >
                <span style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{p.name}:</span>
                <span style={{ textDecoration: 'line-through', color: 'var(--accent-rose)', opacity: 0.8 }}>
                  {p.old_value !== null ? p.old_value : 'unset'}
                </span>
                <span style={{ color: 'var(--text-faint)' }}>&rarr;</span>
                <span style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                  {p.new_value}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
