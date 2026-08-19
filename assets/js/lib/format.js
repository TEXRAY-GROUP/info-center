/** 共用格式化工具 */

/**
 * 匯率位數:依數值大小自動決定小數位,貼近台銀牌告的呈現。
 * 32.43 / 4.831 / 0.2054 / 0.00142
 */
export function fmtRate(v, ref = v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  // 位數依 ref 決定,讓「漲跌」與「主數字」的小數位一致(如 32.43 / 0.09)
  const a = Math.abs(ref);
  const d = a >= 10 ? 2 : a >= 1 ? 3 : a >= 0.01 ? 4 : 5;
  return v.toFixed(d);
}

/** 金額(千分位;小數位可指定) */
export function fmtMoney(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toLocaleString('zh-TW', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** 漲跌:回傳 { text, cls } */
export function fmtChange(change, pct, ref) {
  if (change === null || change === undefined) return { text: '—', cls: 'flat' };
  const cls = change > 0 ? 'up' : change < 0 ? 'down' : 'flat';
  const sign = change > 0 ? '▲' : change < 0 ? '▼' : '－';
  const p = pct === null || pct === undefined ? '' : ` (${pct > 0 ? '+' : ''}${pct.toFixed(2)}%)`;
  return { text: `${sign} ${fmtRate(Math.abs(change), ref ?? change)}${p}`, cls };
}

/** 2026-08-13 → 8/13(週四) */
export function fmtDateShort(iso) {
  const d = new Date(iso + 'T00:00:00+08:00');
  const w = '日一二三四五六'[d.getDay()];
  return `${d.getMonth() + 1}/${d.getDate()}(週${w})`;
}

/** 2026-08-19T08:56:04+08:00 → 8/19 08:56(給區塊標題用的短格式) */
export function fmtStampShort(iso) {
  if (!iso) return '';
  const [date, time] = String(iso).split('T');
  const [, m, d] = date.split('-');
  return `${Number(m)}/${Number(d)} ${(time || '').slice(0, 5)}`;
}

/** ISO 時間 → 2026-08-14 15:30 */
export function fmtDateTime(iso) {
  if (!iso) return '';
  return String(iso).replace('T', ' ').slice(0, 16);
}
