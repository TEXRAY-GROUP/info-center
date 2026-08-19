/**
 * 主程式:深淺色、錨點路由、依註冊表載入積木
 *
 * 路由用網址錨點(#/rates、#/freight…),不用乾淨網址——
 * GitHub Pages 直接開 /rates 會 404,要用 404.html 轉址的偏方,不穩。
 * 一次只載入並顯示一塊積木:五塊資料全載是 269 KB,一塊通常只有 10~90 KB。
 */
import { BLOCKS } from './registry.js';
import { fmtDateTime } from './lib/format.js';

const LAST_PAGE_KEY = 'texray-last-page';
const THEME_KEY = 'texray-theme';
const SITE_TITLE = 'TEXRAY 綜合資訊中心';

const view = document.getElementById('view');
const nav = document.getElementById('nav');

/* ---------- 深淺色 ---------- */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
}
applyTheme(localStorage.getItem(THEME_KEY) ||
  (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

document.getElementById('theme-toggle').addEventListener('click', () => {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

/* ---------- 企業 logo ----------
   載入成功就用正式 logo(其中已含 TEXRAY 字樣,故移除標題重複的字);
   檔案不存在時退回暫代的三色標記。日後換向量檔只要改這一行。 */
const LOGO_SRC = 'assets/img/logo.png';
(function initLogo() {
  const img = document.getElementById('brand-logo');
  const fallback = document.getElementById('brand-fallback');
  const word = document.getElementById('brand-word');
  const probe = new Image();
  probe.onload = () => {
    img.src = LOGO_SRC;
    img.hidden = false;
    fallback.remove();       // SVG 沒有 hidden IDL 屬性,設 .hidden 無效,直接移除
    if (word) word.remove();
  };
  probe.src = LOGO_SRC;
})();

/* ---------- 路由 ---------- */
const enabled = BLOCKS.filter((b) => b.enabled);
const byId = Object.fromEntries(BLOCKS.map((b) => [b.id, b]));
const dataCache = new Map();      // 同一次瀏覽內載過的資料不重載
let current = null;               // { id, cleanup }

function routeId() {
  const m = location.hash.match(/^#\/([\w-]+)/);
  if (m && byId[m[1]]?.enabled) return m[1];
  const last = localStorage.getItem(LAST_PAGE_KEY);
  if (last && byId[last]?.enabled) return last;
  return enabled[0]?.id;
}

function buildNav() {
  nav.innerHTML = BLOCKS.map((b) => b.enabled
    ? `<a href="#/${b.id}" data-id="${b.id}">
         <span class="nav-title">${b.title}</span>
         <span class="nav-sub">${b.subtitle || ''}</span>
       </a>`
    : `<span class="nav-soon" title="${b.soon || ''}">
         <span class="nav-title">${b.title}</span>
         <span class="nav-sub">規劃中</span>
       </span>`).join('');
}

function markNav(id) {
  nav.querySelectorAll('a').forEach((a) => {
    const on = a.dataset.id === id;
    a.classList.toggle('is-active', on);
    if (on) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
}

async function loadData(cfg) {
  if (dataCache.has(cfg.id)) return dataCache.get(cfg.id);
  const r = await fetch(`${cfg.data}?v=${Date.now()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const json = await r.json();
  dataCache.set(cfg.id, json);
  return json;
}

async function show(id) {
  const cfg = byId[id];
  if (!cfg) return;

  // 換頁前先讓上一塊收拾自己(有些積木掛了 window resize 監聽器,
  // 不解除的話反覆進出會越疊越多)
  if (current?.cleanup) {
    try { current.cleanup(); } catch (err) { console.error('destroy 失敗', err); }
  }
  current = { id, cleanup: null };

  markNav(id);
  localStorage.setItem(LAST_PAGE_KEY, id);
  document.title = `${cfg.title} · ${SITE_TITLE}`;

  view.innerHTML = `
    <section class="block" id="block-${cfg.id}">
      <div class="block-head">
        <h2>${cfg.title}</h2>
        ${cfg.subtitle ? `<span class="block-sub">${cfg.subtitle}</span>` : ''}
        <div class="block-meta"></div>
      </div>
      <div class="block-body">載入資料中…</div>
    </section>`;

  const body = view.querySelector('.block-body');
  const meta = view.querySelector('.block-meta');

  try {
    const [mod, data] = await Promise.all([cfg.load(), loadData(cfg)]);
    if (current.id !== id) return;            // 使用者已經切走,丟棄這次結果
    const block = mod.default;
    meta.innerHTML = block.meta ? block.meta(data) : '';
    body.textContent = '';
    // render 可回傳一個清理函式,換頁時呼叫
    current.cleanup = block.render(body, data) || null;
    updateFooter(data);
  } catch (err) {
    body.innerHTML = `<p class="note">此區塊載入失敗:${err.message}。
      資料可能尚未產生,或自動更新排程異常。</p>`;
    console.error(`[${id}] 載入失敗`, err);
  }
}

function updateFooter(data) {
  const stamp = data.fetched_at || data.updated_at;
  document.getElementById('build-info').textContent = stamp
    ? `最後檢查 ${fmtDateTime(stamp)}`
    : '';
}

function onRoute() {
  const id = routeId();
  if (!id) return;
  // 網址沒有錨點(或指向不存在的頁)時,把網址補成實際顯示的那一頁
  if (location.hash !== `#/${id}`) {
    location.replace(`#/${id}`);
    return;                                    // replace 會再觸發一次 hashchange
  }
  if (current?.id === id) return;
  show(id);
}

buildNav();
window.addEventListener('hashchange', onRoute);
onRoute();
