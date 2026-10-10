import React from 'react';
import { Stethoscope, UserRound } from 'lucide-react';

export function MsgRow({ role, children }) {
  return (
    <div className={`msg-wrapper ${role}`}>
      <div className={`msg-avatar ${role}`}>
        {role === 'assistant'
          ? <Stethoscope size={14} color="white" />
          : <UserRound size={15} />}
      </div>
      {children}
    </div>
  );
}
