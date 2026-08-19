/**
 * 積木:運費試算(DHL vs FedEx 公告價)
 *
 * 只用兩家對外公告的標準價目表,不含公司議定的合約價,所以是「牌價對牌價」的公平比較。
 * 僅提供台灣出口 / 進口;第三地(起訖點皆非台灣)DHL 未公開價目表,不做。
 */
import { fmtStampShort } from '../lib/format.js';

const money = (v) => 'NT$ ' + Math.round(v).toLocaleString('zh-TW');
const HOME = '台灣';

const DHL_TIERS = [
  ['', 'Express Worldwide(標準)'],
  ['12:00', 'Premium 12:00 早安件'],
  ['10:30', 'Premium 10:30 快件'],
  ['9:00', 'Premium 9:00 清晨件'],
];
const FX_SERVICES = [
  ['IPE', 'IPE 國際優先快遞特快(最快)'],
  ['IP', 'IP 國際優先快遞(標準)'],
  ['IE', 'IE 國際經濟快遞(較慢較省)'],
];

/** DHL:30 公斤以內進位到 0.5,30 公斤以上進位到 1;FedEx 一律 0.5 */
function billable(w, carrier) {
  if (carrier === 'DHL' && w > 30) return Math.ceil(w - 1e-9);
  return Math.ceil((w - 1e-9) / 0.5) * 0.5;
}

/* ---------------- DHL 計算 ---------------- */
function quoteDHL(data, { dir, country, weight, kind, tier }) {
  const zone = country.dhl_zone;
  if (!zone) return { error: 'DHL 未公開此國家的分區' };
  const svc = data.dhl.services[dir];
  if (!svc) return { error: '無此情境費率' };

  const bw = billable(weight, 'DHL');
  let base = null;
  let how = '';

  if (kind === 'document' && bw <= 2 && svc.document[String(bw)]) {
    base = svc.document[String(bw)][zone];
    how = '文件費率';
  } else if (bw > 30) {
    const band = svc.per_kg.find((b) => bw >= b.from && bw <= b.to);
    if (!band) return { error: '超出費率表範圍(逾 3,000 公斤)' };
    base = band.rate[zone] * bw;
    how = `每公斤 ${band.rate[zone]} × ${bw} 公斤`;
  } else if (svc.parcel[String(bw)]) {
    base = svc.parcel[String(bw)][zone];
    how = '包裹費率';
  } else {
    // 10 公斤以上價目表只列到整數公斤,零頭用「每 0.5 公斤加收費用」往上加
    const listed = Object.keys(svc.parcel).map(Number).filter((w) => w <= bw).sort((a, b) => a - b);
    const from = listed.at(-1);
    if (from === undefined) return { error: '查無對應費率' };
    const band = svc.extra_per_half_kg
      .filter((e) => bw > e.from).sort((a, b) => a.from - b.from).at(-1)
      || svc.extra_per_half_kg[0];
    const steps = Math.round((bw - from) / 0.5);
    base = svc.parcel[String(from)][zone] + steps * band.rate[zone];
    how = `${from} 公斤費率 + ${steps} × 每 0.5 公斤加收 ${band.rate[zone]}`;
  }
  if (base == null) return { error: '查無對應費率' };

  const rows = [['計費重量', `${bw.toFixed(1)} kg`], ['基本運費', money(base)]];
  let total = base;
  const premium = svc.premium || {};
  if (tier && premium[tier] != null) {
    total += premium[tier];
    rows.push([`Premium ${tier} 加價`, money(premium[tier])]);
  }
  return { zone: `第 ${zone} 區`, base, total, rows, how };
}

/* ---------------- FedEx 計算 ---------------- */
function quoteFedEx(data, { dir, country, weight, kind, service }) {
  const field = (dir === 'export' ? 'exp_' : 'imp_') +
    (service === 'IPE' ? 'IPE' : service === 'IP' ? 'IP' : 'IPF_IE_IEF');
  const zone = country.fedex_zones?.[field];
  if (!zone) return { error: 'FedEx 未公開此國家的分區' };

  const svc = data.fedex.services[dir]?.[service];
  if (!svc) return { error: `FedEx ${dir === 'import' ? '進口' : '出口'}無 ${service} 公告價` };

  const bw = billable(weight, 'FedEx');
  let base = null;
  let how = '';

  if (kind === 'document' && bw <= 0.5 && svc.envelope?.[zone]) {
    base = svc.envelope[zone];
    how = 'FedEx 快遞封(定額)';
  } else if (kind === 'document' && bw <= 2.5 && svc.pak?.[String(bw)]) {
    base = svc.pak[String(bw)][zone];
    how = 'FedEx 快遞袋';
  } else if (svc.parcel?.[String(bw)]) {
    base = svc.parcel[String(bw)][zone];
    how = '包裹費率';
  } else {
    const band = (svc.per_kg || []).find((b) => bw >= b.from && bw <= b.to);
    if (!band) return { error: '超出費率表範圍' };
    base = band.rate[zone] * bw;
    how = `每公斤 ${band.rate[zone]} × ${bw} 公斤`;
  }
  if (base == null) return { error: '查無對應費率' };

  return {
    zone: `分區 ${zone}`, base, total: base, how,
    rows: [['計費重量', `${bw.toFixed(1)} kg`], ['基本運費', money(base)]],
  };
}

