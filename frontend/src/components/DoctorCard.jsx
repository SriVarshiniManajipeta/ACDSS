import React from 'react';
import {
  UserRound, MapPin, Clock, Heart, Brain, Eye, Bone, Zap, Activity, Smile, Stethoscope
} from 'lucide-react';


export const SPEC_ICONS = {
  'Cardiologist':       <Heart size={16} />,
  'Neurologist':        <Brain size={16} />,
  'Ophthalmologist':    <Eye size={16} />,
  'Orthopedic':         <Bone size={16} />,
  'Dermatologist':      <Zap size={16} />,
  'Gastroenterologist': <Activity size={16} />,
  'Psychiatrist':       <Smile size={16} />,
  'Endocrinologist':    <Activity size={16} />,
  'Nephrologist':       <Activity size={16} />,
  'Pulmonologist':      <Activity size={16} />,
  'General Physician':  <Stethoscope size={16} />,
};

export function DoctorCard({ doctor, onBook }) {
  return (
    <div className="doctor-card">
      <div className="doctor-card-top">
        <div className="doctor-avatar">
          {SPEC_ICONS[doctor.specialization] || <UserRound size={16} />}
        </div>
        <div className="doctor-info">
          <h3 title={doctor.name}>{doctor.name}</h3>
          <div className="doctor-meta">
            <span className="spec-tag">{doctor.specialization}</span>
            <span>{doctor.hospital}</span>
            <span style={{ display:'flex', alignItems:'center', gap:3 }}>
              <MapPin size={10} /> {doctor.location}
            </span>
          </div>
        </div>
      </div>
      <div className="doctor-stats">
        <span className="stat-pill rating">⭐ {doctor.rating}</span>
        <span className="stat-pill exp">{doctor.experience_years} yrs exp</span>
      </div>
      <div className="slots-label">Available Slots</div>
      <div className="slots">
        {doctor.available_slots.length > 0
          ? doctor.available_slots.map(slot => (
            <button key={slot} className="slot-btn" onClick={() => onBook(doctor, slot)}>
              <Clock size={10} style={{ marginRight:2 }} />{slot}
            </button>
          ))
          : <span style={{ fontSize:11, color:'var(--text-muted)' }}>No slots</span>
        }
      </div>
    </div>
  );
}
