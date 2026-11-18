# Herdr Codex Images

[English](README.md)

在 Codex CLI 回覆中直接預覽圖片，並在 Herdr 點擊終端圖片查看清晰原圖。
同一個專案維護 Herdr、Codex 兩個可分別使用的原生元件。

**目前為原始碼預覽版。** 已公開完整修補檔、相容版本、驗證紀錄及修補工具。
預先編譯套件、一鍵安裝與 plugin marketplace 入口仍是後續項目；首版沒有提供
可直接安裝的二進位檔。這是獨立整合專案，並非 Herdr 或 OpenAI 官方版本。

## 功能

- Codex 回覆完成後，直接顯示本機圖片連結、Markdown 圖片及反引號中的圖片路徑。
- 多張圖片依序顯示，相同檔案去重；保留原本說明、搜尋與複製內容。
- 在 Herdr 點擊圖片開啟預覽，透過既有連線從終端所在機器讀取原圖。
- 支援 Fit／`0`、100%／`1`、`+`／`-`、捲動、拖曳及 `Esc` 關閉。

Codex 元件可在支援圖片協定的其他終端獨立使用。Herdr 元件可獨立查看終端傳入的
圖片像素；讀取完整原檔則需要 Codex 元件提供的原圖參照。

## 已驗證組合

| 元件 | 上游版本 | 測試環境 |
| --- | --- | --- |
| Herdr app | v0.1.16 | Windows x64、macOS Apple Silicon |
| Codex CLI | rust-v0.169.1 | macOS Apple Silicon |
| 遠端原圖 | 既有 Herdr core 連線 | Windows 用戶端 → macOS 主機 |

精確 commit 與修補檔 SHA-256 見 [manifest.json](manifest.json)。其他平台及版本尚未驗證。

## 使用原始碼

先取得本專案，再依元件說明複製指定版本的上游原始碼：

```sh
git clone https://github.com/yanzzzzzzzzz/herdr-codex-images.git
cd herdr-codex-images
```

- [Herdr 建置方式](components/herdr/README.md)
- [Codex 建置方式](components/codex/README.md)

工具需要 Python 3.9+ 及 Git。`python tools/patch_component.py --validate` 可驗證兩份
修補檔；套用時會檢查 SHA-256、上游 commit 與工作目錄是否乾淨。
工具只修改指定的原始碼 checkout，不安裝程式、不修改 shell 設定，也不重啟現有工作階段。

## 限制與驗證

圖片必須存在於 Codex 所在機器；不自動下載 HTTP(S) 圖片。每則回覆最多預覽 8 張
不同圖片，程式碼區塊中的範例不觸發預覽。回覆預覽高度約為終端三分之一，上限 12 列。
遺失或無法解碼的檔案保留文字連結。

CLI 沿用上游 32 MiB 限制；Herdr 原圖讀取的檔案上限為 32 MiB、解碼像素預算 64 MiB。
部署後需啟動新的 Codex 程序；舊程序中的 `/new` 不會更換執行檔。

測試範圍見 [驗證紀錄](docs/validation.md)，設計見 [架構](docs/architecture.md)。
終端圖片繪製能力已有上游實作；本專案延伸一般回覆的圖片檔案預覽與 Herdr 原圖互動。

## 後續發布

規劃將 plugin 安裝入口與原生執行元件分開：由 setup／doctor／uninstall 管理安裝，
GitHub Releases 提供分平台套件與雜湊。詳細範圍見 [發布規劃](docs/distribution.md)。

Apache-2.0；上游授權與聲明收錄於 [licenses](licenses/)。
