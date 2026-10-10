import React from 'react';
import { CheckCircle } from 'lucide-react';


export function BookingBubble({ data }) {
  return (
    <div className="booking-confirm">
      <CheckCircle size={20} color="var(--success)" style={{ flexShrink:0, marginTop:1 }} />
      <div>
        <div className="booking-title">Appointment Confirmed ✅</div>
        <div className="booking-detail">
          <span>Doctor: <strong>{data.doctor_name}</strong></span>
          <span>Patient: <strong>{data.patient_name}</strong></span>
          <span>Slot: <strong>{data.slot}</strong></span>
          <span>Status: <strong style={{ textTransform:'capitalize' }}>{data.status}</strong></span>
        </div>
      </div>
    </div>
  );
}
