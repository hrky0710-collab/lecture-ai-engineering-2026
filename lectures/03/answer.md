# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：第1回の `app.ask` は講座の宿題の「3レベル」を知らず、一般論で「基礎・応用・発展の難易度別の3段階」と答えていた。第3回の `app.agent` は答える前に `search_glossary` で用語集を引き、用語集の定義に沿って答え、最後に「関係する回：第2回」を付けた（「LoRAとQLoRAの違いは？」で確認。回答の LoRA・QLoRA の説明は data/glossary.json の定義と一致していた）。
- `--trace` で見えたツール呼び出し（ツール名と引数）：
  ```
  [tool call]   search_glossary({'query': 'LoRA'})
  [tool call]   search_glossary({'query': 'QLoRA'})
  [tool return] search_glossary -> [{"term": "LoRA", "lecture": 2, ...
  [tool return] search_glossary -> [{"term": "QLoRA", "lecture": 2, ...
  ```
  docstring の「query には調べたい用語を1つだけ入れる」に従い、2つの用語を別々に検索していた。
- 1つの質問での LLM 呼び出し回数（`requests`）：2回（`requests=2, tool_calls=2`）。1回目でツール呼び出しを依頼し、2回目でツールの結果を読んで回答を書いている。2つの検索は1回のリクエストでまとめて依頼されていた。
- 追加したツールと、docstring に書いた説明：`make_quiz(lecture: int)`。指定した回の用語から1つを `random.choice` で選び、「○○の意味は？」という問題と、用語集の定義を答えとして JSON で返す。docstring には「『第2回の確認問題を出して』のように、復習用の問題を求められたときに使う」と使う場面を書いた。存在しない回（例: 0）では、問題を作れる回の一覧を返して落ちないようにした。INSTRUCTIONS にも「確認問題・復習問題を求められたら make_quiz を使う」を足した。
  - 確認（`--trace "第2回の内容から確認問題を1問出して"`）：
    ```
    [tool call]   make_quiz({'lecture': 2})
    [tool return] make_quiz -> {"lecture": 2, "question": "「エポック」の意味は？", "answer": "学習データ全体を1周学習することを1エポックと数える。..."}
    [usage] RunUsage(... requests=2, tool_calls=1)
    ```
  - モデルは問題文だけを表示し、答えは書かなかった。INSTRUCTIONS の「答えそのものは書かず、ヒントで導く」が効いたと考えられる。

## 宿題

- 取り組んだレベル：実装
- やったこと：
  - `app/tools.py` に `save_learning_log(title: str, content: str)` を追加した。`learning_log/` に「日時_題名.md」で Markdown を保存する。題名のファイル名に使えない文字は `_` に置き換え、本文が空なら保存しない。
  - `app/agent.py` で `agent.tool_plain(tools.save_learning_log, requires_approval=True)` として登録し、エージェントの `output_type` を `[str, DeferredToolRequests]` にした。
  - CLI に `run_with_approval()` を追加した。結果が `DeferredToolRequests` のときは、呼ばれようとしているツール名と引数を表示して `y/N` で聞き、`build_results(approvals=...)` で作った `DeferredToolResults` と `message_history` を渡して続きを実行する（複数回止まっても while で繰り返す）。
  - `tests/test_lec03_homework.py` に TestModel を使ったテストを書いた（承認待ちで止まること・承認したときだけファイルができること・拒否したらできないこと・make_quiz）。保存先は monkeypatch で一時フォルダに差し替え、本物の `learning_log/` を汚さないようにした。
  - 既存の `tests/test_agent.py` は「ツール呼び出しの数 = ツール結果の数」を確かめていたが、承認待ちのツールは承認されるまで結果が無いので、承認待ちの数を足して比べるように直した。
- 結果：
  - `uv run pytest -q`：`16 passed in 4.00s`
  - 承認した場合（`--trace "今日学んだ「エージェント＝モデル＋ループ＋ツール」を学習ログに記録して"` → y）：
    ```
    [承認待ち] save_learning_log({'content': '...', 'title': '...'})
    このツールを実行してよいですか？ [y/N]: y
    --- trace ---
    [tool call]   save_learning_log({'content': 'エージェントの基本構成について学んだ。...', 'title': 'エージェントの基本構成（モデル・ループ・ツール）'})
    [tool return] save_learning_log -> 保存しました: learning_log/20261109-053648_エージェントの基本構成（モデル・ループ・ツール）.md
    [usage] RunUsage(... requests=1, tool_calls=1)
    ```
  - 拒否した場合（同じ質問 → n）：
    ```
    [tool call]   save_learning_log({'title': 'エージェントの基本構成（モデル・ループ・ツール）', 'content': '## 学んだこと ...'})
    [tool return] save_learning_log -> The tool call was denied.
    [usage] RunUsage(... requests=1)
    ```
    `ls learning_log` の結果は承認時の1ファイルだけで、拒否したときはファイルが作られていないことを確認した。
- 気づき・疑問：
  - 承認待ちのツールを呼ぶと実行はそこで一度終わり、続きは「それまでの会話履歴＋承認結果」を渡して新しく実行し直す形になる。LLM はステートレスなので、止めて再開するにも履歴を全部渡す必要があるのだと分かった。
  - 拒否すると、モデルには「The tool call was denied.」がツールの結果として返る。ツールを止めても会話自体は続けられる。拒否時は `tool_calls` が数えられていなかった（実行されていないため）。
  - `[usage]` の `requests` は承認の前後で計2回 LLM を呼んでいるはずなのに 1 と表示された。再開した2回目の実行分だけが数えられているためだと考えられる。料金やレート制限を見積もるときは、止まった回の分も足す必要がある。
  - INSTRUCTIONS には「必ず search_glossary で用語集を確認する」とあるのに、記録の依頼では用語集を引かずにすぐ保存しようとした。また、承認時と拒否時で保存しようとした本文が毎回違った。指示は必ず守られるとは限らず、出力も毎回変わる。だから取り消しにくい操作は、モデルの判断に任せずにループの外側（`requires_approval=True`）で止めるのが安全だと感じた。
  - ファイル名の日時が 05:36 になっていた。Codespaces の時刻が UTC（日本時間 −9 時間）のためで、日本時間にするにはタイムゾーンを指定する必要がある。
  - 疑問：承認時に引数を書き換えて実行させる（`ToolApproved(override_args=...)`）使い方は、実際のアプリでどの程度使われるのか。
