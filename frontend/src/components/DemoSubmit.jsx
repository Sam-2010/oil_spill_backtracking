import { useRef, useState } from 'react'

// Color palette: spill #EF4444, cyan #38BDF8, amber #F59E0B
const C = {
  abyss: '#0B1326',
  hull: '#171F33',
  line: '#334155',
  foam: '#DAE2FD',
  dim: '#86948A',
  amber: '#F59E0B',
  cyan: '#38BDF8',
  spill: '#EF4444',
  good: '#10B981',
}

const STATUS_LINES = [
  'Ingesting SAR scene…',
  'Running U-Net segmentation…',
  'Vectorizing detection…',
  'Correlating drift model…',
]

export default function DemoSubmit({ delayMs = 12000, onComplete }) {
  const [files, setFiles] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusIdx, setStatusIdx] = useState(0)
  const fileInputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    const dropped = Array.from(e.dataTransfer?.files || [])
    addFiles(dropped)
  }

  const addFiles = (newFiles) => {
    const imageFiles = newFiles.filter((f) =>
      /\.(tif|tiff|png|jpg|jpeg)$/i.test(f.name)
    )
    setFiles((prev) => [...prev, ...imageFiles])
  }

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  const handleFileInput = (e) => {
    const selected = Array.from(e.target.files || [])
    addFiles(selected)
    e.target.value = '' // Reset to allow re-selecting same files
  }

  const runDetection = () => {
    if (files.length === 0 || isProcessing) return
    setIsProcessing(true)
    setProgress(0)
    setStatusIdx(0)

    const start = Date.now()
    const interval = setInterval(() => {
      const elapsed = Date.now() - start
      const pct = Math.min((elapsed / delayMs) * 100, 100)
      setProgress(pct)

      const newIdx = Math.min(
        Math.floor((elapsed / delayMs) * STATUS_LINES.length),
        STATUS_LINES.length - 1
      )
      setStatusIdx(newIdx)

      if (elapsed >= delayMs) {
        clearInterval(interval)
        setProgress(100)
        setIsProcessing(false)
        setFiles([])
        onComplete?.()
      }
    }, 50)
  }

  const hasFiles = files.length > 0

  return (
    <div
      className="demo-submit"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      {/* Glass panel */}
      <div className="demo-panel">
        <h3 className="demo-title">SAR Scene Upload</h3>

        {/* Dropzone */}
        <div
          className={`dropzone ${isProcessing ? 'disabled' : ''}`}
          onClick={isProcessing ? undefined : openFilePicker}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".tif,.tiff,.png,.jpg,.jpeg"
            onChange={handleFileInput}
            disabled={isProcessing}
          />
          <div className="dropzone-content">
            <div className="dropzone-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17,8 12,3 7,8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <div className="dropzone-text">
              <p className="dropzone-primary">
                {hasFiles ? `${files.length} file${files.length > 1 ? 's' : ''} selected` : 'Drop SAR images here'}
              </p>
              <p className="dropzone-secondary">
                .tif, .tiff, .png, .jpg, .jpeg
              </p>
            </div>
          </div>
        </div>

        {/* Thumbnail grid */}
        {files.length > 0 && (
          <div className="thumb-grid">
            {files.map((f, i) => (
              <div key={`${f.name}-${i}`} className="thumb-item">
                <div className="thumb-preview">
                  <span className="thumb-ext">
                    {f.name.split('.').pop().toUpperCase()}
                  </span>
                </div>
                <span className="thumb-name" title={f.name}>
                  {f.name.length > 24 ? f.name.slice(0, 12) + '…' + f.name.slice(-10) : f.name}
                </span>
                {!isProcessing && (
                  <button
                    className="thumb-remove"
                    onClick={() => removeFile(i)}
                    aria-label="Remove file"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Run button */}
        <button
          className="run-btn"
          onClick={runDetection}
          disabled={!hasFiles || isProcessing}
        >
          {isProcessing ? 'Processing…' : 'Run Detection'}
        </button>
      </div>

      {/* Processing overlay */}
      {isProcessing && (
        <div className="processing-overlay">
          <div className="processing-card">
            <div className="processing-spinner">
              {[...Array(12)].map((_, i) => (
                <span key={i} style={{ '--i': i }} />
              ))}
            </div>
            <p className="processing-status">{STATUS_LINES[statusIdx]}</p>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <p className="progress-pct">{Math.round(progress)}%</p>
          </div>
        </div>
      )}

      <style>{`
        .demo-submit {
          position: relative;
          font-family: system-ui, -apple-system, sans-serif;
        }

        .demo-panel {
          padding: 20px 24px;
          background: linear-gradient(180deg, rgba(23, 31, 51, 0.65) 0%, rgba(11, 19, 38, 0.7) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          backdrop-filter: blur(12px);
        }

        .demo-title {
          font-size: 14px;
          font-weight: 600;
          letter-spacing: 0.03em;
          color: ${C.foam};
          margin: 0 0 16px 0;
          padding-bottom: 12px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }

        .dropzone {
          border: 1.5px dashed ${C.line};
          border-radius: 8px;
          padding: 24px;
          text-align: center;
          cursor: pointer;
          transition: all 0.15s ease;
          background: rgba(11, 19, 38, 0.4);
        }

        .dropzone:not(.disabled):hover {
          border-color: ${C.cyan};
          background: rgba(56, 189, 248, 0.05);
        }

        .dropzone.disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .dropzone input {
          display: none;
        }

        .dropzone-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
        }

        .dropzone-icon {
          color: ${C.cyan};
          opacity: 0.7;
        }

        .dropzone-text {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .dropzone-primary {
          font-size: 13px;
          color: ${C.foam};
          margin: 0;
        }

        .dropzone-secondary {
          font-size: 11px;
          color: ${C.dim};
          margin: 0;
        }

        .thumb-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
          gap: 10px;
          margin-top: 16px;
        }

        .thumb-item {
          position: relative;
          background: rgba(11, 19, 38, 0.6);
          border: 1px solid ${C.line};
          border-radius: 6px;
          padding: 8px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .thumb-preview {
          aspect-ratio: 4/3;
          background: ${C.abyss};
          border-radius: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .thumb-ext {
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.05em;
          color: ${C.cyan};
          opacity: 0.8;
        }

        .thumb-name {
          font-size: 10px;
          color: ${C.dim};
          white-space: nowrap;
          overflow: hidden;
        }

        .thumb-remove {
          position: absolute;
          top: 4px;
          right: 4px;
          width: 18px;
          height: 18px;
          border: none;
          background: rgba(239, 68, 68, 0.9);
          color: white;
          border-radius: 50%;
          font-size: 12px;
          line-height: 1;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 0 1px 1px;
          transition: transform 0.1s ease;
        }

        .thumb-remove:hover {
          transform: scale(1.1);
          background: ${C.spill};
        }

        .run-btn {
          width: 100%;
          margin-top: 16px;
          padding: 12px 20px;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.02em;
          color: ${C.abyss};
          background: linear-gradient(180deg, ${C.cyan} 0%, ${C.cyan}ee 100%);
          border: none;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .run-btn:not(:disabled):hover {
          background: linear-gradient(180deg, ${C.cyan}f0 0%, ${C.cyan} 100%);
          box-shadow: 0 0 20px rgba(56, 189, 248, 0.25);
        }

        .run-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* Processing overlay */
        .processing-overlay {
          position: fixed;
          inset: 0;
          background: rgba(2, 4, 9, 0.85);
          backdrop-filter: blur(8px);
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .processing-card {
          width: 320px;
          padding: 32px;
          background: ${C.hull};
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          text-align: center;
          animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes slideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .processing-spinner {
          width: 48px;
          height: 48px;
          margin: 0 auto 20px;
          position: relative;
        }

        .processing-spinner span {
          position: absolute;
          top: 50%;
          left: 50%;
          width: 4px;
          height: 12px;
          background: ${C.cyan};
          border-radius: 2px;
          transform: translate(-50%, -50%) rotate(calc(var(--i) * 30deg)) translateY(-18px);
          opacity: calc(1 - (var(--i) * 0.08));
          animation: spinnerPulse 1.2s linear infinite;
          animation-delay: calc(var(--i) * 0.1s);
        }

        @keyframes spinnerPulse {
          0%, 100% { opacity: 0.15; }
          50% { opacity: 1; }
        }

        .processing-status {
          font-size: 13px;
          color: ${C.foam};
          margin: 0 0 20px 0;
          min-height: 20px;
        }

        .progress-bar {
          height: 4px;
          background: rgba(255, 255, 255, 0.06);
          border-radius: 2px;
          overflow: hidden;
          margin-bottom: 12px;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, ${C.cyan}, ${C.amber});
          border-radius: 2px;
          transition: width 0.05s linear;
        }

        .progress-pct {
          font-size: 12px;
          font-weight: 600;
          color: ${C.dim};
          margin: 0;
          font-variant-numeric: tabular-nums;
        }
      `}</style>
    </div>
  )
}
