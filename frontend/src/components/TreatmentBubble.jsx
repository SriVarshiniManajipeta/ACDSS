import React, { useState } from 'react';
import { TrendingUp, CalendarCheck, ChevronDown, Shield } from 'lucide-react';


export const SEVERITY_STYLE = {
  mild:     { color: '#86efac', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.22)'   },
  moderate: { color: '#fde047', bg: 'rgba(234,179,8,0.08)',   border: 'rgba(234,179,8,0.22)'   },
  severe:   { color: '#fca5a5', bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.30)'   },
  critical: { color: '#f87171', bg: 'rgba(239,68,68,0.16)',   border: 'rgba(239,68,68,0.45)'   },
};

export function TreatmentBubble({ data, problem, onDone }) {
  const [showSteps, setShowSteps] = useState(false);
  const sev   = (data.severity_level || 'moderate').toLowerCase();
  const style = SEVERITY_STYLE[sev] || SEVERITY_STYLE.moderate;
  const steps = data.treatment_plan || [];

  const prog       = (data.prognosis || '').trim();
  const followupQ  = (data.follow_up_question || '').trim();
  const showFollowup = followupQ &&
    followupQ !== prog &&
    followupQ !== (data.disease_explanation || '').trim();

  return (
    <div className="analysis-bubble" style={{ borderTop:`2px solid ${style.border}` }}>
      {/* Severity header */}
      <div className="analysis-header" style={{ background:`linear-gradient(135deg, ${style.bg}, transparent)` }}>
        <div className="analysis-icon" style={{ background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.12)' }}>
          <TrendingUp size={17} color={style.color} />
        </div>
        <div style={{ flex:1 }}>
          <div className="analysis-title">Treatment Plan</div>
          <div className="analysis-hyp">{data.disease_explanation}</div>
        </div>
        <div className="sev-badge" style={{ color: style.color, borderColor: style.border, background: style.bg }}>
          {sev.toUpperCase()}
        </div>
      </div>

      {/* ── Summary: what we discovered + how it's treated (always visible) ── */}
      <div className="tx-summary">
        <div className="txs-block">
          <div className="txs-label">🔍 What we found in your report</div>
          <p className="txs-text">
            {problem?.hypothesis ? <><strong>{problem.hypothesis}</strong>. </> : null}
            {data.disease_explanation || problem?.plain || 'See the diagnosis above for details.'}
          </p>
          {problem?.findings?.length > 0 && (
            <div className="txs-findings">Key findings: {problem.findings.join(', ')}</div>
          )}
        </div>

        <div className="txs-block">
          <div className="txs-label"> How it's treated</div>
          {steps.length > 0 ? (
            <ul className="txs-list">
              {steps.slice(0, 4).map((s, i) => (
                <li key={i}>
                  <strong>{s.medication_or_action}</strong>
                  {s.dosage_or_detail ? ` — ${s.dosage_or_detail}` : ''}
                </li>
              ))}
            </ul>
          ) : (
            <p className="txs-text">A personalised plan is outlined below.</p>
          )}
          {data.prognosis && (
            <p className="txs-outlook">📈 Outlook: {data.prognosis}</p>
          )}
        </div>
      </div>

      {/* Treatment steps accordion (full detail with rationale) */}
      {data.treatment_plan?.length > 0 && (
        <div className="treatment-section">
          <button className="treatment-toggle" onClick={() => setShowSteps(v => !v)}>
            <CalendarCheck size={14} />
            Full treatment details with rationale ({data.treatment_plan.length} items)
            <ChevronDown size={14} className={`chevron ${showSteps ? 'open' : ''}`} />
          </button>
          {showSteps && (
            <div className="treatment-cards">
              {data.treatment_plan.map((step, i) => (
                <div className="treatment-card" key={i}>
                  <div className="tc-action">{step.medication_or_action}</div>
                  <div className="tc-detail">{step.dosage_or_detail}</div>
                  <div className="tc-rationale">{step.rationale}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Follow-up scheduling note (prognosis already shown as "Outlook" above) */}
      {data.follow_up && (
        <div className="prognosis-row">
          <div className="prog-chip prog-info">🗓 {data.follow_up}</div>
        </div>
      )}

      {/* Meta Evaluation (Call 3 Auditor) */}
      {data.meta_evaluation && (
        <div className="meta-eval-section">
          <div className="me-header">
            <Shield size={14} /> AI Clinical Audit Report
          </div>
          <div className="me-grid">
            <div className="me-stat">
              <span className="me-label">Quality Score</span>
              <span className="me-val">{data.meta_evaluation.overall_quality_score}%</span>
            </div>
            <div className="me-stat">
              <span className="me-label">Safety</span>
              <span className={`me-val me-${data.meta_evaluation.safety_verdict.replace(/_/g, '-')}`}>
                {data.meta_evaluation.safety_verdict.replace(/_/g, ' ').toUpperCase()}
              </span>
            </div>
          </div>
          {data.meta_evaluation.safety_flags?.length > 0 && (
            <div className="me-flags">
              <strong>⚠ Flags:</strong> {data.meta_evaluation.safety_flags.join(', ')}
            </div>
          )}
          <p className="me-summary"><strong>Summary:</strong> {data.meta_evaluation.clinical_summary}</p>
          <p className="me-recs"><strong>Recommendations:</strong> {data.meta_evaluation.pipeline_recommendations}</p>
        </div>
      )}

      {/* Follow-up question — only when it's a genuine, non-duplicate question */}
      {showFollowup && (
        <div className="followup-cta" style={{ borderColor: style.border, background: style.bg }}>
          <span style={{ color: style.color, fontSize:13, fontWeight:600 }}>
            💬 {followupQ}
          </span>
        </div>
      )}
    </div>
  );
}
