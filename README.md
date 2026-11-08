# My Radio

ニュースの見出しと概要を集め、日本語の短い番組にするスマホ向けラジオです。元のキャラクターとプレーヤーで、音声、字幕、台本、元記事を確認できます。配信枠は日本時間の **07:00・12:00・18:00** です。同じ日の回も番組一覧から選べます。

## スマホで聴く

HTTPS で配信したページをスマホで開きます。iPhone は Safari の共有メニューから「ホーム画面に追加」を選び、「Webアプリとして開く」をオンにします。Android は Chrome のメニューから「ホーム画面に追加」または「インストール」を選びます。ニュースの再生にはネット接続が必要です。

## デモを試す

配布された **My Radio デモ.html** は、ダブルクリックでブラウザーに開き、再生ボタンを押すと聴けます。音声と字幕を同じファイルに入れているため、サーバーの起動やネット接続は不要です。

リポジトリから試聴ファイルを作る場合は、Python 3 で次を実行します。日本語のサンプル放送が2回分入ります。

```sh
python tools/demo.py --output "../My Radio デモ.html"
```

開発用の通常版をブラウザーで確認する場合は `python -m http.server 8000 --bind 127.0.0.1` を実行し、[ローカルのプレーヤー](http://127.0.0.1:8000/) を開きます。

## ニュースを登録して番組を作る

- [news.json](news.json) に、NHK、Yahoo!ニュース、朝日新聞、毎日新聞、時事通信、FNN、東洋経済オンライン、Impress Watch、nippon.com、デジタル庁の公式 RSS を登録しています。差し替える場合は媒体名と公開 RSS／Atom URL を設定します。
- 各回は最大4件。RSS の説明から短く完結した文を最大2文選び、元記事へのリンクを付けます。見出ししか配信していない記事や、紹介できる説明のない記事は飛ばします。直近に扱った同じ記事 URL は除外します。新着がなければ前の回を保持します。
- 読み上げはニュースに絞り、天気と地震はプレーヤー下の放送データに表示します。放送一覧で回を切り替えると、その回のグラフと地図に切り替わります。
- 天気は東京・ソウル・北京・ニューデリー・ロンドン・パリ・ベルリン・ローマ・ワシントン・オタワの気温を横棒グラフで比較できます。気温と天気は Open-Meteo の推定値です。
- 地震マップは前の配信枠より後、今回の配信枠までのデータを表示します。気象庁の最大震度3以上と USGS のマグニチュード5以上が対象で、ピンや一覧から発生時刻と出典を確認できます。朝7時の回は前日の18時から集計します。
- 標準の音声はものラジオと同じ `COEIROINK:リリンちゃん` の「メスガキ」スタイルです。読み上げは PC 上の COEIROINK が行います。ニュース・天気・地震の取得に通信が必要で、API キーや従量課金の設定は不要です。

PC で [COEIROINK v2](https://coeiroink.com/download) を開き、キャラクターダウンロードから「リリンちゃん」の「メスガキ」を追加して起動したままにします。Python 3.12 で以下を実行すると、指定先の **My Radio.html** を更新します。同じフォルダーに台本と直近30日分の音声を保管します。

```sh
python -m pip install lameenc==1.9.0
python tools/local_radio.py --slot 07:00 --library ../radio-library
```

Windows のタスク スケジューラに、このコマンドを日本時間の07:00・12:00・18:00で登録できます。各タスクの `--slot` を対応する時刻に変更し、同じライブラリーを指定します。作業フォルダーはこのリポジトリに設定してください。PC と COEIROINK の起動中に生成できます。

## GitHub Actions で試聴版を作る

現在のフォークは公開リポジトリです。GitHub Pages の番組や GitHub Actions にアップロードしたファイルは閲覧可能になります。個人で使う場合はローカルで生成してください。この方式は RSS の文を抜き出して読み上げるため、一般公開する場合は再利用と配信が許可されたフィードに差し替えてください。

1. フォークの **Actions** を有効にします。**Actions → My Radio broadcast → Run workflow** で試聴版を選ぶと、サンプルだけを含む `radio-demo` をダウンロードできます。ZIP を展開して中の HTML を開きます。
2. GitHub の標準環境には COEIROINK がないため、リリンちゃんで番組を作る場合は上のローカル生成を使います。音声を Mei に変えて GitHub Pages に公開する場合は、配信可能な RSS に差し替え、`news.json` の `voice` を `mei`、`allow_publication` を `true` にします。**Settings → Pages → Source → GitHub Actions** を選び、**Run workflow** で放送枠を選んで試聴版のチェックを外します。
3. 定時公開を有効にするには、Actions のリポジトリ変数 `BROADCAST_ENABLED` を `true` に設定します。時刻は [ワークフロー](.github/workflows/broadcast.yml) と [局の表示設定](station.json) にあります。GitHub Actions の混雑時は開始が遅れる場合があります。

台本と直近30日分の公開用音声は、放送専用の `broadcast-data` ブランチに保存されます。プレーヤーは音声の公開期間が過ぎた回も台本を表示します。

## クレジットとライセンス

- プレーヤーとツールの元コードは [ものラジオ](https://github.com/monoradio102/myradio) の MIT ライセンスです。著作権表示と許諾文は [LICENSE](LICENSE) にあります。
- キャラクター画像は元プロジェクトの利用条件に基づいて使用しています。 [素材の利用条件](https://github.com/monoradio102/myradio#ライセンス)
- ローカル放送の音声は COEIROINK:リリンちゃん（Lusty*Kiss Production）です。 [音声の利用条件](https://coeiroink.com/character/audio-character/lilin-m) · [COEIROINK の利用規約](https://coeiroink.com/terms)
- 同梱サンプルの音声は HTS Voice「Mei」 © 2009–2013 名古屋工業大学（MMDAgent Project Team）です。 [音声モデルのライセンス](https://github.com/r9y9/pyopenjtalk/blob/master/pyopenjtalk/htsvoice/LICENSE_mei_normal.htsvoice) · [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)
- 天気は Open-Meteo（CC BY 4.0）、地震は気象庁と USGS の公開情報を使用します。 [天気の利用条件](https://open-meteo.com/en/terms) · [気象庁の地震情報](https://www.jma.go.jp/bosai/map.html#contents=earthquake_map) · [USGS の地震データ](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)
- 地図の海岸線は Natural Earth のパブリックドメインデータを使用しています。 [Natural Earth の利用条件](https://www.naturalearthdata.com/about/terms-of-use/)
