/**
 * 積木註冊表
 *
 * 新增一塊積木 = 新增四件套 + 在這裡加一行:
 *   1. scripts/fetch_<id>.py   抓取器(人工維護的積木可省略)
 *   2. data/<id>.json          資料
 *   3. assets/js/blocks/<id>.js  畫面(export default { render(el, data) })
 *   4. 本檔案加一筆 { id, title, ... }
 *
 * enabled: false 的積木會顯示成「規劃中」佔位卡,不會去抓資料。
 */
export const BLOCKS = [
  {
    id: 'rates',
    title: '匯率',
    subtitle: '臺灣銀行牌告',
    data: 'data/rates.json',
    enabled: true,
    load: () => import('./blocks/rates.js'),
  },
  {
    id: 'news',
    title: '紡織產業新聞',
    subtitle: '多來源彙整',
    data: 'data/news.json',
    enabled: true,
    load: () => import('./blocks/news.js'),
  },
  {
    id: 'brands',
    title: '品牌客戶動態',
    subtitle: '國際成衣品牌經營面消息',
    data: 'data/brands.json',
    enabled: true,
    load: () => import('./blocks/brands.js'),
  },
  {
    id: 'materials',
    title: '原物料價格',
    subtitle: '聚酯鏈 · 棉花 · 能源',
    data: 'data/materials.json',
    enabled: true,
    load: () => import('./blocks/materials.js'),
  },
  {
    id: 'freight',
    title: '運費試算',
    subtitle: 'DHL vs FedEx 公告價',
    data: 'data/freight.json',
    enabled: true,
    load: () => import('./blocks/freight.js'),
  },
];
