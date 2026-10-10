import React, { useState, useRef } from 'react';
import { Upload, FileText, X, RefreshCw, Sparkles } from 'lucide-react';


export function UploadZone({ onAnalyze, loading }) {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile]         = useState(null);
  const [preview, setPreview]   = useState(null);
  const [notes, setNotes]       = useState('');
  const fileInputRef            = useRef(null);

  function handleFile(f) {
    if (!f) return;
    const allowed = ['image/jpeg','image/png','image/jpg','image/bmp','image/tiff'];
    if (!allowed.includes(f.type)) {
      alert('Please upload a JPG or PNG image of your lab report.');
      return;
    }
    setFile(f);
    const reader = new FileReader();
    reader.onload = e => setPreview(e.target.result);
    reader.readAsDataURL(f);
  }

  return (
    <div className="upload-zone-wrapper">
      <div
        className={`upload-zone${dragOver ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
        onClick={() => !file && fileInputRef.current?.click()}
      >
        <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/jpg,image/bmp"
          style={{ display:'none' }} onChange={e => handleFile(e.target.files[0])} />

        {!file ? (
          <div className="upload-prompt">
            <div className="upload-icon-ring">
              <Upload size={26} color="var(--text-secondary)" />
            </div>
            <p className="upload-title">Upload your Lab Report</p>
            <p className="upload-sub">Drag & drop or <span className="upload-link">browse files</span></p>
            <p className="upload-hint">JPG · PNG · Max 10 MB</p>
          </div>
        ) : (
          <div className="upload-preview">
            <img src={preview} alt="Report preview" className="report-thumb" />
            <div className="file-info">
              <FileText size={14} color="var(--text-secondary)" />
              <span>{file.name}</span>
              <button className="remove-file"
                onClick={e => { e.stopPropagation(); setFile(null); setPreview(null); }}>
                <X size={13} />
              </button>
            </div>
          </div>
        )}
      </div>

      <textarea className="notes-input"
        placeholder="Optional: Add clinical context (e.g. 'Patient has diabetes history'…)"
        value={notes} onChange={e => setNotes(e.target.value)} rows={2} />

      <button className="analyze-btn" disabled={!file || loading}
        onClick={() => onAnalyze(file, notes)}>
        {loading
          ? <><RefreshCw size={16} className="spin" /> Analysing…</>
          : <><Sparkles size={16} /> Run AI Diagnosis</>
        }
      </button>
    </div>
  );
}