/* ---------------- 畫面 ---------------- */
export default {
  render(root, data) {
    const byName = Object.fromEntries(data.countries.map((c) => [c.name, c]));
    const state = {
      origin: HOME, dest: '美國西部', weight: 5,
      kind: 'parcel', tier: '', service: 'IP',
      dhlFuel: 0, fxFuel: 0, fuelLabel: '燃油附加費載入中…',
    };

    const opts = data.countries.map((c) => `<option value="${c.name}">${c.name}</option>`).join('');
    root.innerHTML = `
      <div class="fr-form">
        <div class="field">
          <label for="fr-origin">起運地</label>
          <select id="fr-origin"><option value="${HOME}">${HOME}</option>${opts}</select>
        </div>
        <div class="field">
          <label for="fr-dest">目的地</label>
          <select id="fr-dest"><option value="${HOME}">${HOME}</option>${opts}</select>
        </div>
        <div class="field">
          <label for="fr-weight">重量(公斤)</label>
          <input id="fr-weight" type="number" min="0.1" step="0.5" value="${state.weight}" inputmode="decimal">
        </div>
        <div class="field">
          <label>貨件類型</label>
          <div class="seg" id="fr-kind">
            <button type="button" data-kind="parcel">包裹</button>
            <button type="button" data-kind="document">文件</button>
          </div>
        </div>
        <div class="field">
          <label for="fr-tier">DHL 服務</label>
          <select id="fr-tier">${DHL_TIERS.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}</select>
        </div>
        <div class="field">
          <label for="fr-svc">FedEx 服務</label>
          <select id="fr-svc">${FX_SERVICES.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}</select>
        </div>
      </div>

      <div class="fr-fuel">
        <div class="field">
          <label>DHL 燃油附加費</label>
          <div class="fuel-row">
            <input type="range" id="fr-dhl-fuel" min="0" max="80" step="0.25">
            <span class="fuel-val" id="fr-dhl-fuel-v"></span>
          </div>
        </div>
        <div class="field">
          <label>FedEx 燃油附加費</label>
          <div class="fuel-row">
            <input type="range" id="fr-fx-fuel" min="0" max="80" step="0.25">
            <span class="fuel-val" id="fr-fx-fuel-v"></span>
          </div>
        </div>
      </div>
      <div class="fr-fuel-note" id="fr-fuel-note"></div>

      <div id="fr-result"></div>
      <p class="note">${data.note}<br>${data.scope}</p>
    `;

    const $ = (id) => root.querySelector('#' + id);
    $('fr-origin').value = state.origin;
    $('fr-dest').value = state.dest;
    $('fr-svc').value = state.service;

    // 燃油:讀同一站台的 fuel.json(DHL 自動抓、FedEx 人工維護)
    fetch(`data/fuel.json?v=${Date.now()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
      .then((f) => {
        state.dhlFuel = f.dhl?.percent ?? 0;
        state.fxFuel = f.fedex?.percent ?? 0;
        state.fuelLabel =
          `燃油附加費:DHL ${f.dhl?.label || '—'} · FedEx ${f.fedex?.label || '—'}(FedEx 為人工維護)`;
        syncFuel();
        paint();
      })
      .catch(() => {
        state.fuelLabel = '無法取得燃油附加費,請自行拉動滑桿輸入。';
        syncFuel();
        paint();
      });

    function syncFuel() {
      $('fr-dhl-fuel').value = state.dhlFuel;
      $('fr-fx-fuel').value = state.fxFuel;
      $('fr-dhl-fuel-v').textContent = state.dhlFuel + '%';
      $('fr-fx-fuel-v').textContent = state.fxFuel + '%';
      $('fr-fuel-note').textContent = state.fuelLabel;
    }

    function scenario() {
      const oh = state.origin === HOME;
      const dh = state.dest === HOME;
      if (oh && dh) return 'domestic';
      if (oh) return 'export';
      if (dh) return 'import';
      return 'third';
    }

    function withFuel(q, pct) {
      if (q.error) return q;
      const amt = q.base * pct / 100;
      return {
        ...q,
        total: q.total + amt,
        rows: [...q.rows, [`燃油附加費 (${pct}%)`, money(amt)]],
      };
    }

    function card(name, q, win) {
      if (q.error) {
        return `<div class="fr-card na"><div class="fr-name">${name}</div>
          <div class="fr-msg">${q.error}</div></div>`;
      }
      const isWin = win === name;
      return `<div class="fr-card ${isWin ? 'win' : ''}">
        <div class="fr-name">${name} <span class="fr-zone">${q.zone}</span>
          ${isWin ? '<span class="fr-win">較便宜</span>' : ''}</div>
        <div class="fr-total">${money(q.total)}</div>
        <table class="fr-brk"><tbody>
          ${q.rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('')}
          <tr class="sum"><th>合計估算</th><td>${money(q.total)}</td></tr>
        </tbody></table>
        <div class="fr-how">${q.how}</div>
      </div>`;
    }

    function diff(dhl, fx, win) {
      const gap = Math.abs(dhl.total - fx.total);
      const pct = gap / Math.max(dhl.total, fx.total) * 100;
      return `<div class="fr-diff"><b>${win}</b> 便宜 <b>${money(gap)}</b>(約 ${pct.toFixed(1)}%)</div>`;
    }

    function paint() {
      root.querySelectorAll('#fr-kind button').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.kind === state.kind)));

      const box = $('fr-result');
      const sc = scenario();
      if (sc === 'domestic') {
        box.innerHTML = '<div class="fr-msg">起運地與目的地都是台灣,本試算只處理國際件。</div>';
        return;
      }
      if (sc === 'third') {
        box.innerHTML = `<div class="fr-msg">
          <b>第三地件(起訖點皆非台灣)不提供試算。</b><br>
          DHL 未公開第三地價目表,只列 FedEx 會變成單邊報價、無法比較,這類需求請洽承辦。</div>`;
        return;
      }
      if (!Number.isFinite(state.weight) || state.weight <= 0) {
        box.innerHTML = '<div class="fr-msg">請輸入重量。</div>';
        return;
      }

      const country = byName[sc === 'export' ? state.dest : state.origin];
      const ctx = { dir: sc, country, weight: state.weight, kind: state.kind };
      const dhl = withFuel(quoteDHL(data, { ...ctx, tier: state.tier }), state.dhlFuel);
      const fx = withFuel(quoteFedEx(data, { ...ctx, service: state.service }), state.fxFuel);

      const ok = [dhl, fx].filter((q) => !q.error);
      const win = ok.length === 2 ? (dhl.total <= fx.total ? 'DHL' : 'FedEx') : null;

      box.innerHTML = `
        <div class="fr-route">
          <span class="fr-badge">${sc === 'export' ? '出口(台灣 → 國外)' : '進口(國外 → 台灣)'}</span>
          <b>${state.origin}</b> → <b>${state.dest}</b> ·
          ${state.weight} kg · ${state.kind === 'document' ? '文件' : '包裹'} · 含 5% 營業稅
        </div>
        <div class="fr-cards">${card('DHL', dhl, win)}${card('FedEx', fx, win)}</div>
        ${win ? diff(dhl, fx, win) : ''}
      `;
    }

    $('fr-origin').onchange = (e) => { state.origin = e.target.value; paint(); };
    $('fr-dest').onchange = (e) => { state.dest = e.target.value; paint(); };
    $('fr-weight').oninput = (e) => { state.weight = parseFloat(e.target.value); paint(); };
    $('fr-tier').onchange = (e) => { state.tier = e.target.value; paint(); };
    $('fr-svc').onchange = (e) => { state.service = e.target.value; paint(); };
    $('fr-dhl-fuel').oninput = (e) => { state.dhlFuel = parseFloat(e.target.value); syncFuel(); paint(); };
    $('fr-fx-fuel').oninput = (e) => { state.fxFuel = parseFloat(e.target.value); syncFuel(); paint(); };
    root.querySelectorAll('#fr-kind button').forEach((b) => {
      b.onclick = () => { state.kind = b.dataset.kind; paint(); };
    });

    syncFuel();
    paint();
  },

  meta(data) {
    return `DHL ${data.dhl.effective} · FedEx ${data.fedex.effective} ·
      最後檢查 ${fmtStampShort(data.fetched_at)}`;
  },
};
