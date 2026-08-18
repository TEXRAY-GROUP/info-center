/** 主程式:主題切換 + 依註冊表載入各積木 */
import { BLOCKS } from './registry.js';
import { fmtDateTime } from './lib/format.js';

/* ---------- 深淺色 ---------- */
const THEME_KEY = 'texray-theme';

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
}

(function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (prefersDark ? 'dark' : 'light'));
})();

document.getElementById('theme-toggle').addEventListener('click', () => {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

/* ---------- 企業 logo ----------
   載入成功就用正式 logo(其中已含 TEXRAY 字樣,故移除標題重複的字);
   檔案不存在時退回暫代的三色標記。
   日後換成向量檔只要改這一行(建議放 assets/img/logo.svg)。 */
const LOGO_SRC = 'assets/img/logo.png';

(function initLogo() {
  const img = document.getElementById('brand-logo');
  const fallback = document.getElementById('brand-fallback');
  const word = document.getElementById('brand-word');

  const probe = new Image();
  probe.onload = () => {
    img.src = LOGO_SRC;
    img.hidden = false;
    fallback.remove();       // SVG 元素沒有 hidden IDL 屬性,設 .hidden 無效,直接移除
    if (word) word.remove(); // logo 已有 TEXRAY 字樣,避免重複
  };
  probe.onerror = () => {};  // 保留暫代標記
  probe.src = LOGO_SRC;
})();

/* ---------- 積木載入 ---------- */
const main = document.getElementById('blocks');
const nav = document.getElementById('block-nav');

function section(cfg) {
  const sec = document.createElement('section');
  sec.className = 'block';
  sec.id = `block-${cfg.id}`;
  sec.innerHTML = `
    <div class="block-head">
      <h2>${cfg.title}</h2>
      ${cfg.subtitle ? `<span class="block-meta-sub">${cfg.subtitle}</span>` : ''}
      <div class="block-meta"></div>
    </div>
    <div class="block-body"></div>
  `;
  return sec;
}

async function mount(cfg) {
  const sec = section(cfg);
  main.append(sec);

  const body = sec.querySelector('.block-body');
  const meta = sec.querySelector('.block-meta');

  if (!cfg.enabled) {
    sec.classList.add('is-soon');
    body.textContent = cfg.soon || '規劃中';
    meta.textContent = '尚未開放';
    return;
  }

  body.textContent = '載入資料中…';
  try {
    const [mod, data] = await Promise.all([
      cfg.load(),
      fetch(`${cfg.data}?v=${Date.now()}`).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
    ]);
    const block = mod.default;
    meta.innerHTML = block.meta ? block.meta(data) : '';
    body.textContent = '';
    block.render(body, data);
    sec.dataset.fetchedAt = data.fetched_at || '';
  } catch (err) {
    body.innerHTML = `<p class="note">此區塊載入失敗:${err.message}。
      資料可能尚未產生,或自動更新排程異常。</p>`;
    console.error(`[${cfg.id}] 載入失敗`, err);
  }
}

function buildNav() {
  BLOCKS.forEach((cfg) => {
    const a = document.createElement('a');
    a.href = `#block-${cfg.id}`;
    a.textContent = cfg.title;
    if (!cfg.enabled) a.classList.add('is-soon');
    nav.append(a);
  });
}

(async function start() {
  document.getElementById('boot-hint')?.remove();
  buildNav();
  for (const cfg of BLOCKS) await mount(cfg);

  const stamps = [...main.querySelectorAll('.block[data-fetched-at]')]
    .map((s) => s.dataset.fetchedAt)
    .filter(Boolean)
    .sort();
  if (stamps.length) {
    document.getElementById('build-info').textContent =
      `資料最後更新:${fmtDateTime(stamps.at(-1))}(每個工作日自動更新)`;
  }
})();
