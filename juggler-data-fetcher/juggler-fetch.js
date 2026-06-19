#!/usr/bin/env node
/*
 * ジャグラー台データ取り込みツール
 *  - robots.txt を尊重し、レート制限つきでHTMLを取得（urlモード）
 *  - 保存済みHTMLをオフライン解析（fileモード／ネット不要・安全）
 *  - 表(<table>)解析 or ラベル近傍解析で 台番号/G数/BB/RB/差枚 を抽出
 *
 * アクセス制御(ログイン/有料/対策)の回避は一切行いません。
 * 対象サイトの利用規約・robots.txt を必ず自分で確認してください。
 */
'use strict';
const https = require('https');
const http = require('http');
const fs = require('fs');
const { URL } = require('url');

// ---------- 引数パース ----------
function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t.startsWith('--')) {
      const key = t.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) { a[key] = true; }
      else { a[key] = next; i++; }
    } else a._.push(t);
  }
  return a;
}

// ---------- HTML 取得（robots尊重＋レート制限） ----------
function get(urlStr, ua, timeout = 15000) {
  return new Promise((resolve, reject) => {
    let u;
    try { u = new URL(urlStr); } catch (e) { return reject(new Error('URL不正: ' + urlStr)); }
    const lib = u.protocol === 'http:' ? http : https;
    const req = lib.get(u, { headers: { 'User-Agent': ua, 'Accept': 'text/html' } }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(get(new URL(res.headers.location, u).toString(), ua, timeout));
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error('HTTP ' + res.statusCode)); }
      let data = ''; res.setEncoding('utf8');
      res.on('data', c => data += c);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(timeout, () => { req.destroy(new Error('タイムアウト')); });
  });
}

