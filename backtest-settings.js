// 全機種 設定1〜6 を 1万ゲーム × 100セッション バックテスト
// モデルは予想ツールと同一: 1G=3枚投入, BIG=+240枚, REG=+96枚,
//   非ボーナス分は機械割に整合する基礎増減(期待差枚/G = 3*(機械割-1))。
const BIG_COIN=240, REG_COIN=96, BET=3;
const GAMES=10000, SESSIONS=100;
const RENCHAN_G=100; // 連チャン継続条件: 前回ボーナスから100G以内に次が当たれば連チャン継続

// 全機種 設定1〜6 [BIG分母, REG分母, 機械割%]
const MACHINES={
 'アイムジャグラーEX':[[273.1,439.8,97.0],[269.7,399.6,98.0],[269.7,331.0,99.5],[259.0,315.1,101.1],[259.0,255.0,103.3],[255.0,255.0,105.5]],
 'ネオアイムジャグラーEX':[[273.1,439.8,97.0],[269.7,399.6,98.0],[269.7,331.0,99.5],[259.0,315.1,101.1],[259.0,255.0,103.3],[255.0,255.0,105.5]],
 'マイジャグラーV':[[273.1,439.8,97.0],[270.8,385.5,98.7],[266.4,336.1,99.9],[254.0,290.0,102.8],[240.1,268.6,105.3],[229.1,229.1,109.4]],
 'ファンキージャグラー2':[[266.4,439.8,97.0],[259.0,407.1,98.5],[256.0,366.1,99.8],[249.2,322.8,102.8],[240.1,299.3,104.3],[219.9,262.1,109.0]],
 'ゴーゴージャグラー3':[[259.0,354.2,97.0],[258.0,330.0,98.0],[257.0,305.6,99.9],[254.0,268.8,102.8],[247.3,247.3,105.3],[234.9,234.9,109.4]],
 'ハッピージャグラーVIII':[[287.4,409.6,96.1],[282.5,364.1,97.9],[273.1,341.3,99.9],[264.3,315.1,102.9],[252.1,287.4,105.8],[240.9,273.1,108.4]],
 'ジャグラーガールズSS':[[273.1,381.0,97.0],[270.8,350.5,97.9],[260.1,316.6,99.9],[250.1,281.3,102.1],[243.6,270.8,104.0],[226.0,252.1,107.5]],
 'ミスタージャグラー':[[268.6,374.5,97.0],[267.5,354.2,98.0],[260.1,331.0,99.8],[249.2,291.3,102.7],[240.9,257.0,105.5],[237.4,237.4,107.3]],
 'ウルトラミラクルジャグラー':[[267.5,425.6,97.0],[261.1,402.1,98.9],[256.0,350.5,101.0],[242.7,322.8,102.1],[233.2,297.9,105.0],[216.3,277.7,108.1]],
};

// 1セッション(1万G)を回す
function runSession(big,reg,payout){
 const pB=1/big, pR=1/reg;
 const expPerG=BET*(payout/100-1);
 const basePerG=expPerG-(pB*BIG_COIN+pR*REG_COIN);
 let diff=0, nB=0, nR=0;
 let since=0, maxHamari=0;          // 最大ハマり(連続非ボーナス)
 let lastBonusG=-99999, chain=0, maxChain=0; // 連チャン
 for(let g=0; g<GAMES; g++){
   diff+=basePerG;
   const r=Math.random();
   let bonus=false;
   if(r<pB){ diff+=BIG_COIN; nB++; bonus=true; }
   else if(r<pB+pR){ diff+=REG_COIN; nR++; bonus=true; }
   if(bonus){
     if(g-lastBonusG<=RENCHAN_G) chain++; else chain=1;
     if(chain>maxChain) maxChain=chain;
     lastBonusG=g;
     since=0;
   } else {
     since++; if(since>maxHamari) maxHamari=since;
   }
 }
 return {diff,nB,nR,maxHamari,maxChain};
}

