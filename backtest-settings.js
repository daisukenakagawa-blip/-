// 全機種 設定1〜6 を 1万ゲーム × 100セッション バックテスト（チェリー重複対応版）
// モデル: 1G=3枚投入, BIG=+240枚, REG=+96枚, 非ボーナス分は機械割整合の基礎増減。
// ボーナスは内訳(チェリー重複BIG/単独BIG/チェリー重複REG/単独REG)に分解して発生させる。
//   ※チェリー重複は総BIG/総REGの「内数」。総BIG=1/big, 総REG=1/reg は不変。
const BIG_COIN=240, REG_COIN=96, BET=3;
const GAMES=10000, SESSIONS=100;
const RENCHAN_G=100; // 連チャン: 前回ボーナスから100G以内継続の最長連続数

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

// チェリー重複の設定別分母 [設定1..6]  (取り込めた機種のみ。他はデータ非公表で対象外)
//  cBig=チェリー重複BIG(チェリービッグ), cReg=チェリー重複REG(チェリーバケ)
const CHERRY={
 'マイジャグラーV':       {rel:'解析一致(高)', cBig:[1424,1395,1365,1285,1214,1130], cReg:[1092,1074,1057,1008,862,762]},
 'ミスタージャグラー':     {rel:'解析一致(高)', cBig:[1680,1680,1524,1394,1285,1236], cReg:[1680,1560,1394,1213,1074,1008]},
 'ファンキージャグラー2':  {rel:'推定値',      cBig:[1456,1365,1365,1337,1260,1191], cReg:[1424,1394,1285,1149,1110,992]},
 'ゴーゴージャグラー3':    {rel:'推定値(バケは出典分裂)', cBig:[1337,1337,1337,1310,1310,1260], cReg:[1365,1310,1191,1057,964,910]},
 'ウルトラミラクルジャグラー':{rel:'参考値',    cBig:[1365,1213,1149,1129,1024,936],  cReg:[1638,1638,1337,1337,1191,1110]},
};
// 中段チェリー(レアチェリー)=全機種 約1/3276.8・設定差なし・BIG確定プレミア → 判別不可・表示のみ
const RARE_CHERRY = 3276.8;

// 1セッション(1万G)。cherry指定があればボーナスを内訳分解して発生。
function runSession(big,reg,payout,cBig,cReg){
 const pTotBig=1/big, pTotReg=1/reg;
 const pcBig=cBig?1/cBig:0, pcReg=cReg?1/cReg:0;        // チェリー重複
 const psBig=pTotBig-pcBig, psReg=pTotReg-pcReg;        // 単独
 const expPerG=BET*(payout/100-1);
 const basePerG=expPerG-(pTotBig*BIG_COIN+pTotReg*REG_COIN);
 let diff=0, nBig=0, nReg=0, ncBig=0, ncReg=0;
 let since=0, maxHamari=0;
 let lastBonusG=-99999, chain=0, maxChain=0;
 for(let g=0; g<GAMES; g++){
   diff+=basePerG;
   const r=Math.random();
   let bonus=0; // 1=BIG,2=REG
   // 区間: [0,pcBig) チェリーBIG, [..,+psBig) 単独BIG, [..,+pcReg) チェリーREG, [..,+psReg) 単独REG
   if(r<pcBig){ bonus=1; ncBig++; }
   else if(r<pcBig+psBig){ bonus=1; }
   else if(r<pcBig+psBig+pcReg){ bonus=2; ncReg++; }
   else if(r<pcBig+psBig+pcReg+psReg){ bonus=2; }
   if(bonus===1){ diff+=BIG_COIN; nBig++; }
   else if(bonus===2){ diff+=REG_COIN; nReg++; }
   if(bonus){
     if(g-lastBonusG<=RENCHAN_G) chain++; else chain=1;
     if(chain>maxChain) maxChain=chain;
     lastBonusG=g; since=0;
   } else { since++; if(since>maxHamari) maxHamari=since; }
 }
 return {diff,nBig,nReg,ncBig,ncReg,maxHamari,maxChain};
}

const rows=[], cherryRows=[];
const detail=[['機種','設定','セッション','差枚','BIG回数','REG回数','BIG確率','REG確率','合成確率','チェリービッグ回数','チェリーバケ回数','最大ハマり','最大連チャン']];

