# AI 音檔分割工具

Windows 桌面工具，自動將音檔依語音停頓切割成句子、AI 辨識文字，支援調整分割點、合併句子、跨音檔批次匯出。

---

## 功能對照需求

| 需求 | 狀態 | 說明 |
|------|------|------|
| 匯入多個音檔 | ✅ | mp3 / wav / m4a，匯入即自動排隊處理 |
| 自動依語音停頓分割 | ✅ | faster-whisper VAD 靜音偵測 |
| AI 辨識每句文字 | ✅ | faster-whisper CPU 模式，支援中文、台語、英文等 |
| 顯示波形圖 | ✅ | pyqtgraph 波形，紫色區域可拖曳調整分割點 |
| 播放單句 / 全部 | ✅ | 點擊句子的 ▶ 按鈕或「播放全部」 |
| 手動調整分割點 | ✅ | 拖曳波形區域邊框微調開始/結束時間 |
| 選取多句合併 | ✅ | 勾選連續句子後點「合併選取」 |
| 批次匯出音檔 | ✅ | wav / mp3 / m4a，自動以辨識文字命名 |
| 檔名規則 | ✅ | 使用辨識文字，自動清理非法字元 |
| 輸出 metadata.json | ✅ | 含 text / start / end / file |
| CPU 模式（免 GPU）| ✅ | int8 量化，普通電腦可執行 |
| 辨識結果快取 | ✅ | 存成 `.segments.json`，重開不需重新辨識 |

---

## 安裝指南（工程師版）

### 系統需求
- Windows 10 / 11
- Python 3.10+（建議 3.11）
- 網路連線（首次下載 AI 模型用）

### 步驟

**1. 安裝 Python**

前往 https://www.python.org/downloads/ 下載安裝。
安裝時勾選「Add Python to PATH」。

**2. 安裝 ffmpeg**

```
winget install ffmpeg
```
或手動下載：https://ffmpeg.org/download.html（解壓後將 bin 資料夾加入 PATH）

**3. 安裝 Python 套件**

```bash
pip install -r requirements.txt
```

**4. 執行**

```bash
python main.py
```

---

## 安裝指南（PM / 非工程師版）

> 以下步驟假設電腦上尚未安裝任何開發工具，請依序執行。

### 第一步：安裝 Python

1. 打開瀏覽器，前往 👉 https://www.python.org/downloads/
2. 點擊黃色大按鈕「Download Python 3.x.x」
3. 開啟下載的安裝檔
4. **重要**：勾選畫面下方的 ☑ **「Add Python to PATH」**
5. 點擊「Install Now」，等待安裝完成

### 第二步：安裝 ffmpeg（處理 mp3/m4a 必須）

1. 同時按下鍵盤 `Windows鍵 + R`，輸入 `cmd`，按 Enter
2. 在黑色視窗中輸入以下指令並按 Enter：
   ```
   winget install ffmpeg
   ```
3. 等待安裝完成，看到「Successfully installed」即可

> 如果 winget 指令無法使用，請改至 https://www.gyan.dev/ffmpeg/builds/ 下載 `ffmpeg-release-essentials.zip`，解壓後將 `bin` 資料夾路徑加入系統 PATH。

### 第三步：安裝工具套件

1. 再次開啟命令提示字元（`Windows鍵 + R` → 輸入 `cmd`）
2. 用 `cd` 指令切換到工具所在資料夾，例如：
   ```
   cd "D:\Audio Sentence Cutter"
   ```
3. 輸入以下指令並按 Enter：
   ```
   pip install -r requirements.txt
   ```
4. 等待所有套件安裝完畢（約 1–3 分鐘）

### 第四步：啟動工具

在同一個命令提示字元視窗輸入：
```
python main.py
```

程式視窗會出現。之後每次要開啟，重複第四步即可。

> **第一次使用時**，工具會自動從網路下載 AI 語音辨識模型（約 500MB），需要等待數分鐘，這只需要做一次。

---

## 使用方式

### 基本流程

1. **匯入音檔**
   - 點擊左側「＋ 匯入音檔」，選取一個或多個 mp3 / wav / m4a 檔案
   - 匯入後工具自動在背景排隊載入並辨識，無需等待即可繼續匯入其他檔案

