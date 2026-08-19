/**
 * 積木:品牌客戶動態
 *
 * 追蹤國際成衣品牌商的經營面消息(財報、庫存、採購、供應鏈、產能移轉)。
 * 洲別依**品牌總部所在地**固定歸屬,不隨新聞事件發生地變動。
 * 樣式沿用新聞積木的 .news-* 類別。
 */
import { fmtStampShort } from '../lib/format.js';

function friendlyDate(s) {
  const [d, t] = s.split(' ');
  const now = new Date();
  const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
  if (d === iso(now)) return `今天 ${t}`;
  if (d === iso(new Date(now.getTime() - 86400000))) return `昨天 ${t}`;
  const [, m, dd] = d.split('-');
  return `${Number(m)}/${Number(dd)}`;
}

export default {
  render(root, data) {
    const regionLabel = Object.fromEntries(data.regions.map((r) => [r.id, r.label]));
    const state = { region: 'all', lang: 'all', brand: 'all' };

    const count = (rid) => data.items.filter((i) => i.region === rid).length;
    // 只列出實際有新聞的品牌,避免下拉出現一堆空品牌
    const activeBrands = data.brands
      .filter((b) => data.items.some((i) => i.brand === b.id))
      .map((b) => ({ ...b, n: data.items.filter((i) => i.brand === b.id).length }));

    root.innerHTML = `
      <div class="news-bar">
        <div class="seg news-cats" id="br-regions">
          <button type="button" data-region="all">全部 ${data.items.length}</button>
          ${data.regions.filter((r) => count(r.id) > 0)
            .map((r) => `<button type="button" data-region="${r.id}">${r.label} ${count(r.id)}</button>`)
            .join('')}
        </div>
        <select id="br-brand" aria-label="品牌">
          <option value="all">全部品牌</option>
          ${activeBrands.map((b) => `<option value="${b.id}">${b.name}(${b.n})</option>`).join('')}
        </select>
        <div class="seg" id="br-lang">
          <button type="button" data-lang="all">中英</button>
          <button type="button" data-lang="zh">中文</button>
          <button type="button" data-lang="en">英文</button>
        </div>
      </div>
      <ul class="news-list" id="br-list"></ul>
      <p class="note">
        近 ${data.window_days} 天、共 ${data.items.length} 則。來源:${data.source}。
        只收經營面消息(財報、庫存、採購、供應鏈、產能),新品與行銷已濾除。<br>
        ${data.note}
      </p>
    `;

    const list = root.querySelector('#br-list');

    function paint() {
      root.querySelectorAll('#br-regions button').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.region === state.region)));
      root.querySelectorAll('#br-lang button').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.lang === state.lang)));

      const shown = data.items.filter((i) =>
        (state.region === 'all' || i.region === state.region) &&
        (state.lang === 'all' || i.lang === state.lang) &&
        (state.brand === 'all' || i.brand === state.brand));

      if (!shown.length) {
        list.innerHTML = '<li class="news-empty">沒有符合的消息。</li>';
        return;
      }
      list.innerHTML = shown.map((i) => `
        <li class="news-item">
          <a href="${i.link}" target="_blank" rel="noopener">${i.title}</a>
          <div class="news-meta">
            <span class="brand-badge">${i.brand_name}</span>
            <span class="news-tag">${regionLabel[i.region]}</span>
            ${i.lang === 'en' ? '<span class="lang-badge">EN</span>' : ''}
            <span class="news-date">${friendlyDate(i.date)}</span>
            <span class="news-src">${i.source}</span>
          </div>
        </li>`).join('');
    }

    root.querySelectorAll('#br-regions button').forEach((b) => {
      b.onclick = () => { state.region = b.dataset.region; paint(); };
    });
    root.querySelectorAll('#br-lang button').forEach((b) => {
      b.onclick = () => { state.lang = b.dataset.lang; paint(); };
    });
    root.querySelector('#br-brand').onchange = (e) => {
      state.brand = e.target.value;
      paint();
    };

    paint();
  },

  meta(data) {
    return `近 ${data.window_days} 天 ${data.items.length} 則 · 最後檢查 ${fmtStampShort(data.fetched_at)}`;
  },
};
