# My Radio

ニュースの見出しと概要を集め、日本語の短い番組にするスマホ向けラジオです。元のキャラクターとプレーヤーで、音声、字幕、台本、元記事を確認できます。配信枠は日本時間の **07:00・12:00・18:00** です。同じ日の回も番組一覧から選べます。

## スマホで聴く

HTTPS で配信したページをスマホで開きます。iPhone は Safari の共有メニューから「ホーム画面に追加」を選び、「Webアプリとして開く」をオンにします。Android は Chrome のメニューから「ホーム画面に追加」または「インストール」を選びます。ニュースの再生にはネット接続が必要です。

## デモを試す

Python 3 が入っている端末で、このフォルダーを開いて以下を実行し、ブラウザーで [デモを開きます](http://127.0.0.1:8000/) 。日本語のデモ音声が2回分入っています。

```sh
python -m http.server 8000 --bind 127.0.0.1
```

## ニュースを登録して番組を作る

- [news.json](news.json) に、NHK、Yahoo!ニュース、朝日新聞、毎日新聞、時事通信、FNN、東洋経済オンライン、Impress Watch、nippon.com、デジタル庁の公式 RSS を登録しています。差し替える場合は媒体名と公開 RSS／Atom URL を設定します。
- 各回は最大4件。フィードの見出し・説明から日本語の要約を作り、元記事のリンクを付けます。直近の回で扱った同じ記事 URL は除外します。新着がなければ前の回を保持します。
- 標準設定は OpenAI API で要約をまとめて1回生成し、Open JTalk で日本語の合成音声を作ります。音声と同じ台本から字幕のタイミングを計算します。OpenAI API の利用料金が発生します。キーは環境変数または GitHub の Actions シークレット `OPENAI_API_KEY` に設定します。
- キーなしで個人的に試す場合は、設定ファイルのコピーで `summary_mode` を `extractive` に変更して `--config` で指定します。このモードは RSS の説明から短い一文を抜き出して読み上げます。説明のある記事が対象です。

Python 3.12 で番組だけをローカル生成する例です。出力先は新しいフォルダーを指定します。結果には番組一覧、台本 JSON、MP3 が入ります。

```sh
python -m pip install -r tools/requirements.txt
python tools/broadcast.py --slot 07:00 --output-dir ../radio-preview
```

## 定時配信を始める

現在のフォークは公開リポジトリです。GitHub Pages の番組や GitHub Actions にアップロードした試聴用ファイルも閲覧可能になります。個人で確認する場合は上記のローカル生成を使い、一般公開する場合は媒体ごとの利用条件と番組の内容を確認してください。記事本文や画像は取得せず、フィードで確認できる事実を自分の言葉で要約して出典を添える設計です。

1. PR を取り込んだ後、フォークの **Actions** を有効にし、**Settings → Secrets and variables → Actions** で `OPENAI_API_KEY` を登録します。
2. 公開する場合は **Settings → Pages → Source → GitHub Actions** を選びます。**Actions → My Radio broadcast → Run workflow** で放送枠を選び、プレビューを外すと手動で公開します。プレビューを選んだ場合は `radio-preview` をダウンロードできます。展開したフォルダーでデモと同じサーバー起動コマンドを使います。
3. 定時公開を有効にするには、Actions のリポジトリ変数 `BROADCAST_ENABLED` を `true` に設定します。時刻は [ワークフロー](.github/workflows/broadcast.yml) と [局の表示設定](station.json) にあります。GitHub Actions の混雑時は開始が遅れる場合があります。

台本と直近30日分の公開用音声は、放送専用の `broadcast-data` ブランチに保存されます。プレーヤーは音声の公開期間が過ぎた回も台本を表示します。

## クレジットとライセンス

- プレーヤーとツールの元コードは [ものラジオ](https://github.com/monoradio102/myradio) の MIT ライセンスです。著作権表示と許諾文は [LICENSE](LICENSE) にあります。
- キャラクター画像は元プロジェクトの利用条件に基づいて使用しています。 [素材の利用条件](https://github.com/monoradio102/myradio#ライセンス)
- デモと自動放送の合成音声は HTS Voice「Mei」 © 2009–2013 名古屋工業大学（MMDAgent Project Team）を使っています。 [音声モデルのライセンス](https://github.com/r9y9/pyopenjtalk/blob/master/pyopenjtalk/htsvoice/LICENSE_mei_normal.htsvoice) · [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)
