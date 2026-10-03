# CHANGELOG — 依赖启动自检修复（新电脑上「psutil 未安装」）（2026-10-03）

## 现象

在「另一台电脑 / 其他项目副本」上启动时报缺少 psutil：
托盘入口报 `ModuleNotFoundError: No module named 'psutil'`，或运行日志里
CPU 压力监测提示 `psutil is not installed`；每台新机器/新副本都会遇到。

## 根因

- `psutil` 自 2026-08-10 起就在 `app/requirements.txt` 中（`psutil>=5.9,<8`），
  且在各 Python 版本（3.10–3.14）上都能正常安装——**不是清单缺条目**。
- 问题在「依赖同步是否执行」：`RUN.bat` 用
  `app/.requirements.installed`（上一次安装后复制的标记文件）与
  `app/requirements.txt` 做**字节比对**来决定是否跳过安装。
- 但该标记文件会**随项目拷贝一起传播**（整包复制 app/frontend/plugins 到
  另一台电脑时它也在其中），于是新代码带来的 requirements 变更被判定为
  「没有变化」，`pip install` 被跳过；从旧环境升上来的机器**此后新增的依赖
  永远不会被补装**。
- `psutil` 是 8 月后新增、且被托盘启动器/启动入口**急切导入**的第一个依赖，
  所以每台机器都先撞到它（9 月新增的 `jsonschema` 为懒加载，未被注意）。
- 另：`app/check_requirements.py` 旧实现为每个包起一个 `pip show` 子进程，
  实测单次 **>300 秒超时**，无法用于每次启动，这也是当初用标记文件「抄近路」
  的原因。

## 修复

- `app/check_requirements.py`：改为单进程 `importlib.metadata` 快检
  （PEP 503 归一化名称匹配，并校验已安装版本是否满足版本约束；成功静默、失败列清单、退出码不变；缺少
  `packaging` 的全新环境给明确提示）。**实测 ~2.3s（旧版 >300s 超时）。**
- `RUN.bat`：不再用标记文件判定跳过；**每次启动真实校验当前解释器环境**，
  有缺失或版本不满足要求即 `pip install -r requirements.txt`，安装后复核一次；
  `.requirements.installed` 仅在安装成功后写回作记录，不再具备跳过效力。
- `RUN.sh`：同步加入启动前校验与补装、失败时报错退出（Ubuntu/macOS）。
- `tests/test_check_requirements.py`：新增丢失检测、PEP 503 归一化、
  main() 退出码用例。

## 验证

- 新自检（本机内置 Python）：静默、退出码 0、约 2.3s。
- `pytest tests/test_check_requirements.py`：14 通过，包含上下界、固定版本、排除版本、兼容版本及清单变更后已有包不满足要求的回归。
- `RUN.bat` 分支演练（stub 版，不安装不启动）：
  - 环境满足 → 静默直进启动分支；
  - 缺依赖 → 列出缺失项 → 进入安装分支 → 装后复核仍缺则中止并报错（exit 1）。

## 附注（新机器的 Python 版本）

现行固定版本中 `pymupdf==1.24.0`、`orjson==3.9.0`、`pandas==2.2.0`、
`tokenizers==0.15.0`、`matplotlib==3.9.0`、`tiktoken==0.9.0` 在
**Python 3.13 / 3.14 上没有 wheel**（pip 将尝试源码编译，普通新电脑会失败）。
新电脑若使用系统 Python，建议 3.10–3.12；或后续单独评估升级这几个包。
