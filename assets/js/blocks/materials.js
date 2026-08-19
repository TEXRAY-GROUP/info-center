/**
 * 積木:原物料價格
 *
 * 期貨收盤價,非實際採購報價。
 * 聚酯鏈與棉花另附「台幣/公斤」參考值(用站上現成的匯率換算);
 * 原油與天然氣不換算——美元/桶換成台幣/公斤沒有意義。
 */
import { fmtStampShort } from '../lib/format.js';
import { sparkline, lineChart } from '../lib/chart.js';

const RANGES = [
  { key: 30, label: '近 30 天' },
  { key: 90, label: '近 3 個月' },
  { key: 365, label: '近 1 年' },
];
const LB_PER_KG = 0.45359237;

const num = (v, d = 2) =>
  v.toLocaleString('zh-TW', { minimumFractionDigits: d, maximumFractionDigits: d });

/** 依數值大小決定小數位:原油 91.6、天然氣 2.79、PTA 5,958 */
function fmtPrice(v) {
  const a = Math.abs(v);
  return num(v, a >= 1000 ? 0 : a >= 10 ? 2 : 3);
}

/** 期貨價 → 台幣/公斤。拿不到匯率就回 null(不猜) */
function toTwdPerKg(item, fx) {
  if (item.convert === 'cny_per_ton' && fx.CNY) return item.price / 1000 * fx.CNY;
  if (item.convert === 'usc_per_lb' && fx.USD) return item.price / 100 / LB_PER_KG * fx.USD;
  return null;
}

/** 從 rates.json 取即期中價;沒有即期就退回主要顯示價 */
function spotMid(c) {
  if (c.spot_buy && c.spot_sell) return (c.spot_buy + c.spot_sell) / 2;
  return c.primary ?? null;
}

