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
- 文の選択、Open JTalk による読み上げ、字幕のタイミング計算はすべて実行環境内で行います。ニュースを取得するときに RSS への通信が必要です。API キーや従量課金の設定は不要です。

Python 3.12 で番組だけをローカル生成する例です。出力先は新しいフォルダーを指定します。結果には番組一覧、台本 JSON、MP3 が入ります。

```sh
python -m pip install -r tools/requirements.txt
python tools/broadcast.py --slot 07:00 --output-dir ../radio-preview
python tools/demo.py --state-dir ../radio-preview --output "../My Radio デモ.html"
```

## 定時配信を始める

現在のフォークは公開リポジトリです。GitHub Pages の番組や GitHub Actions にアップロードしたファイルは閲覧可能になります。個人で使う場合はローカルで生成してください。この方式は RSS の文を抜き出して読み上げるため、一般公開する場合は再利用と配信が許可されたフィードに差し替えてください。

1. フォークの **Actions** を有効にします。**Actions → My Radio broadcast → Run workflow** で試聴版を選ぶと、サンプルだけを含む `radio-demo` をダウンロードできます。ZIP を展開して中の HTML を開きます。
2. 公開する場合は配信可能な RSS に差し替え、`news.json` の `allow_publication` を `true` にします。**Settings → Pages → Source → GitHub Actions** を選び、**Run workflow** で放送枠を選んで試聴版のチェックを外すと手動で公開します。
3. 定時公開を有効にするには、Actions のリポジトリ変数 `BROADCAST_ENABLED` を `true` に設定します。時刻は [ワークフロー](.github/workflows/broadcast.yml) と [局の表示設定](station.json) にあります。GitHub Actions の混雑時は開始が遅れる場合があります。

台本と直近30日分の公開用音声は、放送専用の `broadcast-data` ブランチに保存されます。プレーヤーは音声の公開期間が過ぎた回も台本を表示します。

## クレジットとライセンス

- プレーヤーとツールの元コードは [ものラジオ](https://github.com/monoradio102/myradio) の MIT ライセンスです。著作権表示と許諾文は [LICENSE](LICENSE) にあります。
- キャラクター画像は元プロジェクトの利用条件に基づいて使用しています。 [素材の利用条件](https://github.com/monoradio102/myradio#ライセンス)
- デモと自動放送の合成音声は HTS Voice「Mei」 © 2009–2013 名古屋工業大学（MMDAgent Project Team）を使っています。 [音声モデルのライセンス](https://github.com/r9y9/pyopenjtalk/blob/master/pyopenjtalk/htsvoice/LICENSE_mei_normal.htsvoice) · [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)