for(const [name,sets] of Object.entries(MACHINES)){
 const ch=CHERRY[name];
 for(let si=0; si<6; si++){
   const [big,reg,payout]=sets[si];
   const cBig=ch?ch.cBig[si]:null, cReg=ch?ch.cReg[si]:null;
   let sumDiff=0,sumB=0,sumR=0,sumCB=0,sumCR=0,maxHam=0,maxCh=0,minDiff=Infinity,maxDiff=-Infinity,win=0;
   for(let s=0;s<SESSIONS;s++){
     const r=runSession(big,reg,payout,cBig,cReg);
     sumDiff+=r.diff;sumB+=r.nBig;sumR+=r.nReg;sumCB+=r.ncBig;sumCR+=r.ncReg;
     if(r.maxHamari>maxHam)maxHam=r.maxHamari; if(r.maxChain>maxCh)maxCh=r.maxChain;
     if(r.diff<minDiff)minDiff=r.diff; if(r.diff>maxDiff)maxDiff=r.diff; if(r.diff>0)win++;
     detail.push([name,si+1,s+1,Math.round(r.diff),r.nBig,r.nReg,
       (GAMES/r.nBig).toFixed(1),(GAMES/r.nReg).toFixed(1),(GAMES/(r.nBig+r.nReg)).toFixed(1),
       ch?r.ncBig:'',ch?r.ncReg:'',r.maxHamari,r.maxChain]);
   }
   const tot=SESSIONS*GAMES;
   rows.push({name,set:si+1,payout,avgDiff:sumDiff/SESSIONS,minDiff,maxDiff,
     bigP:tot/sumB,regP:tot/sumR,combP:tot/(sumB+sumR),maxHam,maxCh,win});
   if(ch){
     cherryRows.push({name,set:si+1,rel:ch.rel,
       cBigPub:cBig,cBigReal:sumCB?tot/sumCB:Infinity,
       cRegPub:cReg,cRegReal:sumCR?tot/sumCR:Infinity});
   }
 }
}

const fs=require('fs');
fs.writeFileSync('backtest-all-sessions.csv', detail.map(r=>r.join(',')).join('\n'));
const sumCsv=[['機種','設定','機械割%','平均差枚','最低差枚','最高差枚','勝率%','BIG確率','REG確率','合成確率','最大ハマり','最大連チャン']];
rows.forEach(r=>sumCsv.push([r.name,r.set,r.payout,Math.round(r.avgDiff),Math.round(r.minDiff),Math.round(r.maxDiff),r.win,
  '1/'+r.bigP.toFixed(1),'1/'+r.regP.toFixed(1),'1/'+r.combP.toFixed(1),r.maxHam,r.maxCh]));
fs.writeFileSync('backtest-summary.csv', sumCsv.map(r=>r.join(',')).join('\n'));
const chCsv=[['機種','設定','信頼度','チェリービッグ公表','チェリービッグ実測','チェリーバケ公表','チェリーバケ実測']];
cherryRows.forEach(r=>chCsv.push([r.name,r.set,r.rel,'1/'+r.cBigPub,'1/'+r.cBigReal.toFixed(1),'1/'+r.cRegPub,'1/'+r.cRegReal.toFixed(1)]));
fs.writeFileSync('backtest-cherry.csv', chCsv.map(r=>r.join(',')).join('\n'));

// コンソール
const pad=(s,n)=>String(s).padEnd(n), padL=(s,n)=>String(s).padStart(n);
const fmt=n=>(n>0?'+':'')+Math.round(n).toLocaleString();
console.log(`全機種 設定1〜6 バックテスト  ${GAMES.toLocaleString()}G × ${SESSIONS}セッション/条件`);
console.log(`確率は各条件100万G集計の実測。連チャン=前回から${RENCHAN_G}G以内継続の最長連続数。`);
console.log(`中段(レア)チェリー=全機種 約1/${RARE_CHERRY}・設定差なし・BIG確定プレミア(判別不可)。\n`);
let cur='';
for(const r of rows){
 if(r.name!==cur){ cur=r.name;
   console.log('\n■ '+cur+(CHERRY[cur]?'  [チェリー重複データ: '+CHERRY[cur].rel+']':'  [チェリー重複: 設定別公表なし]'));
   console.log(pad('設定',5)+padL('平均差枚',10)+padL('最低',9)+padL('最高',9)+padL('勝率',6)+padL('BIG',10)+padL('REG',10)+padL('合成',10)+padL('最大ハマり',9)+padL('最大連チャン',9));
 }
 console.log(pad('設定'+r.set,5)+padL(fmt(r.avgDiff),10)+padL(fmt(r.minDiff),9)+padL(fmt(r.maxDiff),9)+padL(r.win+'%',6)+
   padL('1/'+r.bigP.toFixed(1),10)+padL('1/'+r.regP.toFixed(1),10)+padL('1/'+r.combP.toFixed(1),10)+padL(r.maxHam+'G',9)+padL(r.maxCh+'連',9));
}
// チェリー重複セクション
console.log('\n\n=== チェリー重複（対応機種のみ・公表値 vs 100万G実測）===');
let ccur='';
for(const r of cherryRows){
 if(r.name!==ccur){ ccur=r.name;
   console.log('\n■ '+ccur+'  ['+r.rel+']');
   console.log(pad('設定',5)+padL('チェリービッグ(公表/実測)',26)+padL('チェリーバケ(公表/実測)',26));
 }
 console.log(pad('設定'+r.set,5)+padL('1/'+r.cBigPub+' / 1/'+r.cBigReal.toFixed(0),26)+padL('1/'+r.cRegPub+' / 1/'+r.cRegReal.toFixed(0),26));
}
console.log('\nCSV: backtest-all-sessions.csv(全'+(detail.length-1)+'セッション) / backtest-summary.csv(54条件) / backtest-cherry.csv(チェリー重複)');
