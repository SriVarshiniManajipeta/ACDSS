import React, { useState } from 'react';
import { Activity, Info, MapPin, CalendarCheck } from 'lucide-react';

export function statusClass(s = '') {
  const v = s.toLowerCase();
  if (v === 'high')       return 'flag-high';
  if (v === 'low')        return 'flag-low';
  if (v === 'borderline') return 'flag-borderline';
  if (v === 'normal')     return 'flag-normal';
  return 'flag-unknown';
}
export function statusEmoji(s = '') {
  const v = s.toLowerCase();
  if (v === 'high')       return '▲';
  if (v === 'low')        return '▼';
  if (v === 'borderline') return '◆';
  if (v === 'normal')     return '●';
  return '○';
}

export function DiagnosisBubble({ data, onWantTreatment, onWantDoctors }) {
  const conf    = data.confidence_score ?? 75;
  const confClr = conf >= 80 ? '#86efac' : conf >= 60 ? '#fde047' : '#fca5a5';

  return (
    <div className="analysis-bubble">
      {/* Header */}
      <div className="analysis-header">
        <div className="analysis-icon"><Activity size={17} color="white" /></div>
        <div style={{ flex:1 }}>
          <div className="analysis-title">Diagnosis Complete</div>
          <div className="analysis-hyp">{data.primary_hypothesis}</div>
        </div>
        {/* Confidence badge */}
        <div className="conf-badge" style={{ color: confClr, borderColor: confClr }}>
          {conf}% confidence
        </div>
      </div>

      {/* ── Diagnosis summary — what we found, in plain English ── */}
      {(data.primary_hypothesis || data.simple_explanation) && (
        <div className="plain-english-card">
          <div className="pe-label">
            <span className="pe-icon">📋</span> Diagnosis summary
          </div>
          <p className="pe-text">
            From your report, the most likely issue is{' '}
            <strong>{data.primary_hypothesis || 'a general health concern'}</strong>.
            {data.simple_explanation ? ' ' + data.simple_explanation : ''}
          </p>
        </div>
      )}

      {/* Evaluator key abnormalities */}
      {data.key_abnormalities?.length > 0 && (
        <div className="key-flags">
          <span className="kf-label">⚠ Key findings:</span>
          {data.key_abnormalities.map((k, i) => (
            <span key={i} className="kf-chip">{k}</span>
          ))}
        </div>
      )}

      {/* Lab table */}
      {data.detailed_analysis?.length > 0 && (
        <div className="lab-table-wrapper">
          <table className="lab-table">
            <thead>
              <tr><th>Test</th><th>Value</th><th>Reference</th><th>Status</th></tr>
            </thead>
            <tbody>
              {data.detailed_analysis.map((row, i) => (
                <tr key={i}>
                  <td className="test-name">{row.test_name}</td>
                  <td className="test-value">{row.patient_value}</td>
                  <td className="test-ref">{row.reference_range || '—'}</td>
                  <td>
                    <span className={`status-flag ${statusClass(row.status)}`}>
                      {statusEmoji(row.status)} {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Evaluator notes */}
      {data.evaluation_notes && (
        <div className="eval-notes">
          <Info size={12} style={{ flexShrink:0, marginTop:2 }} />
          <span>{data.evaluation_notes}</span>
        </div>
      )}

      {/* CTA row */}
      <div className="analysis-cta" style={{ flexWrap:'wrap', gap:8 }}>
        <span style={{ fontSize:13, color:'var(--text-secondary)' }}>
          Specialist: <strong style={{ color:'var(--text-primary)' }}>
            {data.recommended_specialization}
          </strong>
        </span>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
          <button className="find-doctors-btn" onClick={onWantDoctors}>
            <MapPin size={14} /> Find Specialist
          </button>
          <button className="find-doctors-btn" style={{ background:'rgba(255,255,255,0.08)', color:'#e2e2e2', boxShadow:'none', border:'1px solid rgba(255,255,255,0.12)' }}
            onClick={onWantTreatment}>
            <CalendarCheck size={14} /> Get Treatment Plan
          </button>
        </div>
      </div>
    </div>
  );
}
