// 各機種の設定6を10万ゲーム・バックテスト
// モデルは予想ツール(juggler-yosou.html / slump-graph-yosou.html)と同一:
//   1ゲーム3枚投入。BIG=+240枚, REG=+96枚。非ボーナス分は機械割に整合する基礎増減。
//   期待差枚/G = 3*(機械割-1)。基礎増減/G = それ - (pB*240 + pR*96)。
const BIG_COIN = 240, REG_COIN = 96, BET = 3;
const GAMES = 100000;          // 1セッションのゲーム数
const SESSIONS = 1000;         // 分布をとる試行回数(集計用)

// 各機種 設定6 (BIG分母, REG分母, 機械割%)
const SET6 = {
  'アイムジャグラーEX':        {big:255.0, reg:255.0, payout:105.5},
  'ネオアイムジャグラーEX':    {big:255.0, reg:255.0, payout:105.5},
  'マイジャグラーV':           {big:229.1, reg:229.1, payout:109.4},
  'ファンキージャグラー2':     {big:219.9, reg:262.1, payout:109.0},
  'ゴーゴージャグラー3':       {big:234.9, reg:234.9, payout:109.4},
  'ハッピージャグラーVIII':    {big:240.9, reg:273.1, payout:108.4},
  'ジャグラーガールズSS':      {big:226.0, reg:252.1, payout:107.5},
  'ミスタージャグラー':        {big:237.4, reg:237.4, payout:107.3},
  'ウルトラミラクルジャグラー':{big:216.3, reg:277.7, payout:108.1},
};

function randn(){ let u=0,v=0; while(!u)u=Math.random(); while(!v)v=Math.random(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); }

// 1セッション(ゲームごと)を回し、詳細統計を返す
function runDetailed(spec){
  const pB = 1/spec.big, pR = 1/spec.reg;
  const expPerG = BET*(spec.payout/100 - 1);
  const basePerG = expPerG - (pB*BIG_COIN + pR*REG_COIN);
  let diff=0, big=0, reg=0;
  let peak=0, maxDD=0;          // 最大ドローダウン(高値からの落ち込み)
  let sinceBonus=0, maxHamari=0; // 最大ハマり(連続非ボーナス)
  for(let g=0; g<GAMES; g++){
    diff += basePerG;
    const r=Math.random();
    if(r < pB){ diff+=BIG_COIN; big++; sinceBonus=0; }
    else if(r < pB+pR){ diff+=REG_COIN; reg++; sinceBonus=0; }
    else { sinceBonus++; if(sinceBonus>maxHamari) maxHamari=sinceBonus; }
    if(diff>peak) peak=diff;
    const dd=peak-diff; if(dd>maxDD) maxDD=dd;
  }
  return {diff, big, reg, maxDD, maxHamari};
}

// 集計用: 100kゲームの最終差枚を二項(正規近似)で高速サンプル
function sampleFinalDiff(spec){
  const pB=1/spec.big, pR=1/spec.reg;
  const expPerG=BET*(spec.payout/100-1);
  const basePerG=expPerG-(pB*BIG_COIN+pR*REG_COIN);
  const nB=Math.round(GAMES*pB + Math.sqrt(GAMES*pB*(1-pB))*randn());
  const nR=Math.round(GAMES*pR + Math.sqrt(GAMES*pR*(1-pR))*randn());
  return basePerG*GAMES + nB*BIG_COIN + nR*REG_COIN;
}

const pad=(s,n)=>String(s).padEnd(n);
const padL=(s,n)=>String(s).padStart(n);
const fmt=n=>(n>0?'+':'')+Math.round(n).toLocaleString();

console.log('='.repeat(96));
console.log(`設定6 バックテスト  ${GAMES.toLocaleString()}ゲーム/セッション  集計 ${SESSIONS}セッション`);
console.log('='.repeat(96));

// (A) 詳細1セッション(ゲームごと) — 実測確率/差枚/最大ハマり/最大DD
console.log('\n【A】 ゲームごと10万G 1セッション 実測');
console.log(pad('機種',26)+pad('実測BIG',13)+pad('実測REG',13)+pad('実測割',9)+pad('最終差枚',12)+pad('最大ハマリ',10)+'最大DD');
console.log('-'.repeat(96));
for(const [name,spec] of Object.entries(SET6)){
  const r=runDetailed(spec);
  const realBig = (GAMES/r.big).toFixed(1);
  const realReg = (GAMES/r.reg).toFixed(1);
  const realPayout = (1 + r.diff/(BET*GAMES))*100;
  console.log(
    pad(name,26)+
    pad('1/'+realBig,13)+
    pad('1/'+realReg,13)+
    pad(realPayout.toFixed(1)+'%',9)+
    pad(fmt(r.diff),12)+
    pad(r.maxHamari+'G',10)+
    '-'+Math.round(r.maxDD).toLocaleString()+'枚'
  );
}

// (B) 1000セッション集計 — 最終差枚の分布・勝率
console.log('\n【B】 10万G × '+SESSIONS+'セッション集計  最終差枚の分布');
console.log(pad('機種',26)+pad('公表割',9)+pad('平均差枚',12)+pad('中央値',12)+pad('最低',11)+pad('最高',11)+pad('標準偏差',10)+'勝率');
console.log('-'.repeat(96));
for(const [name,spec] of Object.entries(SET6)){
  const arr=[];
  for(let s=0;s<SESSIONS;s++) arr.push(sampleFinalDiff(spec));
  arr.sort((a,b)=>a-b);
  const mean=arr.reduce((a,c)=>a+c,0)/arr.length;
  const med=arr[Math.floor(arr.length/2)];
  const sd=Math.sqrt(arr.reduce((a,c)=>a+(c-mean)**2,0)/arr.length);
  const win=arr.filter(v=>v>0).length/arr.length*100;
  console.log(
    pad(name,26)+
    pad(spec.payout+'%',9)+
    pad(fmt(mean),12)+
    pad(fmt(med),12)+
    pad(fmt(arr[0]),11)+
    pad(fmt(arr[arr.length-1]),11)+
    pad(Math.round(sd).toLocaleString(),10)+
    win.toFixed(1)+'%'
  );
}
console.log('\n注: 期待差枚/10万G = 3枚 × 10万 × (機械割-1)。例 109.4% → 300000×0.094 ≈ +28,200枚。');
console.log('    実測割は乱数次第で公表値の周辺にばらつく(10万Gなら±0.3%程度に収束)。');
