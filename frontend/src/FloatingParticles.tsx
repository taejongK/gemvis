import { useMemo } from 'react';

type Particle = {
  left: number;       // vw
  top: number;        // vh
  size: number;       // px
  hue: 'cyan' | 'soft' | 'white';
  driftDur: number;   // s
  driftDelay: number; // s
  twinkleDur: number; // s
};

const COUNT = 80;

const rand = (min: number, max: number) => min + Math.random() * (max - min);

function makeParticles(): Particle[] {
  return Array.from({ length: COUNT }, () => {
    const r = Math.random();
    const hue: Particle['hue'] = r < 0.55 ? 'cyan' : r < 0.85 ? 'soft' : 'white';
    return {
      left: rand(0, 100),
      top: rand(0, 100),
      size: rand(1, 2.6),
      hue,
      driftDur: rand(50, 110),
      driftDelay: rand(-110, 0),
      twinkleDur: rand(3, 8),
    };
  });
}

export default function FloatingParticles() {
  const particles = useMemo(makeParticles, []);
  return (
    <div className="particles-layer" aria-hidden="true">
      {particles.map((p, i) => (
        <span
          key={i}
          className={`particle particle-${p.hue}`}
          style={{
            left: `${p.left}vw`,
            top: `${p.top}vh`,
            width: `${p.size}px`,
            height: `${p.size}px`,
            animationDuration: `${p.driftDur}s, ${p.twinkleDur}s`,
            animationDelay: `${p.driftDelay}s, ${-rand(0, p.twinkleDur)}s`,
          }}
        />
      ))}
    </div>
  );
}
