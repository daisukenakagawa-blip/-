# パチンコ・パチスロ情報スクレイパー

config.json に登録したサイト(RSS / HTML)から記事タイトル・URL・日付を集めて
CSV / JSON に保存するツールです。動画ネタ探し(auto_video_uploader の topics.csv 候補)
などに使えます。

## セットアップ

```bat
cd pachinko_scraper
pip install -r requirements.txt
```

Windows なら `スクレイピング実行.bat` をダブルクリックでも動きます。

## 使い方

```bat
python scraper.py                        … 全サイトを巡回
python scraper.py --keyword ジャグラー   … タイトルにジャグラーを含む記事だけ保存
python scraper.py --site グリーン        … 名前に「グリーン」を含むサイトだけ
python scraper.py --limit 10             … 1サイトあたり最大10件
```

結果は `data/articles.csv`(累積・重複除外)と `data/articles_日時.json`(その回の全件)に保存されます。

## サイトの追加方法

`config.json` の `sites` に追加するだけです。

**RSSがあるサイト(推奨・簡単)**

```json
{ "name": "サイト名", "type": "rss", "url": "https://…/feed/", "enabled": true }
```

多くのWordPress系サイトは URL の末尾に `/feed/` を付けるとRSSが取れます。

**RSSがないサイト(CSSセレクタで指定)**

```json
{
  "name": "サイト名",
  "type": "html",
  "url": "https://…/news/",
  "enabled": true,
  "selectors": {
    "item": "記事1件を囲む要素のセレクタ (例: article.post)",
    "title": "タイトル要素 (例: h2)",
    "link": "リンクのaタグ (例: a)",
    "date": "日付要素 (例: time) ※省略可"
  }
}
```

セレクタは Chrome で対象要素を右クリック →「検証」→ 要素を右クリック →
「Copy → Copy selector」で調べられます。

## マナーと注意事項(重要)

- **robots.txt を自動チェック**し、禁止されているページはスキップします。
- **同一サイトへのアクセスは3秒以上間隔**を空けます(scraper.py の `REQUEST_INTERVAL_SEC`)。
- スクレイピングを **利用規約で禁止しているサイト**(会員制サイト、DMMぱちタウン、
  多くの出玉データサイトなど)には使わないでください。
- 取得した記事の**本文をそのまま転載・動画化するのは著作権侵害**になります。
  タイトルやURLを「ネタ探しの参考」に使う範囲にとどめてください。
