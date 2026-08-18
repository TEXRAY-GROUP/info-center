/** 自繪 SVG 圖表(無外部套件) */

const NS = 'http://www.w3.org/2000/svg';

function el(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

/** 依資料算出「好看」的 y 軸上下界(上下各留 8% 邊距) */
function bounds(values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [min * 0.995, max * 1.005];
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

/**
 * 迷你走勢線(卡片用,無座標軸)
 * @param {Array<[string, number]>} points
 */
export function sparkline(points, { width = 160, height = 30 } = {}) {
  const svg = el('svg', {
    viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: 'none',
    role: 'img',
    'aria-hidden': 'true',
  });
  if (points.length < 2) return svg;

  const vals = points.map((p) => p[1]);
  const [lo, hi] = bounds(vals);
  const x = (i) => (i / (points.length - 1)) * width;
  const y = (v) => height - ((v - lo) / (hi - lo)) * height;

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
  svg.append(
    el('path', {
      d: `${line}L${width},${height}L0,${height}Z`,
      fill: 'var(--chart-fill)',
      stroke: 'none',
    }),
    el('path', {
      d: line,
      fill: 'none',
      stroke: 'var(--chart-line)',
      'stroke-width': 1.6,
      'stroke-linejoin': 'round',
      'vector-effect': 'non-scaling-stroke',
    }),
  );
  return svg;
}

/**
 * 主走勢圖(含座標軸與 hover 提示)
 * @param {HTMLElement} box      容器(需 position:relative)
 * @param {Array<[string, number]>} points
 * @param {{formatValue?:Function, label?:string}} opts
 */
export function lineChart(box, points, { formatValue = (v) => v, formatX = (d) => d, label = '' } = {}) {
  box.textContent = '';
  if (points.length < 2) {
    box.textContent = '資料點不足,無法繪製走勢。';
    return;
  }

  // viewBox 內的長度單位會隨容器寬度縮放,所以字級、留白、線寬都要先乘上縮放倍率,
  // 才能在任何寬度下都渲染成固定的實際像素(字約 11px)。
  const W = 720;
  const cw = box.clientWidth || W;
  const k = W / cw;                                   // viewBox 單位 / 實際像素
  const FS = 11 * k;                                  // 座標軸字級
  const targetPx = Math.max(170, Math.min(300, cw * 0.45));
  const H = targetPx * k;
  const PAD = { top: FS * 1.3, right: FS * 4.4 + 8 * k, bottom: FS * 2.3, left: 6 * k };
  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;

  const vals = points.map((p) => p[1]);
  const [lo, hi] = bounds(vals);
  const x = (i) => PAD.left + (i / (points.length - 1)) * iw;
  const y = (v) => PAD.top + ih - ((v - lo) / (hi - lo)) * ih;

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  svg.setAttribute('aria-label', `${label}走勢圖`);

  // 水平格線 + y 軸標籤(右側)
  for (let i = 0; i <= 4; i++) {
    const v = lo + ((hi - lo) * i) / 4;
    const yy = y(v);
    svg.append(
      el('line', {
        x1: PAD.left, x2: PAD.left + iw, y1: yy, y2: yy,
        stroke: 'var(--border)', 'stroke-width': k,
        'stroke-dasharray': i === 0 ? '' : `${3 * k} ${4 * k}`,
      }),
    );
    const t = el('text', {
      x: PAD.left + iw + 6 * k, y: yy + FS * 0.36,
      fill: 'var(--text-dim)', 'font-size': FS.toFixed(1),
    });
    t.textContent = formatValue(v);
    svg.append(t);
  }

  // 面積 + 折線
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${y(p[1]).toFixed(2)}`).join('');
  svg.append(
    el('path', {
      d: `${line}L${x(points.length - 1)},${PAD.top + ih}L${PAD.left},${PAD.top + ih}Z`,
      fill: 'var(--chart-fill)', stroke: 'none',
    }),
    el('path', {
      d: line, fill: 'none', stroke: 'var(--chart-line)',
      'stroke-width': 2 * k, 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
    }),
  );

  // x 軸日期(頭 / 中 / 尾)
  [0, Math.floor((points.length - 1) / 2), points.length - 1].forEach((i, n) => {
    const t = el('text', {
      x: x(i), y: H - FS * 0.7, fill: 'var(--text-dim)', 'font-size': FS.toFixed(1),
      'text-anchor': n === 0 ? 'start' : n === 1 ? 'middle' : 'end',
    });
    t.textContent = formatX(points[i][0]);
    svg.append(t);
  });

  // hover:十字線 + 圓點
  const hoverLine = el('line', {
    y1: PAD.top, y2: PAD.top + ih, stroke: 'var(--c-amber)',
    'stroke-width': k, 'stroke-dasharray': `${3 * k} ${3 * k}`, opacity: 0,
  });
  const dot = el('circle', {
    r: 4.5 * k, fill: 'var(--c-amber)', stroke: 'var(--surface)', 'stroke-width': 2 * k, opacity: 0,
  });
  svg.append(hoverLine, dot);
  box.append(svg);

  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  box.append(tip);

  function locate(clientX) {
    const rect = svg.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;          // 0~1
    const px = ratio * W;                                       // 換回 viewBox 座標
    const i = Math.round(((px - PAD.left) / iw) * (points.length - 1));
    return Math.max(0, Math.min(points.length - 1, i));
  }

  function show(ev) {
    const i = locate(ev.clientX ?? ev.touches?.[0]?.clientX);
    const [date, val] = points[i];
    hoverLine.setAttribute('x1', x(i));
    hoverLine.setAttribute('x2', x(i));
    hoverLine.setAttribute('opacity', 1);
    dot.setAttribute('cx', x(i));
    dot.setAttribute('cy', y(val));
    dot.setAttribute('opacity', 1);
    tip.textContent = `${date} · ${formatValue(val)}`;
    tip.style.left = `${(x(i) / W) * 100}%`;
    tip.style.top = `${(y(val) / H) * 100}%`;
    tip.style.opacity = 1;
  }

  function hide() {
    hoverLine.setAttribute('opacity', 0);
    dot.setAttribute('opacity', 0);
    tip.style.opacity = 0;
  }

  svg.addEventListener('mousemove', show);
  svg.addEventListener('mouseleave', hide);
  svg.addEventListener('touchstart', show, { passive: true });
  svg.addEventListener('touchmove', show, { passive: true });
  svg.addEventListener('touchend', hide);
}
