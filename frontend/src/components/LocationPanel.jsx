import React, { useState } from 'react';
import { MapPin, Navigation, RefreshCw, ChevronRight } from 'lucide-react';


export function LocationPanel({ onConfirm, loading }) {
  const [city, setCity]     = useState('');
  const [geoErr, setGeoErr] = useState('');
  const [geo, setGeo]       = useState(false);

  function detectGeo() {
    if (!navigator.geolocation) { setGeoErr('Geolocation not supported.'); return; }
    setGeo(true); setGeoErr('');
    navigator.geolocation.getCurrentPosition(
      () => { setGeo(false); setGeoErr('Auto-detected. Type your city name below.'); },
      () => { setGeo(false); setGeoErr('Access denied. Please type your city.'); },
      { timeout: 8000 },
    );
  }

  return (
    <div className="location-panel">
      <div className="loc-header">
        <MapPin size={16} color="var(--text-secondary)" />
        <span>Where should I find specialists?</span>
      </div>
      <div className="loc-row">
        <input className="loc-input"
          placeholder="Type your city (e.g. Hyderabad, Chennai…)"
          value={city} onChange={e => setCity(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && city.trim() && onConfirm(city.trim())} />
        <button className="loc-geo-btn" onClick={detectGeo} disabled={geo} title="Use my location">
          <Navigation size={15} />
        </button>
        <button className="loc-confirm-btn"
          disabled={!city.trim() || loading}
          onClick={() => onConfirm(city.trim())}>
          {loading ? <RefreshCw size={14} className="spin" /> : <ChevronRight size={14} />}
          Search
        </button>
      </div>
      {geoErr && <p className="loc-error">{geoErr}</p>}
      <p className="loc-hint">Available cities: Vijayawada · Hyderabad · Chennai · Bangalore</p>
    </div>
  );
}
