/** 積木:紡織產業新聞(Google News 多組關鍵字彙整) */
import { fmtStampShort } from '../lib/format.js';

/** 2026-08-19 09:30 → 今天 09:30 / 昨天 09:30 / 8/17 */
function friendlyDate(s) {
  const [d, t] = s.split(' ');
  const today = new Date();
  const y = new Date(today.getTime() - 86400000);
  const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
  if (d === iso(today)) return `今天 ${t}`;
  if (d === iso(y)) return `昨天 ${t}`;
  const [, m, dd] = d.split('-');
  return `${Number(m)}/${Number(dd)}`;
}

export default {
  render(root, data) {
    const labels = Object.fromEntries(data.categories.map((c) => [c.id, c.label]));
    const state = { cat: 'all', q: '' };

    const counts = Object.fromEntries(
      data.categories.map((c) => [c.id, data.items.filter((i) => i.cats.includes(c.id)).length]));

    root.innerHTML = `
      <div class="news-bar">
        <div class="seg news-cats" id="news-cats">
          <button type="button" data-cat="all">全部 ${data.items.length}</button>
          ${data.categories
            .filter((c) => counts[c.id] > 0)
            .map((c) => `<button type="button" data-cat="${c.id}">${c.label} ${counts[c.id]}</button>`)
            .join('')}
        </div>
        <input id="news-q" type="search" placeholder="搜尋標題或媒體…" autocomplete="off">
      </div>
      <ul class="news-list" id="news-list"></ul>
      <p class="note">
        近 ${data.window_days} 天、共 ${data.items.length} 則。來源:${data.source}。
        以關鍵字自動彙整並過濾,可能仍有遺漏或不相關項目;點標題可前往原始報導。
      </p>
    `;

    const list = root.querySelector('#news-list');
    const $q = root.querySelector('#news-q');

    function paint() {
      root.querySelectorAll('#news-cats button').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.cat === state.cat)));

      const kw = state.q.trim().toLowerCase();
      const shown = data.items.filter((i) => {
        if (state.cat !== 'all' && !i.cats.includes(state.cat)) return false;
        if (!kw) return true;
        return (i.title + ' ' + i.source).toLowerCase().includes(kw);
      });

      if (!shown.length) {
        list.innerHTML = '<li class="news-empty">沒有符合的新聞。</li>';
        return;
      }
      list.innerHTML = shown.map((i) => `
        <li class="news-item">
          <a href="${i.link}" target="_blank" rel="noopener">${i.title}</a>
          <div class="news-meta">
            <span class="news-date">${friendlyDate(i.date)}</span>
            <span class="news-src">${i.source}</span>
            ${i.cats.map((c) => `<span class="news-tag">${labels[c]}</span>`).join('')}
          </div>
        </li>`).join('');
    }

    root.querySelectorAll('#news-cats button').forEach((b) => {
      b.onclick = () => { state.cat = b.dataset.cat; paint(); };
    });
    $q.oninput = () => { state.q = $q.value; paint(); };

    paint();
  },

  meta(data) {
    return `近 ${data.window_days} 天 ${data.items.length} 則 · 最後檢查 ${fmtStampShort(data.fetched_at)}`;
  },
};
