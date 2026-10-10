import React, { useState, useRef, useEffect } from 'react';

export function useTypewriter(text, { speed = 38, onDone } = {}) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone]           = useState(false);
  const rafRef                    = useRef(null);
  const indexRef                  = useRef(0);

  useEffect(() => {
    setDisplayed('');
    setDone(false);
    indexRef.current = 0;

    if (!text) { setDone(true); return; }

    const words = text.split(' ');

    function tick() {
      if (indexRef.current >= words.length) {
        setDone(true);
        onDone?.();
        return;
      }
      setDisplayed(words.slice(0, indexRef.current + 1).join(' '));
      indexRef.current += 1;

      const delay = speed + Math.random() * 18 - 9;
      rafRef.current = setTimeout(tick, delay);
    }

    rafRef.current = setTimeout(tick, speed);
    return () => clearTimeout(rafRef.current);
  }, [text]);

  return { displayed, done };
}

export function TypewriterBubble({ text, onDone, instant = false }) {
  const { displayed, done } = useTypewriter(instant ? '' : text, { onDone });
  const content = instant ? text : displayed;

  return (
    <div className="msg-bubble assistant">
      {content}
      {!done && !instant && <span className="typing-cursor">▋</span>}
    </div>
  );
}