2. **等待處理完成**
   - 左側列表會顯示每個檔案的狀態：
     - ⏳ 排隊中
     - 📂 載入中
     - 🎙 辨識中
     - ✓ 完成（綠色，此時才可點擊）
     - ✗ 失敗（紅色，可點「重新辨識」重試）

3. **選取音檔**
   - 點擊左側已完成（✓）的音檔，波形與句子列表自動顯示

4. **調整分割點**
   - 點擊句子列表中的某一行，波形上的紫色區域會跳到該句子
   - 拖曳紫色區域的左右邊框，微調句子的開始/結束時間
   - 時間欄位也可直接點兩下修改數字

5. **播放**
   - 點擊句子旁的 ▶ 按鈕：播放該句子
   - 點擊「▶ 播放全部」：播放整個音檔
   - 點擊「⏹ 停止」：停止播放

6. **合併句子**（需連續）
   - 勾選相鄰的句子（勾選框在每一行左側）
   - 點擊「合併選取」
   - ⚠️ 只能合併相鄰的句子，中間不能有未勾選的句子

7. **分割句子**
   - 點擊要分割的句子（點列表行選取）
   - 將波形上的紫色區域拖曳到要切割的位置
   - 點擊「在波形處分割」，分割點為紫色區域的中心

8. **跨音檔選取**
   - 切換音檔時，☑ 勾選狀態會保留
   - 下方工具列顯示「已選取 N 句（跨 M 個音檔）」
   - 左側列表會顯示每個音檔的勾選數量，例如 `audio1.mp3 [3]`

9. **匯出**
   - 「匯出選取」：匯出所有有打勾的句子（支援跨音檔）
   - 「匯出全部」：匯出當前音檔的所有句子
   - 選擇輸出資料夾與格式（wav / mp3 / m4a）
   - 自動輸出 `metadata.json`（含文字、時間、檔名）

---

## AI 模型說明

| 模型 | 下載大小 | 速度 | 建議情境 |
|------|---------|------|---------|
| tiny | ~75 MB | 最快 | 快速測試 |
| base | ~150 MB | 快 | 英文為主 |
| **small**（預設）| ~500 MB | 中 | 中文/台語推薦 |
| medium | ~1.5 GB | 慢 | 最高精度 |

模型自動下載到 `C:\Users\你的帳號\.cache\huggingface\hub\`，只需下載一次。

---

## 打包為 exe（給工程師）

```bash
pip install pyinstaller
build.bat
```

打包完成後 exe 位於 `dist\AI音檔分割工具.exe`。

> 打包後仍需在目標電腦安裝 ffmpeg，才能處理 mp3/m4a 格式。

---

## 專案結構

```
D:\Audio Sentence Cutter\
├── main.py                        # 程式入口
├── ui\
│   ├── main_window.py             # 主視窗、佇列管理、所有 UI 邏輯
│   └── waveform_widget.py         # 波形圖元件（pyqtgraph）
├── core\
│   ├── audio_loader.py            # 音檔載入 + numpy 轉換
│   ├── transcriber.py             # faster-whisper 語音辨識
│   └── exporter.py                # 音檔與 metadata.json 匯出
├── utils\
│   ├── filename_cleaner.py        # 清理非法檔名字元
│   └── ffmpeg_helper.py           # ffmpeg 路徑偵測與設定
├── requirements.txt
├── build.bat                      # PyInstaller 打包腳本
└── README.md
```

---

## 常見問題

**Q：出現「找不到 ffmpeg」或「WinError 2」**
A：需要安裝 ffmpeg。或點左側面板的「⚙ 設定 ffmpeg」手動指定 `ffmpeg.exe` 路徑。

**Q：第一次辨識很慢**
A：首次使用需下載 AI 模型（約 500MB），之後會快很多。

**Q：辨識完一直是「排隊中」沒有變化**
A：請確認網路正常（下載模型需要連線），以及 ffmpeg 已安裝（wav 格式可跳過 ffmpeg）。

**Q：匯出的音檔沒有聲音**
A：確認 pydub 和 ffmpeg 安裝正確，wav 格式最穩定，建議優先使用。