const rows=[]; // 集計
const detail=[['機種','設定','セッション','差枚','BIG回数','REG回数','BIG確率','REG確率','合成確率','最大ハマり','最大連チャン']];

for(const [name,sets] of Object.entries(MACHINES)){
 for(let si=0; si<6; si++){
   const [big,reg,payout]=sets[si];
   let sumDiff=0, sumB=0, sumR=0, maxHam=0, maxCh=0;
   let minDiff=Infinity, maxDiff=-Infinity, winCnt=0;
   for(let s=0;s<SESSIONS;s++){
     const r=runSession(big,reg,payout);
     sumDiff+=r.diff; sumB+=r.nB; sumR+=r.nR;
     if(r.maxHamari>maxHam) maxHam=r.maxHamari;
     if(r.maxChain>maxCh) maxCh=r.maxChain;
     if(r.diff<minDiff) minDiff=r.diff;
     if(r.diff>maxDiff) maxDiff=r.diff;
     if(r.diff>0) winCnt++;
     detail.push([name,si+1,s+1,Math.round(r.diff),r.nB,r.nR,
       (GAMES/r.nB).toFixed(1),(GAMES/r.nR).toFixed(1),(GAMES/(r.nB+r.nR)).toFixed(1),
       r.maxHamari,r.maxChain]);
   }
   const tot=SESSIONS*GAMES; // 100万G
   rows.push({name,set:si+1,payout,
     avgDiff:sumDiff/SESSIONS, minDiff, maxDiff,
     bigP:tot/sumB, regP:tot/sumR, combP:tot/(sumB+sumR),
     maxHam, maxCh, win:winCnt});
 }
}

// CSV出力
const fs=require('fs');
fs.writeFileSync('backtest-all-sessions.csv', detail.map(r=>r.join(',')).join('\n'));
const sumCsv=[['機種','設定','機械割%','平均差枚','最低差枚','最高差枚','勝率%','BIG確率','REG確率','合成確率','最大ハマり','最大連チャン']];
rows.forEach(r=>sumCsv.push([r.name,r.set,r.payout,Math.round(r.avgDiff),Math.round(r.minDiff),Math.round(r.maxDiff),
  r.win,'1/'+r.bigP.toFixed(1),'1/'+r.regP.toFixed(1),'1/'+r.combP.toFixed(1),r.maxHam,r.maxCh]));
fs.writeFileSync('backtest-summary.csv', sumCsv.map(r=>r.join(',')).join('\n'));

// コンソール表示
const pad=(s,n)=>String(s).padEnd(n), padL=(s,n)=>String(s).padStart(n);
const fmt=n=>(n>0?'+':'')+Math.round(n).toLocaleString();
console.log(`全機種 設定1〜6 バックテスト  ${GAMES.toLocaleString()}G × ${SESSIONS}セッション/条件`);
console.log(`確率は各条件100万G集計の実測。連チャン=前回から${RENCHAN_G}G以内継続の最長連続数。\n`);
let cur='';
for(const r of rows){
 if(r.name!==cur){ cur=r.name;
   console.log('\n■ '+cur);
   console.log(pad('設定',5)+padL('平均差枚',10)+padL('最低',9)+padL('最高',9)+padL('勝率',6)+padL('BIG',10)+padL('REG',10)+padL('合成',10)+padL('最大ハマり',9)+padL('最大連チャン',9));
 }
 console.log(pad('設定'+r.set,5)+padL(fmt(r.avgDiff),10)+padL(fmt(r.minDiff),9)+padL(fmt(r.maxDiff),9)+
   padL(r.win+'%',6)+padL('1/'+r.bigP.toFixed(1),10)+padL('1/'+r.regP.toFixed(1),10)+padL('1/'+r.combP.toFixed(1),10)+
   padL(r.maxHam+'G',9)+padL(r.maxCh+'連',9));
}
console.log('\nCSV: backtest-all-sessions.csv (全'+(detail.length-1)+'セッションの生データ) / backtest-summary.csv (54条件の集計)');