export default {
  render(root, data) {
    const groupLabel = Object.fromEntries(data.groups.map((g) => [g.id, g.label]));
    const state = { id: data.items[0]?.id, range: 90, fx: {} };
    const byId = Object.fromEntries(data.items.map((i) => [i.id, i]));

    root.innerHTML = `
      ${data.failed?.length
        ? `<div class="note">有 ${data.failed.length} 項來源暫時取不到:${data.failed.join('、')}</div>`
        : ''}
      <div id="mat-groups"></div>
      <div class="rate-detail">
        <div>
          <div class="detail-head">
            <h3 id="mat-title"></h3>
            <div class="range-tabs" id="mat-ranges"></div>
          </div>
          <div class="chart-box" id="mat-chart"></div>
          <div class="mat-info" id="mat-info"></div>
        </div>
        <div class="mat-side" id="mat-side"></div>
      </div>
      <p class="note">${data.note}</p>
    `;

    // ---------- 分組卡片 ----------
    const groupsBox = root.querySelector('#mat-groups');
    data.groups.forEach((g) => {
      const items = data.items.filter((i) => i.group === g.id);
      if (!items.length) return;
      const sec = document.createElement('div');
      sec.className = 'mat-group';
      sec.innerHTML = `<h4>${g.label}</h4><div class="mat-grid"></div>`;
      const grid = sec.querySelector('.mat-grid');
      items.forEach((it) => {
        const cls = it.change > 0 ? 'up' : it.change < 0 ? 'down' : 'flat';
        const sign = it.change > 0 ? '▲' : it.change < 0 ? '▼' : '－';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mat-card';
        btn.dataset.id = it.id;
        btn.innerHTML = `
          <div class="mat-name">${it.name}</div>
          <div class="mat-price">${fmtPrice(it.price)}</div>
          <div class="mat-unit">${it.unit}</div>
          <div class="mat-twd" data-twd="${it.id}"></div>
          <div class="mat-change ${cls}">${sign} ${fmtPrice(Math.abs(it.change))}
            (${it.change_pct > 0 ? '+' : ''}${it.change_pct?.toFixed(2)}%)</div>
          <div class="mat-spark"></div>
        `;
        btn.querySelector('.mat-spark').append(sparkline(it.history.slice(-90)));
        btn.onclick = () => { state.id = it.id; paint(); };
        grid.append(btn);
      });
      groupsBox.append(sec);
    });

    // ---------- 期間切換 ----------
    const ranges = root.querySelector('#mat-ranges');
    RANGES.forEach((r) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = r.label;
      b.dataset.range = r.key;
      b.onclick = () => { state.range = r.key; paint(); };
      ranges.append(b);
    });

    // ---------- 匯率(換算用,與本站匯率積木同一份資料)----------
    fetch(`data/rates.json?v=${Date.now()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('rates'))))
      .then((rates) => {
        rates.currencies.forEach((c) => { state.fx[c.code] = spotMid(c); });
        state.fxDate = rates.data_date;
        paint();
      })
      .catch(() => paint());

    function paint() {
      const it = byId[state.id];
      root.querySelectorAll('.mat-card').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.id === state.id)));
      ranges.querySelectorAll('button').forEach((b) =>
        b.setAttribute('aria-pressed', String(Number(b.dataset.range) === state.range)));

      // 卡片上的台幣換算
      data.items.forEach((x) => {
        const el = root.querySelector(`[data-twd="${x.id}"]`);
        if (!el) return;
        const twd = toTwdPerKg(x, state.fx);
        el.textContent = twd === null ? '' : `≈ NT$ ${num(twd, 1)} /公斤`;
      });

      if (!it) return;
      root.querySelector('#mat-title').textContent = `${it.name} · 收盤價走勢`;
      lineChart(root.querySelector('#mat-chart'), it.history.slice(-state.range), {
        formatValue: fmtPrice,
        formatX: (d) => (state.range >= 365 ? d.slice(0, 7) : d.slice(5)),
        label: it.name,
      });
      root.querySelector('#mat-info').innerHTML =
        `<b>${it.name}</b>(${it.symbol})· ${it.note}<br>
         資料日期 ${it.date} · 來源:${it.source}`;

      const twd = toTwdPerKg(it, state.fx);
      root.querySelector('#mat-side').innerHTML = `
        <div class="mat-big">
          <div class="mat-big-label">${groupLabel[it.group]} · ${it.name}</div>
          <div class="mat-big-price">${fmtPrice(it.price)}<small> ${it.unit}</small></div>
          ${twd === null
            ? `<div class="mat-note-small">此品項不做台幣換算(單位性質不同,換算沒有意義)</div>`
            : `<div class="mat-big-twd">≈ NT$ ${num(twd, 1)} /公斤</div>
               <div class="mat-note-small">
                 以${state.fxDate ? ` ${state.fxDate} ` : ''}台銀即期中價換算,
                 <b>為期貨價格換算值,不等於採購報價</b>
               </div>`}
        </div>
        <table class="price-table">
          <tbody>
            <tr><th>前一交易日</th><td>${fmtPrice(it.prev)}</td></tr>
            <tr><th>漲跌</th><td class="${it.change > 0 ? 'up' : it.change < 0 ? 'down' : ''}">
              ${it.change > 0 ? '+' : ''}${fmtPrice(it.change)}</td></tr>
            <tr><th>漲跌幅</th><td class="${it.change > 0 ? 'up' : it.change < 0 ? 'down' : ''}">
              ${it.change_pct > 0 ? '+' : ''}${it.change_pct?.toFixed(2)}%</td></tr>
            <tr><th>資料日期</th><td>${it.date}</td></tr>
          </tbody>
        </table>`;
    }

    // 視窗寬度變了要重繪圖表(字級依容器寬度換算)
    const box = root.querySelector('#mat-chart');
    let lastW = box.clientWidth;
    let timer;
    window.addEventListener('resize', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (Math.abs(box.clientWidth - lastW) > 16) { lastW = box.clientWidth; paint(); }
      }, 150);
    });

    paint();
  },

  meta(data) {
    const days = [...new Set(data.items.map((i) => i.date))].sort();
    return `${data.items.length} 項 · 資料日期 ${days[0]}${days.length > 1 ? `~${days.at(-1)}` : ''}
      · 最後檢查 ${fmtStampShort(data.fetched_at)}`;
  },
};
