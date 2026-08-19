/** 積木:匯率(臺灣銀行牌告) */
import { fmtRate, fmtMoney, fmtChange, fmtDateShort, fmtStampShort } from '../lib/format.js';
import { sparkline, lineChart } from '../lib/chart.js';

const RANGES = [
  { key: 30, label: '近 30 天' },
  { key: 90, label: '近 3 個月' },
  { key: 365, label: '近 1 年' },
];

const FIELDS = [
  ['cash_buy', '現金買入'],
  ['cash_sell', '現金賣出'],
  ['spot_buy', '即期買入'],
  ['spot_sell', '即期賣出'],
];

export default {
  render(root, data) {
    const state = {
      code: data.currencies[0].code,
      toCode: data.currencies[1].code,   // 外幣→外幣 的目標幣別
      range: 90,
      // fx2twd:外幣→台幣(銀行買入) / twd2fx:台幣→外幣(銀行賣出) / fx2fx:外幣→外幣(經台幣兩段)
      dir: 'fx2twd',
      kind: 'cash',                      // cash / spot
      amount: 1000,
    };
    const byCode = Object.fromEntries(data.currencies.map((c) => [c.code, c]));
    const cur = () => byCode[state.code];
    const nextCode = (code) => {
      const i = data.currencies.findIndex((c) => c.code === code);
      return data.currencies[(i + 1) % data.currencies.length].code;
    };

    /**
     * 取某幣別在某側的牌價。選定的牌價別沒掛牌時退回另一種,並回報 fallback。
     * side: 'buy' = 銀行向你買外幣 / 'sell' = 銀行賣外幣給你
     */
    const pick = (c, side, kind) => {
      const primary = `${kind}_${side}`;
      if (c[primary] !== null && c[primary] !== undefined) {
        return { rate: c[primary], field: primary, fallback: false };
      }
      const alt = `${kind === 'cash' ? 'spot' : 'cash'}_${side}`;
      if (c[alt] !== null && c[alt] !== undefined) {
        return { rate: c[alt], field: alt, fallback: true };
      }
      return null;
    };
    const fieldLabel = (f) => FIELDS.find(([k]) => k === f)?.[1] ?? f;

    root.innerHTML = `
      <div class="rate-grid" id="rate-grid"></div>
      <div class="rate-detail">
        <div>
          <div class="detail-head">
            <h3 id="detail-title"></h3>
            <div class="range-tabs" id="range-tabs"></div>
          </div>
          <div class="chart-box" id="chart-box"></div>
          <table class="price-table" id="price-table"></table>
        </div>
        <div class="converter" id="converter"></div>
      </div>
      <p class="note">
        ${data.primary_note}
        牌價含銀行買賣價差,僅供參考;實際換匯以往來銀行成交價為準。
      </p>
    `;

    // ---------- 幣別卡 ----------
    const grid = root.querySelector('#rate-grid');
    data.currencies.forEach((c) => {
      const chg = fmtChange(c.change, c.change_pct, c.primary);
      const isFallback = c.primary_field !== 'cash_sell';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'rate-card';
      btn.dataset.code = c.code;
      btn.innerHTML = `
        <span class="rc-top">
          <span class="rc-code">${c.code}</span>
          <span class="rc-name">${c.name}</span>
        </span>
        <div class="rc-value">${fmtRate(c.primary)}</div>
        <div class="rc-label">${c.primary_label}${isFallback ? '<span class="tag" title="臺灣銀行未掛此幣別現金牌價">無現金價</span>' : ''}</div>
        <div class="rc-change ${chg.cls}">${chg.text}</div>
        <div class="rc-spark"></div>
      `;
      btn.querySelector('.rc-spark').append(sparkline(c.history.slice(-90)));
      btn.addEventListener('click', () => {
        state.code = c.code;
        if (state.dir === 'fx2fx' && state.toCode === c.code) {
          state.toCode = nextCode(c.code);
        }
        paint();                 // 牌價別維持使用者的選擇,缺的由 pick() 自動退回
      });
      grid.append(btn);
    });

    // ---------- 期間切換 ----------
    const tabs = root.querySelector('#range-tabs');
    RANGES.forEach((r) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = r.label;
      b.dataset.range = r.key;
      b.addEventListener('click', () => {
        state.range = r.key;
        paint();
      });
      tabs.append(b);
    });

    // ---------- 換算工具 ----------
    const conv = root.querySelector('#converter');
    const options = data.currencies
      .map((c) => `<option value="${c.code}">${c.code} ${c.name}</option>`)
      .join('');
    conv.innerHTML = `
      <h3>匯率換算</h3>
      <div class="field">
        <label>換算方向</label>
        <div class="seg seg-3" id="cv-dir">
          <button type="button" data-dir="fx2twd">外幣→台幣</button>
          <button type="button" data-dir="twd2fx">台幣→外幣</button>
          <button type="button" data-dir="fx2fx">外幣→外幣</button>
        </div>
      </div>
      <div class="field">
        <label for="cv-code" id="cv-pair-label">幣別</label>
        <div class="pair">
          <select id="cv-code">${options}</select>
          <button type="button" class="swap" id="cv-swap" title="對調" aria-label="對調幣別" hidden>⇄</button>
          <select id="cv-code2" aria-label="換成的幣別" hidden>${options}</select>
        </div>
      </div>
      <div class="field">
        <label>使用牌價</label>
        <div class="seg" id="cv-kind">
          <button type="button" data-kind="cash">現金</button>
          <button type="button" data-kind="spot">即期</button>
        </div>
      </div>
      <div class="field">
        <label for="cv-amount" id="cv-amount-label">金額</label>
        <input id="cv-amount" type="number" min="0" step="any" value="${state.amount}" inputmode="decimal">
      </div>
      <div class="conv-result">
        <div class="cr-value" id="cv-out">—</div>
        <div class="cr-why" id="cv-why"></div>
      </div>
    `;
    const $code = conv.querySelector('#cv-code');
    const $code2 = conv.querySelector('#cv-code2');
    const $amount = conv.querySelector('#cv-amount');
    $code2.value = state.toCode;

    $code.addEventListener('change', () => {
      state.code = $code.value;
      if (state.dir === 'fx2fx' && state.toCode === state.code) {
        state.toCode = nextCode(state.code);          // 兩邊同幣別沒有意義,自動挪開
      }
      paint();
    });
    $code2.addEventListener('change', () => {
      state.toCode = $code2.value;
      if (state.toCode === state.code) {
        state.code = nextCode(state.toCode);
      }
      paint();
    });
    conv.querySelector('#cv-swap').addEventListener('click', () => {
      [state.code, state.toCode] = [state.toCode, state.code];
      paint();
    });
    conv.querySelector('#cv-dir').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-dir]');
      if (!b) return;
      state.dir = b.dataset.dir;
      paint();
    });
    conv.querySelector('#cv-kind').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-kind]');
      if (!b || b.disabled) return;
      state.kind = b.dataset.kind;
      paint();
    });
    $amount.addEventListener('input', () => {
      state.amount = parseFloat($amount.value);
      paintConverter();
    });

    // ---------- 繪製 ----------
    function paint() {
      const c = cur();

      grid.querySelectorAll('.rate-card').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.code === state.code));
      });
      tabs.querySelectorAll('button').forEach((b) => {
        b.setAttribute('aria-pressed', String(Number(b.dataset.range) === state.range));
      });

      root.querySelector('#detail-title').textContent =
        `${c.name} ${c.code} · ${c.primary_label}走勢`;

      const pts = c.history.slice(-state.range);
      lineChart(root.querySelector('#chart-box'), pts, {
        formatValue: (v) => fmtRate(v, c.primary),
        // 一年期跨年,軸標籤顯示到「年-月」;短期只顯示「月-日」
        formatX: (d) => (state.range >= 365 ? d.slice(0, 7) : d.slice(5)),
        label: `${c.name}${c.primary_label}`,
      });

      root.querySelector('#price-table').innerHTML = `
        <tbody>
          ${FIELDS.map(([f, label]) => `
            <tr>
              <th>${label}</th>
              <td class="${c[f] === null ? 'na' : ''}">${c[f] === null ? '— 未掛牌' : fmtRate(c[f])}</td>
            </tr>`).join('')}
        </tbody>
      `;

      if ($code.value !== state.code) $code.value = state.code;
      paintConverter();
    }

    function paintConverter() {
      const isPair = state.dir === 'fx2fx';
      const from = cur();
      const to = byCode[state.toCode];
      const legs = isPair ? [from, to] : [from];

      // 牌價別:任一邊掛得出這種價就可選(個別缺的那一邊由 pick() 自動退回另一種)
      conv.querySelectorAll('#cv-kind button').forEach((b) => {
        const k = b.dataset.kind;
        const ok = legs.some((c) => c[`${k}_buy`] !== null || c[`${k}_sell`] !== null);
        b.disabled = !ok;
        b.title = ok ? '' : `台銀未掛${k === 'cash' ? '現金' : '即期'}牌價`;
        b.setAttribute('aria-pressed', String(k === state.kind && ok));
      });
      conv.querySelectorAll('#cv-dir button').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.dir === state.dir));
      });

      // 外幣→外幣 才需要第二個下拉與對調鈕
      conv.querySelector('#cv-code2').hidden = !isPair;
      conv.querySelector('#cv-swap').hidden = !isPair;
      conv.querySelector('#cv-pair-label').textContent = isPair ? '從 → 換成' : '幣別';
      if (conv.querySelector('#cv-code2').value !== state.toCode) {
        conv.querySelector('#cv-code2').value = state.toCode;
      }
      conv.querySelector('#cv-amount-label').textContent =
        state.dir === 'twd2fx' ? '金額(TWD)' : `金額(${from.code})`;

      const out = conv.querySelector('#cv-out');
      const why = conv.querySelector('#cv-why');
      const amt = state.amount;
      const digitsOf = (code) => (code === 'VND' ? 0 : 2);

      if (!Number.isFinite(amt) || amt < 0) {
        out.textContent = '—';
        why.textContent = '請輸入金額。';
        return;
      }

      const note = (leg, c) =>
        leg.fallback ? `(${c.name}無${state.kind === 'cash' ? '現金' : '即期'}牌價,改用${fieldLabel(leg.field)})` : '';

      if (state.dir === 'fx2twd') {
        const leg = pick(from, 'buy', state.kind);
        if (!leg) return fail(out, why, from);
        out.textContent = `NT$ ${fmtMoney(amt * leg.rate)}`;
        why.textContent =
          `${fmtMoney(amt, 2)} ${from.code} × ${fmtRate(leg.rate)}` +
          `(${fieldLabel(leg.field)},銀行向你買外幣的價格)${note(leg, from)}`;
        return;
      }

      if (state.dir === 'twd2fx') {
        const leg = pick(from, 'sell', state.kind);
        if (!leg) return fail(out, why, from);
        out.textContent = `${fmtMoney(amt / leg.rate, digitsOf(from.code))} ${from.code}`;
        why.textContent =
          `NT$ ${fmtMoney(amt, 2)} ÷ ${fmtRate(leg.rate)}` +
          `(${fieldLabel(leg.field)},銀行賣外幣給你的價格)${note(leg, from)}`;
        return;
      }

      // 外幣 → 外幣:台銀沒有直接的交叉牌價,實務走「賣掉A換台幣 → 台幣買B」,兩段都吃價差
      const legA = pick(from, 'buy', state.kind);
      const legB = pick(to, 'sell', state.kind);
      if (!legA) return fail(out, why, from);
      if (!legB) return fail(out, why, to);

      const twd = amt * legA.rate;
      const result = twd / legB.rate;
      const cross = legA.rate / legB.rate;

      out.textContent = `${fmtMoney(result, digitsOf(to.code))} ${to.code}`;
      why.innerHTML =
        `${fmtMoney(amt, 2)} ${from.code} × ${fmtRate(legA.rate)}(${from.name}${fieldLabel(legA.field)})` +
        ` = NT$ ${fmtMoney(twd)}${note(legA, from)}<br>` +
        `NT$ ${fmtMoney(twd)} ÷ ${fmtRate(legB.rate)}(${to.name}${fieldLabel(legB.field)})` +
        ` = ${fmtMoney(result, digitsOf(to.code))} ${to.code}${note(legB, to)}<br>` +
        `<b>換算後 1 ${from.code} ≈ ${cross >= 1000 ? fmtMoney(cross) : fmtRate(cross, cross)} ${to.code}</b><br>` +
        `台銀無直接交叉牌價,此為經台幣兩段換匯的結果(含兩次買賣價差)。`;
    }

    function fail(out, why, c) {
      out.textContent = '—';
      why.textContent = `台銀未掛 ${c.name} 的相關牌價,此組合無法換算。`;
    }

    paint();

    // 圖表的字級/留白依容器實際寬度換算,寬度變了(手機轉向、桌機縮放)就重繪。
    // 回傳清理函式:改成可切換頁面後,不解除的話每進來一次就疊一個監聽器。
    const chartBox = root.querySelector('#chart-box');
    let lastWidth = chartBox.clientWidth;
    let timer;
    const onResize = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (Math.abs(chartBox.clientWidth - lastWidth) > 16) {
          lastWidth = chartBox.clientWidth;
          paint();
        }
      }, 150);
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      clearTimeout(timer);
    };
  },

  /**
   * 區塊右上角的資料狀態說明。
   * 「牌告日期」是台銀發布這份匯率的日期,「最後檢查」是我們去抓的時間——
   * 台銀當日牌告傍晚才發布,早上抓到的必然是前一日,兩個時間分開顯示
   * 才不會讓人誤以為系統沒在跑。
   */
  meta(data) {
    return `牌告日期 ${fmtDateShort(data.data_date)} ·
      最後檢查 ${fmtStampShort(data.fetched_at)} ·
      <a href="${data.source_url}" target="_blank" rel="noopener">臺灣銀行</a>`;
  },
};
