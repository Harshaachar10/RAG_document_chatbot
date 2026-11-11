import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TOUR_STEPS } from '../config/demoTour';

export function Presenter({ active, onEnd }: { active: boolean; onEnd: () => void }) {
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const [box, setBox] = useState<{ top: number; left: number; width: number; height: number } | null>(null);
  const [skipped, setSkipped] = useState<number[]>([]);

  useEffect(() => {
    if (!active) return;
    const step = TOUR_STEPS[index];
    if (!step) {
      onEnd();
      return;
    }
    navigate(step.route);
    let cancelled = false;
    const place = () => {
      if (cancelled) return;
      if (step.rowText) {
        const row = [...document.querySelectorAll('tr, button, a')].find((el) => (el.textContent || '').includes(step.rowText || ''));
        if (row instanceof HTMLElement) row.click();
      }
      if (step.clickTour) {
        const toggle = document.querySelector(`[data-tour="${step.clickTour}"]`);
        if (toggle instanceof HTMLElement) toggle.click();
      }
      const target = document.querySelector(`[data-tour="${step.target}"]`);
      if (!(target instanceof HTMLElement)) {
        setBox(null);
        return;
      }
      const rect = target.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) {
        setBox(null);
        return;
      }
      setBox({ top: rect.top, left: rect.left, width: rect.width, height: rect.height });
    };
    const timers = [80, 350, 900].map((ms) => window.setTimeout(place, ms));
    const giveUp = window.setTimeout(() => {
      if (cancelled) return;
      const target = document.querySelector(`[data-tour="${step.target}"]`);
      if (!(target instanceof HTMLElement)) {
        setSkipped((current) => [...current, index]);
        setIndex((current) => current + 1);
      }
    }, 1200);
    return () => {
      cancelled = true;
      timers.forEach((id) => window.clearTimeout(id));
      window.clearTimeout(giveUp);
    };
  }, [active, index, navigate, onEnd]);

  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onEnd();
      if (event.key === 'ArrowRight') setIndex((current) => Math.min(TOUR_STEPS.length - 1, current + 1));
      if (event.key === 'ArrowLeft') setIndex((current) => Math.max(0, current - 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, onEnd]);

  if (!active || index >= TOUR_STEPS.length) return null;
  const step = TOUR_STEPS[index];
  const calloutTop = box ? Math.min(window.innerHeight - 220, box.top + box.height + 12) : 120;
  const calloutLeft = box ? Math.min(window.innerWidth - 400, Math.max(16, box.left)) : 24;
  return (
    <>
      {box ? (
        <div
          className="spot"
          style={{ top: box.top - 6, left: box.left - 6, width: box.width + 12, height: box.height + 12 }}
        />
      ) : null}
      <div className="callout" role="dialog" aria-label={`Demo step ${index + 1}`} style={{ top: calloutTop, left: calloutLeft }}>
        <span className="k">
          Step {index + 1} of {TOUR_STEPS.length}
          {skipped.includes(index) ? '' : ` · ${step.kicker}`}
        </span>
        <h3>{step.title}</h3>
        <p>{step.text}</p>
        <div className="row">
          <span className="dots">
            {TOUR_STEPS.map((item, dot) => (
              <i key={item.kicker + dot} className={dot === index ? 'on' : ''} />
            ))}
          </span>
          {index > 0 ? (
            <button type="button" className="btn sm" onClick={() => setIndex((current) => current - 1)}>
              Back
            </button>
          ) : null}
          <button
            type="button"
            className="btn sm primary"
            onClick={() => {
              if (index >= TOUR_STEPS.length - 1) onEnd();
              else setIndex((current) => current + 1);
            }}
          >
            {index >= TOUR_STEPS.length - 1 ? 'End' : 'Next'}
          </button>
          <button type="button" className="iconbtn" aria-label="End demo" onClick={onEnd}>
            ×
          </button>
        </div>
      </div>
    </>
  );
}
