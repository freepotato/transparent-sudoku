# Transparent Killer Sudoku

一个运行在 Windows 上的**透明小窗 Killer Sudoku**：启动后会以“刚刚好”的小窗形式显示
[dailykillersudoku.com](https://www.dailykillersudoku.com/) 当天的 Killer Sudoku 题目，
窗口始终置顶、无边框、背景透明，看起来就像屏幕上浮着几个边框和数字。

题目不是内置题库，而是**实时从网站抓取**：默认加载当天题目，也可以输入题号加载任意一题。

> 仅供个人学习与界面实验使用。题目内容与版权归 dailykillersudoku.com 所有。

---

## 功能

- **实时取题**：直接请求网站接口，无需手动下载或维护题库
- **当天题目一键加载**：自动识别今天发布的普通 Killer Sudoku（跳过 Greater-Than 变体）
- **任意题号**：输入 3~5 位题号即可加载
- **透明无边框置顶窗口**：可拖动、可最小化到系统托盘
- **透明度可调**：10%~100% 整体不透明度
- **颜色可调**：背景、网格线、Cage 边界、数字、Cage 求和数值均可单独选色（支持 alpha）
- **格子大小可调**：25~80 px
- **完整解题交互**：鼠标选格、键盘输入、方向键移动、冲突高亮
- **托盘常驻**：隐藏窗口后可从托盘快速恢复或直接切换到当天题目

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11 |
| Python | 3.9 及以上（已在 3.14 上验证） |
| 网络 | 可访问 dailykillersudoku.com |
| 依赖 | PySide6、requests（见 `requirements.txt`） |

---

## 安装与运行（推荐使用虚拟环境）

在 PowerShell 中执行：

```powershell
cd C:\Users\rfuser\OneDrive\文档\Trae-CN\default\transparent-sudoku

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### 方式二：不激活，直接用虚拟环境里的解释器

这种方式不需要修改 PowerShell 执行策略，也适合做成快捷方式或计划任务：

```powershell
cd C:\Users\rfuser\OneDrive\文档\Trae-CN\default\transparent-sudoku

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### 方式三：双击脚本启动（`run.bat`）

如果希望以后双击就能玩，可在项目根目录新建 `run.bat`：

```bat
@echo off
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "" .\.venv\Scripts\pythonw.exe main.py
```

`pythonw.exe` 不弹出控制台窗口，更符合“小窗做题”的使用场景。

### 常见安装问题

**1. 提示“无法加载文件 Activate.ps1，因为在此系统上禁止运行脚本”**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

或用上面的「方式二」直接调用 `.venv\Scripts\python.exe`。

**2. `pip` 下载很慢**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**3. 虚拟环境不需要提交**

`.venv/` 已在 `.gitignore` 中忽略。

---

## 使用说明

主窗口顶部是自定义标题栏：

| 控件 | 作用 |
| --- | --- |
| **Today** | 加载今天的普通 Killer Sudoku（当天有多题时取第一题） |
| **#** 输入框 + **Go** | 加载指定题号，例如 `872`、`32334` |
| **↺** | 清空所有手动填入的数字 |
| **⚙** | 展开/收起设置面板（透明度、格子大小、颜色） |
| **—** | 隐藏到系统托盘 |
| **✕** | 退出程序 |

窗口无系统标题栏，**按住窗口任意空白处即可拖动**。鼠标点托盘图标可快速显示/隐藏。

### 键盘操作

| 按键 | 作用 |
| --- | --- |
| `1`~`9` | 在当前选中的格子里填入数字 |
| `0` / `Delete` / `Backspace` | 清除当前格子 |
| 方向键 | 移动选中格子 |
| 鼠标点击 | 选中格子 |

填入的数字如果与同行、同列、同宫或同 Cage 的数字重复，格子会自动标红提示。
固定数字（题目给定的）会以粗体显示且不可修改。

### 透明度与配色技巧

- 设置面板里的 **Opacity** 控制整个窗口（含边框和数字）的不透明度。
- 如果只想让数字变淡、让边框保持清晰，用 **Numbers** 颜色按钮，在取色对话框里降低 alpha 值。
- 背景默认是全透明的，若需要一点底色（比如深色屏幕上用白字），给 **BG Color** 设一个较低 alpha 的纯色。

---

## 工作原理

1. 访问 `https://www.dailykillersudoku.com/puzzles/by_date?date=YYYY-MM-DD`，从返回的 HTML 中解析当天的题号；
2. 访问 `https://www.dailykillersudoku.com/puzzle/{id}`，从页面中提取内嵌的题目数据；
3. 题目数据是网站自定义的 Base64 编码格式（棋盘固定数字、Cage 归属、Cage 求和与答案），
   本项目在 `puzzle_fetcher.py` 中完成解码；
4. 本程序只在本地绘制题目，不上报成绩、不写入账号数据。

如果当天还没有发布题目（时区差异或站点延迟），程序会自动回退到前一天查找。

---

## 常见问题

**点击 Today 后一直没反应？**
修复后的版本会在标题栏显示 `⏳` 加载状态和 `⚠` 错误信息。若长时间停在加载状态，通常是网络无法访问该站点。

**提示 `No puzzle found for today`？**
站点当天还没发布题目，或所在网络被拦截。可以先用题号加载，例如输入 `32334`。

**怎么知道题号？**
在网站首页的日历里选择日期，题目列表上会显示 `Puzzle #####`，把数字填进输入框即可。

**窗口找不到 / 关不掉？**
点 **✕** 是退出；点 **—** 只是隐藏到托盘，托盘右键菜单里有 *Show/Hide* 和 *Quit*。

**字太小或太大？**
设置面板里拖动 **Cell size** 滑块，窗口大小会随之适配。

---

## 版本发布

项目使用 [release-please](https://github.com/googleapis/release-please) 自动管理版本与 GitHub Release：

- 所有提交遵循 [Conventional Commits](https://www.conventionalcommits.org/)（`feat:`、`fix:`、`docs:` 等）；
- 推送到 `main` 后，GitHub Actions 会自动创建/更新 release PR；
- 合并 release PR 后自动打 tag（如 `v0.1.0`）并生成 Release 说明。

仓库需要一次性开启两项设置（**Settings → Actions → General**）：

1. **Workflow permissions** 选择 **Read and write permissions**；
2. 勾选 **Allow GitHub Actions to create and approve pull requests**
   （否则 release-please 会报 *GitHub Actions is not permitted to create or approve pull requests*）。

开启后，在 **Actions → Release Please → Re-run all jobs** 重新运行即可生成 release PR。

---

## 项目结构

```
transparent-sudoku/
├── main.py            # 主窗口、设置面板、系统托盘
├── board_widget.py    # 棋盘绘制（网格/Cage 边界/Cage 求和/数字/冲突高亮）
├── puzzle_fetcher.py  # 题目抓取与自定义 Base64 格式解码
├── requirements.txt
├── pyproject.toml
└── .github/workflows/release-please.yml
```
