// Shared pressure colour scale. Values are counts of 0.1 mmHg.
// Colour position is sqrt(mmHg / 100), so low pressures stay distinguishable;
// everything at or above 100 mmHg (the CNN's input cap) takes the top colour.
const Heat = (() => {
  const STOPS = [
    [0.0, [77, 38, 110]], // logwood
    [0.25, [155, 37, 87]], // cochineal
    [0.5, [210, 83, 58]], // madder
    [0.75, [240, 163, 58]], // saffron
    [1.0, [251, 239, 196]], // straw
  ];
  const TICKS = [1, 10, 25, 50, 100];
  const pos = (mmhg) => Math.min(1, Math.sqrt(Math.max(0, mmhg) / 100));
  function rgb(mmhg) {
    const t = pos(mmhg);
    for (let i = 1; i < STOPS.length; i++) {
      if (t <= STOPS[i][0]) {
        const [t0, a] = STOPS[i - 1];
        const [t1, b] = STOPS[i];
        const f = (t - t0) / (t1 - t0);
        return a.map((v, k) => Math.round(v + (b[k] - v) * f));
      }
    }
    return STOPS[STOPS.length - 1][1];
  }
  const LUT = Array.from({ length: 4096 }, (_, c) => rgb(c / 10));

  // Draw a 32 x 64 frame seen from above: head at the top, sensor row 0 on
  // the right-hand edge (the PmatData orientation used by the CNN).
  function draw(canvas, values) {
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(32, 64);
    for (let row = 0; row < 32; row++) {
      for (let col = 0; col < 64; col++) {
        const v = values ? values[row * 64 + col] : 0;
        const o = (col * 32 + (31 - row)) * 4;
        if (v > 0) {
          const c = LUT[Math.min(4095, v)];
          img.data[o] = c[0];
          img.data[o + 1] = c[1];
          img.data[o + 2] = c[2];
          img.data[o + 3] = 255;
        }
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  function gradientCss() {
    const parts = [];
    for (let i = 0; i <= 20; i++) {
      const mmhg = Math.pow(i / 20, 2) * 100;
      parts.push(`rgb(${rgb(Math.max(mmhg, 0.01)).join(",")}) ${i * 5}%`);
    }
    return `linear-gradient(90deg, ${parts.join(",")})`;
  }

  return { rgb, draw, pos, gradientCss, TICKS };
})();
