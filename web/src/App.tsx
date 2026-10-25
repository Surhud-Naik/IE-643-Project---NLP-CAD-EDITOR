import React, { useState, useEffect, useRef } from 'react';
import {
  Code,
  Sparkles,
  Play,
  RotateCcw,
  Download,
  Upload,
  CheckCircle,
  AlertCircle,
  HelpCircle,
  Sun,
  Moon,
  Layers,
  Link,
  Unlink,
  History,
  ArrowRight
} from 'lucide-react';
import * as THREE from 'three';

import type { ExampleItem, JobResult, JobEvent, HistoryItem } from './types';
import { ThreeViewer } from './components/ThreeViewer';
import { DiffViewer } from './components/DiffViewer';
import { ChangeSummaryPanel } from './components/ChangeSummaryPanel';
import { ProgressStepper } from './components/ProgressStepper';
import { ExampleGalleryModal } from './components/ExampleGalleryModal';
import { ConventionHelpModal } from './components/ConventionHelpModal';

const DEFAULT_SCRIPT = `import cadquery as cq

LENGTH = 60.0
WIDTH = 40.0
HEIGHT = 12.0
HOLE_DIA = 8.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
`;

export function App() {
  // Theme state
  const [isDark, setIsDark] = useState(true);

  // Modals state
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  // App data & config
  const [examples, setExamples] = useState<ExampleItem[]>([]);
  const [backendMode, setBackendMode] = useState<string>('mock');
  const [availableModes, setAvailableModes] = useState<string[]>(['patch']);

  // Editor and Instruction state
  const [script, setScript] = useState<string>(DEFAULT_SCRIPT);
  const [instruction, setInstruction] = useState<string>('Widen the central mounting hole by 4 mm');
  const [mode, setMode] = useState<'patch' | 'full_regen'>('patch');
  const [retryCount, setRetryCount] = useState<number>(3);
  const [validationState, setValidationState] = useState<{
    valid: boolean | null;
    message: string;
    loading: boolean;
  }>({ valid: null, message: '', loading: false });

  // Job execution state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('IDLE');
  const [currentAttempt, setCurrentAttempt] = useState<number>(1);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [jobError, setJobError] = useState<string | null>(null);
  const [jobResult, setJobResult] = useState<JobResult | null>(null);
  const [rawPatch, setRawPatch] = useState<string | null>(null);

  // 3D Viewer options
  const [isOverlayMode, setIsOverlayMode] = useState(false);
  const [syncCameras, setSyncCameras] = useState(true);
  const [sharedCameraState, setSharedCameraState] = useState<{
    position: THREE.Vector3;
    target: THREE.Vector3;
  } | null>(null);

  // Iterative editing history
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // File upload input ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load config and examples on mount
  useEffect(() => {
    fetch('/api/config')
      .then((res) => res.json())
      .then((data) => {
        setBackendMode(data.model_backend || 'mock');
        if (data.available_modes) setAvailableModes(data.available_modes);
      })
      .catch((err) => console.warn('Could not fetch server config:', err));

    fetch('/api/examples')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setExamples(data);
      })
      .catch((err) => console.warn('Could not fetch examples:', err));
  }, []);

  // Keyboard shortcut Ctrl/Cmd + Enter to submit
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (jobStatus !== 'QUEUED' && jobStatus !== 'GENERATING' && jobStatus !== 'APPLYING' && jobStatus !== 'EXECUTING') {
          handleExecuteEdit();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [script, instruction, mode, retryCount, jobStatus]);

  // Dry-run validate script
  const handleValidateScript = async () => {
    setValidationState({ valid: null, message: '', loading: true });
    try {
      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script })
      });
      const data = await res.json();
      if (data.valid) {
        setValidationState({
          valid: true,
          message: `Valid solid geometry (Volume: ${data.volume ? data.volume.toFixed(1) : 0} mm³)`,
          loading: false
        });
      } else {
        setValidationState({
          valid: false,
          message: data.error || 'Invalid script or geometry error',
          loading: false
        });
      }
    } catch (e: any) {
      setValidationState({ valid: false, message: e.message || 'Validation request failed', loading: false });
    }
  };

  // Execute Edit Job with SSE Streaming
  const handleExecuteEdit = async () => {
    if (!instruction.trim()) {
      alert('Please enter an editing instruction.');
      return;
    }

    setJobStatus('VALIDATING');
    setStatusMessage('Initiating edit job...');
    setJobError(null);
    setJobResult(null);
    setRawPatch(null);
    setCurrentAttempt(1);

    try {
      const res = await fetch('/api/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script,
          instruction,
          mode,
          retry_count: retryCount
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        setJobStatus('FAILED');
        setJobError(errData.detail || 'Failed to submit edit job.');
        setStatusMessage(errData.detail || 'Submission rejected.');
        return;
      }

      const { job_id } = await res.json();
      setActiveJobId(job_id);

      // Connect to SSE stream
      const eventSource = new EventSource(`/api/jobs/${job_id}/events`);

      eventSource.onmessage = (event) => {
        try {
          const data: JobEvent = JSON.parse(event.data);
          setJobStatus(data.status);
          setCurrentAttempt(data.current_attempt || 1);
          setStatusMessage(data.message || '');

          if (data.raw_patch) setRawPatch(data.raw_patch);
          if (data.error) setJobError(data.error);

          if (data.status === 'FAILED') {
            setJobError(data.error || data.message || 'Editing operation failed');
          }

          if (data.result) {
            setJobResult(data.result);
            if (data.result.raw_patch) setRawPatch(data.result.raw_patch);
            if (data.result.error) setJobError(data.result.error);

            // Add to session history
            if (data.result.status === 'COMPLETED' && data.result.edited_script) {
              setHistory((prev) => [
                {
                  id: data.result!.job_id,
                  timestamp: new Date().toLocaleTimeString(),
                  instruction,
                  script: data.result!.edited_script!,
                  patchText: data.result!.patch_text,
                  volumeChangePct: data.result!.metrics?.volume_change_pct
                },
                ...prev.slice(0, 9)
              ]);
            }
          }

          if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(data.status)) {
            eventSource.close();
          }
        } catch (err) {
          console.error('Error parsing SSE event:', err);
        }
      };

      eventSource.onerror = (err) => {
        console.warn('SSE stream closed or encountered error:', err);
        eventSource.close();
      };
    } catch (e: any) {
      setJobStatus('FAILED');
      setJobError(e.message || 'Network error communicating with API.');
    }
  };

  // Cancel Job
  const handleCancelJob = async () => {
    if (!activeJobId) return;
    try {
      await fetch(`/api/jobs/${activeJobId}/cancel`, { method: 'POST' });
      setJobStatus('CANCELLED');
      setStatusMessage('Job was cancelled.');
    } catch (e) {
      console.warn('Failed to cancel job:', e);
    }
  };

  // Continue editing from edited result (Chaining)
  const handleContinueEditing = () => {
    if (!jobResult?.edited_script) return;
    setScript(jobResult.edited_script);
    setInstruction('');
    setJobResult(null);
    setJobStatus('IDLE');
    setStatusMessage('');
  };

  // Revert to a specific history version
  const handleRevertHistory = (item: HistoryItem) => {
    setScript(item.script);
    setInstruction('');
    setJobResult(null);
    setJobStatus('IDLE');
  };

  // File upload handler
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        setScript(content);
        setValidationState({ valid: null, message: '', loading: false });
      }
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Sync camera change
  const handleCameraChange = (cam: { position: THREE.Vector3; target: THREE.Vector3 }) => {
    if (syncCameras) {
      setSharedCameraState(cam);
    }
  };

  return (
    <div className={isDark ? '' : 'light-theme'} style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept=".py,.txt"
        style={{ display: 'none' }}
      />

      {/* Navigation Header */}
      <header style={{
        background: 'var(--bg-card)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-color)',
        position: 'sticky',
        top: 0,
        zIndex: 50
      }}>
        <div className="app-container" style={{ padding: '0.85rem 2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Logo & Title */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-glow)'
            }}>
              <Code size={20} color="#ffffff" strokeWidth={2.5} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                  CAD Patch Editor
                </span>
                <span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>IE 643</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Learning to Edit Parametric CAD Programs from Natural Language
              </p>
            </div>
          </div>

          {/* Header Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            {/* Backend status indicator */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '9999px',
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid var(--border-color)',
              fontSize: '0.75rem'
            }}>
              <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--accent-emerald)' }} />
              <span style={{ color: 'var(--text-muted)' }}>Backend:</span>
              <span style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                {backendMode === 'mock' ? 'Mock Deterministic Patcher' : 'LoRA Fine-Tuned'}
              </span>
            </div>

            {/* Gallery Modal Button */}
            <button
              onClick={() => setGalleryOpen(true)}
              className="btn-secondary"
              style={{ fontSize: '0.825rem' }}
            >
              <Sparkles size={15} color="var(--accent-cyan)" />
              <span>Examples</span>
            </button>

            {/* Help / Convention Modal Button */}
            <button
              onClick={() => setHelpOpen(true)}
              className="btn-secondary"
              style={{ fontSize: '0.825rem' }}
            >
              <HelpCircle size={15} color="var(--accent-blue)" />
              <span>Convention</span>
            </button>

            {/* Theme Toggle */}
            <button
              onClick={() => setIsDark(!isDark)}
              className="btn-outline"
              style={{ padding: '0.5rem' }}
              title="Toggle Theme"
            >
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <main className="app-container" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1rem' }}>
        {/* Hero Notice Banner */}
        <div className="glass-card" style={{
          padding: '0.75rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'linear-gradient(90deg, rgba(14, 165, 233, 0.08) 0%, rgba(6, 182, 212, 0.04) 100%)',
          borderLeft: '4px solid var(--accent-blue)'
        }}>
          <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
            <strong style={{ color: 'var(--text-main)' }}>Parametric Code Patching:</strong> Edits executable CadQuery scripts via localized search/replace blocks rather than full-program regeneration, achieving zero unintended modifications and 68.5% smaller outputs.
          </p>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)', whiteSpace: 'nowrap', marginLeft: '1rem' }}>
            Shortcut: <kbd style={{ padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'var(--border-color)', color: 'var(--text-main)' }}>Ctrl + Enter</kbd>
          </span>
        </div>

        {/* Two-Column Editor & 3D Workspace */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(420px, 1fr) minmax(500px, 1.25fr)', gap: '1.5rem', alignItems: 'start' }}>
          {/* Left Column: Script Editor, Instruction, & Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Script Code Editor Card */}
            <div className="glass-card" style={{ overflow: 'hidden' }}>
              <div style={{
                padding: '0.65rem 1rem',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(15, 23, 42, 0.5)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Code size={16} color="var(--accent-blue)" />
                  <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>CadQuery Python Script</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn-outline"
                    title="Upload .py file"
                  >
                    <Upload size={13} />
                    <span>Upload</span>
                  </button>
                  <button
                    onClick={handleValidateScript}
                    disabled={validationState.loading}
                    className="btn-outline"
                    title="Dry-run script in sandbox"
                  >
                    <span>{validationState.loading ? 'Checking...' : 'Dry-Run'}</span>
                  </button>
                  <button
                    onClick={() => setScript(DEFAULT_SCRIPT)}
                    className="btn-outline"
                    title="Reset to default script"
                  >
                    <RotateCcw size={13} />
                  </button>
                </div>
              </div>

              {/* Textarea Code Input */}
              <textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                spellCheck={false}
                rows={16}
                className="code-font"
                style={{
                  width: '100%',
                  background: 'transparent',
                  color: 'var(--text-main)',
                  border: 'none',
                  padding: '1rem',
                  fontSize: '0.85rem',
                  lineHeight: '1.6',
                  resize: 'vertical',
                  outline: 'none'
                }}
              />

              {/* Validation Feedback Strip */}
              {validationState.valid !== null && (
                <div style={{
                  padding: '0.5rem 1rem',
                  borderTop: '1px solid var(--border-color)',
                  background: validationState.valid ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.8rem',
                  color: validationState.valid ? 'var(--accent-emerald)' : 'var(--accent-rose)'
                }}>
                  {validationState.valid ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                  <span>{validationState.message}</span>
                </div>
              )}
            </div>

            {/* Natural-Language Instruction & Submission Card */}
            <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <label style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-main)' }}>
                  Natural-Language Edit Instruction
                </label>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                  {instruction.length}/500 chars
                </span>
              </div>

              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="e.g. Widen the mounting holes by 2 mm, or make the arm longer by 10 mm"
                rows={2}
                maxLength={500}
                style={{
                  width: '100%',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  color: 'var(--text-main)',
                  padding: '0.75rem',
                  fontSize: '0.875rem',
                  resize: 'none',
                  outline: 'none'
                }}
              />

              {/* Options & Settings */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                {/* Mode Select */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Mode:</span>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as any)}
                    style={{
                      background: 'rgba(15, 23, 42, 0.8)',
                      color: 'var(--text-main)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '6px',
                      padding: '0.25rem 0.5rem',
                      fontSize: '0.8rem',
                      outline: 'none'
                    }}
                  >
                    <option value="patch">Search/Replace Patch (Ours)</option>
                    {availableModes.includes('full_regen') && (
                      <option value="full_regen">Full Regeneration Baseline</option>
                    )}
                  </select>
                </div>

                {/* Retries */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Max Retries:</span>
                  <select
                    value={retryCount}
                    onChange={(e) => setRetryCount(parseInt(e.target.value, 10))}
                    style={{
                      background: 'rgba(15, 23, 42, 0.8)',
                      color: 'var(--text-main)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '6px',
                      padding: '0.25rem 0.5rem',
                      fontSize: '0.8rem',
                      outline: 'none'
                    }}
                  >
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                    <option value={3}>3 (Default)</option>
                    <option value={5}>5</option>
                  </select>
                </div>
              </div>

              {/* Primary Action Button */}
              <button
                onClick={handleExecuteEdit}
                disabled={['VALIDATING', 'GENERATING', 'APPLYING', 'EXECUTING'].includes(jobStatus)}
                className="btn-primary"
                style={{ width: '100%', marginTop: '0.25rem' }}
              >
                <Play size={16} fill="currentColor" />
                <span>
                  {['VALIDATING', 'GENERATING', 'APPLYING', 'EXECUTING'].includes(jobStatus)
                    ? 'Processing CAD Edit...'
                    : 'Apply CAD Patch'}
                </span>
              </button>
            </div>

            {/* Live Progress Stepper */}
            {jobStatus !== 'IDLE' && (
              <ProgressStepper
                status={jobStatus}
                attempt={currentAttempt}
                maxAttempts={retryCount}
                message={statusMessage}
                error={jobError || undefined}
                rawPatch={rawPatch || undefined}
                onCancel={handleCancelJob}
              />
            )}

            {/* Session History List */}
            {history.length > 0 && (
              <div className="glass-card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: 700 }}>
                  <History size={16} color="var(--accent-blue)" />
                  <span>Session Edit History ({history.length})</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '180px', overflowY: 'auto' }}>
                  {history.map((item, idx) => (
                    <div
                      key={item.id + idx}
                      style={{
                        background: 'rgba(15, 23, 42, 0.5)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '6px',
                        padding: '0.5rem 0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '0.775rem'
                      }}
                    >
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '280px' }}>
                        <span style={{ color: 'var(--text-faint)', marginRight: '0.4rem' }}>{item.timestamp}</span>
                        <span style={{ fontWeight: 600 }}>"{item.instruction}"</span>
                      </div>
                      <button
                        onClick={() => handleRevertHistory(item)}
                        className="btn-outline"
                        style={{ padding: '0.2rem 0.45rem', fontSize: '0.7rem' }}
                      >
                        Revert
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: 3D Viewers, Downloads, Diff, and Metrics */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* 3D Viewers Toolbar */}
            <div className="glass-card" style={{
              padding: '0.5rem 1rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '0.5rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Layers size={16} color="var(--accent-cyan)" />
                <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>Interactive 3D Geometry</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                {/* Overlay Ghost Mode Toggle */}
                <button
                  onClick={() => setIsOverlayMode(!isOverlayMode)}
                  className={isOverlayMode ? 'btn-primary' : 'btn-outline'}
                  style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                  title="Toggle Translucent Ghost Overlay Mode"
                >
                  <Layers size={13} />
                  <span>{isOverlayMode ? 'Overlay Mode Active' : 'Overlay Mode'}</span>
                </button>

                {/* Camera Sync Toggle */}
                {!isOverlayMode && (
                  <button
                    onClick={() => setSyncCameras(!syncCameras)}
                    className="btn-outline"
                    style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                    title="Synchronize Orbit Cameras"
                  >
                    {syncCameras ? <Link size={13} color="var(--accent-cyan)" /> : <Unlink size={13} />}
                    <span>{syncCameras ? 'Synced' : 'Unlinked'}</span>
                  </button>
                )}
              </div>
            </div>

            {/* 3D Viewer Container */}
            {isOverlayMode ? (
              // Single Combined Canvas with Ghost Overlay
              <ThreeViewer
                title="Superimposed Before / After Geometry (Ghost Mode)"
                glbUrl={jobResult?.download_urls?.glb}
                stlUrl={jobResult?.download_urls?.stl}
                overlayGlbUrl={jobResult?.download_urls?.original_glb}
                isOverlayMode={true}
                height="420px"
              />
            ) : (
              // Side by Side Viewers
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <ThreeViewer
                  title="Original Model (Before)"
                  glbUrl={jobResult?.download_urls?.original_glb}
                  color="#64748b"
                  onCameraChange={handleCameraChange}
                  externalCameraState={sharedCameraState}
                  height="340px"
                />
                <ThreeViewer
                  title="Edited Model (After)"
                  glbUrl={jobResult?.download_urls?.glb}
                  stlUrl={jobResult?.download_urls?.stl}
                  color="#0ea5e9"
                  onCameraChange={handleCameraChange}
                  externalCameraState={sharedCameraState}
                  height="340px"
                />
              </div>
            )}

            {/* Action Bar: Download & Continue Editing */}
            {jobResult && (
              <div className="glass-card" style={{
                padding: '0.85rem 1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '0.75rem',
                background: 'rgba(15, 23, 42, 0.6)'
              }}>
                {/* Download Buttons */}
                <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.4rem' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '0.3rem' }}>
                    Download:
                  </span>
                  <a href={jobResult.download_urls.py} download="edited_model.py" className="btn-outline" style={{ textDecoration: 'none' }}>
                    <Download size={13} />
                    <span>Python (.py)</span>
                  </a>
                  <a href={jobResult.download_urls.patch} download="patch.diff" className="btn-outline" style={{ textDecoration: 'none' }}>
                    <Download size={13} />
                    <span>Patch (.diff)</span>
                  </a>
                  <a href={jobResult.download_urls.stl} download="model.stl" className="btn-outline" style={{ textDecoration: 'none' }}>
                    <Download size={13} />
                    <span>STL</span>
                  </a>
                  <a href={jobResult.download_urls.step} download="model.step" className="btn-outline" style={{ textDecoration: 'none' }}>
                    <Download size={13} />
                    <span>STEP</span>
                  </a>
                  <a href={jobResult.download_urls.glb} download="model.glb" className="btn-outline" style={{ textDecoration: 'none' }}>
                    <Download size={13} />
                    <span>GLB</span>
                  </a>
                </div>

                {/* Chaining Button: Continue editing from this result */}
                <button
                  onClick={handleContinueEditing}
                  className="btn-primary"
                  style={{ fontSize: '0.825rem', padding: '0.5rem 1rem' }}
                >
                  <span>Continue Editing from Result</span>
                  <ArrowRight size={14} />
                </button>
              </div>
            )}

            {/* Predicted Diff Viewer */}
            <DiffViewer
              patchText={jobResult?.patch_text}
              linesTouched={jobResult?.change_summary?.lines_touched}
            />

            {/* Parametric and Geometric Impact Summary */}
            <ChangeSummaryPanel
              changeSummary={jobResult?.change_summary}
              metrics={jobResult?.metrics}
            />
          </div>
        </div>

        {/* How It Works Educational Section */}
        <section className="glass-card" style={{ padding: '1.75rem', marginTop: '1rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sparkles size={18} color="var(--accent-cyan)" />
            How the CadQuery Patch-Editing Pipeline Works
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
            Unlike token-sequence generative approaches that hallucinate full construction files, our framework predicts localized search/replace blocks over deterministic Python CAD programs.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
            <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-blue)', fontWeight: 700 }}>STEP 1</div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0.25rem 0' }}>Sandbox Pre-flight</h4>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Verifies input script syntax and executes original geometry in an isolated OpenCASCADE subprocess.
              </p>
            </div>
            <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>STEP 2</div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0.25rem 0' }}>Patch Generation</h4>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Fine-tuned code LLM with LoRA predicts minimal search/replace modifications conditioned on the natural-language prompt.
              </p>
            </div>
            <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-indigo)', fontWeight: 700 }}>STEP 3</div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0.25rem 0' }}>Patch Application</h4>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Applies exact substring matching with automatic constrained retries (up to k attempts) if output is malformed.
              </p>
            </div>
            <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 700 }}>STEP 4</div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0.25rem 0' }}>Geometric Evaluation</h4>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Executes edited solid into B-Rep, exports STL/STEP/GLB, and computes Chamfer distance and volumetric IoU.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer style={{
        marginTop: '2rem',
        borderTop: '1px solid var(--border-color)',
        padding: '1.5rem 2rem',
        background: 'var(--bg-secondary)',
        fontSize: '0.8rem',
        color: 'var(--text-muted)'
      }}>
        <div className="app-container" style={{ padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span>IE 643 Course Project — Team AIADMK (T Ganesh, Surhud Naik)</span>
            <span style={{ margin: '0 0.5rem' }}>•</span>
            <span style={{ color: 'var(--text-faint)' }}>Privacy: No user data retained; job artifacts automatically expire via 1h TTL.</span>
          </div>
          <div style={{ color: 'var(--text-faint)' }}>
            Disclaimer: AI model outputs should always be visually inspected and verified before manufacturing.
          </div>
        </div>
      </footer>

      {/* Modals */}
      <ExampleGalleryModal
        isOpen={galleryOpen}
        onClose={() => setGalleryOpen(false)}
        examples={examples}
        onSelect={(ex) => {
          setScript(ex.script);
          setInstruction(ex.instruction);
          setValidationState({ valid: null, message: '', loading: false });
        }}
      />

      <ConventionHelpModal
        isOpen={helpOpen}
        onClose={() => setHelpOpen(false)}
      />
    </div>
  );
}

export default App;