// robots.txt を取得し、指定パスが User-agent:* で Disallow されていないか確認
async function robotsAllows(urlStr, ua) {
  const u = new URL(urlStr);
  const robotsUrl = `${u.protocol}//${u.host}/robots.txt`;
  let txt;
  try { txt = await get(robotsUrl, ua); }
  catch (e) { return { allowed: true, note: 'robots.txt取得不可（' + e.message + '）→存在しないものとして続行。規約は自分で確認のこと' }; }
  // User-agent: * グループの Disallow を収集
  const lines = txt.split(/\r?\n/).map(l => l.replace(/#.*/, '').trim());
  let inStar = false; const disallow = [];
  for (const l of lines) {
    const m = l.match(/^([A-Za-z-]+)\s*:\s*(.*)$/);
    if (!m) continue;
    const field = m[1].toLowerCase(), val = m[2].trim();
    if (field === 'user-agent') inStar = (val === '*');
    else if (inStar && field === 'disallow' && val) disallow.push(val);
  }
  const path = u.pathname + (u.search || '');
  for (const d of disallow) { if (path.startsWith(d)) return { allowed: false, rule: d }; }
  return { allowed: true };
}

// ---------- HTML パース（正規表現ベース・依存なし） ----------
const stripTags = s => s.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ')
  .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/\s+/g, ' ').trim();

// 全 <table> を [ [ [cell,...], ...rows ], ...tables ] に
function extractTables(html) {
  const tables = [];
  const tableRe = /<table\b[\s\S]*?<\/table>/gi;
  let tm;
  while ((tm = tableRe.exec(html))) {
    const rows = [];
    const rowRe = /<tr\b[\s\S]*?<\/tr>/gi;
    let rm;
    while ((rm = rowRe.exec(tm[0]))) {
      const cells = [];
      const cellRe = /<(?:td|th)\b[\s\S]*?<\/(?:td|th)>/gi;
      let cm;
      while ((cm = cellRe.exec(rm[0]))) cells.push(stripTags(cm[0]));
      if (cells.length) rows.push(cells);
    }
    if (rows.length) tables.push(rows);
  }
  return tables;
}

const toInt = s => {
  if (s == null) return null;
  const m = String(s).replace(/[, ]/g, '').match(/-?\+?\d+/);
  if (!m) return null;
  return parseInt(m[0].replace('+', ''), 10);
};

// ---------- inspect ----------
function cmdInspect(html) {
  const tables = extractTables(html);
  if (!tables.length) { console.log('表(<table>)が見つかりませんでした。--label 方式を試してください。'); return; }
  console.log(`表を ${tables.length} 個検出。\n`);
  tables.forEach((rows, ti) => {
    const cols = Math.max(...rows.map(r => r.length));
    console.log(`■ table #${ti}  行数=${rows.length} 最大列数=${cols}`);
    console.log('  見出し行: ' + rows[0].map((c, i) => `[${i}]${c}`).join(' | '));
    const sample = rows.find((r, i) => i > 0 && r.length === cols) || rows[1] || rows[0];
    if (sample) console.log('  サンプル: ' + sample.map((c, i) => `[${i}]${c}`).join(' | '));
    console.log('');
  });
  console.log('→ 使う表を --table <番号>、列を --cols "台番号,G数,BB,RB,差枚" の順で指定してください（不要列は -）。');
}

// ---------- table → rows ----------
function cmdTable(html, args) {
  const tables = extractTables(html);
  const ti = toInt(args.table) || 0;
  if (!tables[ti]) { console.error(`table #${ti} がありません（検出 ${tables.length} 個）`); process.exit(1); }
  if (!args.cols) { console.error('--cols "台番号,G数,BB,RB,差枚" を指定してください（0始まり、不要列は -）'); process.exit(1); }
  const idx = String(args.cols).split(',').map(s => s.trim());
  const [iNo, iG, iBB, iRB, iDiff] = idx.map(s => s === '-' ? -1 : parseInt(s, 10));
  const out = [['台番号', '総回転数', 'BIG', 'REG', '差枚', '合成確率']];
  for (const row of tables[ti]) {
    const g = iG >= 0 ? toInt(row[iG]) : null;
    const bb = iBB >= 0 ? toInt(row[iBB]) : null;
    const rb = iRB >= 0 ? toInt(row[iRB]) : null;
    if (g == null || bb == null || rb == null) continue;     // データ行のみ
    if (g <= 0 || (bb + rb) <= 0) continue;
    const no = iNo >= 0 ? (row[iNo] ?? '') : '';
    const diff = iDiff >= 0 ? toInt(row[iDiff]) : '';
    const comb = (bb + rb) > 0 ? '1/' + (g / (bb + rb)).toFixed(1) : '';
    out.push([no, g, bb, rb, diff == null ? '' : diff, comb]);
  }
  return out;
}

// ---------- label 方式（単台ページ） ----------
function cmdLabel(html) {
  const text = stripTags(html);
  const grab = res => { for (const re of res) { const m = text.match(re); if (m) { const n = toInt(m[1]); if (n != null) return n; } } return null; };
  const g = grab([/(?:総(?:スタート|回転|ゲーム)数?|G数|GAME)\D{0,6}([0-9,]{2,7})/i]);
  const bb = grab([/(?:BB|BIG|ビッグ)\D{0,4}([0-9,]{1,4})/i]);
  const rb = grab([/(?:RB|REG|バケ|レギュラー)\D{0,4}([0-9,]{1,4})/i]);
  const diff = grab([/(?:差枚|差玉|出玉)\D{0,4}([+\-]?[0-9,]{1,6})/]);
  if (g == null || bb == null || rb == null) {
    console.error('ラベルから G数/BB/RB を抽出できませんでした。inspect で表を確認してください。');
    process.exit(1);
  }
  const comb = '1/' + (g / (bb + rb)).toFixed(1);
  return [['台番号', '総回転数', 'BIG', 'REG', '差枚', '合成確率'], ['', g, bb, rb, diff == null ? '' : diff, comb]];
}

// ---------- 出力 ----------
function output(rows, args) {
  if (rows.length <= 1) { console.error('データ行が0件でした。--table/--cols を見直してください。'); process.exit(1); }
  const csv = rows.map(r => r.join(',')).join('\n');
  if (args.out) { fs.writeFileSync(args.out, csv); console.error(`✅ ${rows.length - 1}件を ${args.out} に出力しました。`); }
  else console.log(csv);
}

// ---------- main ----------
(async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0], target = args._[1];
  const ua = args.ua || 'juggler-data-fetcher (personal use; respect robots/ToS)';
  const delay = parseInt(args.delay, 10) || 3000;

  if (!cmd || !target || cmd === 'help') {
    console.log('使い方: node juggler-fetch.js <inspect|url|file> <URL|path> [--table N] [--cols "..."] [--label] [--out f.csv] [--ua ".."] [--delay ms]');
    console.log('  inspect : 表の構造を確認   url : 取得して解析   file : 保存HTMLを解析');
    process.exit(0);
  }

  // HTML を用意
  let html;
  const isUrl = /^https?:\/\//i.test(target);
  if (cmd === 'url' || (cmd === 'inspect' && isUrl)) {
    // robots.txt 確認
    const rb = await robotsAllows(target, ua);
    if (!rb.allowed) {
      console.error(`⛔ robots.txt により取得が禁止されています（Disallow: ${rb.rule}）。中止します。`);
      process.exit(2);
    }
    if (rb.note) console.error('ℹ️ ' + rb.note);
    console.error(`⏳ レート制限のため ${delay}ms 待機してから取得します…`);
    await new Promise(r => setTimeout(r, delay));
    try { html = await get(target, ua); }
    catch (e) {
      console.error('取得失敗: ' + e.message);
      console.error('※この環境は外部アクセスが許可制です。自分のPC/サーバーで実行するか、保存HTMLを file モードで解析してください。');
      process.exit(1);
    }
  } else {
    // file
    try { html = fs.readFileSync(target, 'utf8'); }
    catch (e) { console.error('ファイル読み込み失敗: ' + e.message); process.exit(1); }
  }

  if (cmd === 'inspect') { cmdInspect(html); return; }
  let rows;
  if (args.label) rows = cmdLabel(html);
  else rows = cmdTable(html, args);
  output(rows, args);
})();
