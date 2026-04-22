# Industrial Equipment Digital Twin

工业设备数字孪生管线：后端 Flask API、Excel 设备数据、场景 JSON、前端 2D/3D 预览（Three.js）。

## 源码与仓库

- **你的 GitHub 仓库列表**：<https://github.com/victor-224?tab=repositories>
- **本项目仓库**：<https://github.com/victor-224/Bowen-Li>

克隆到本地：

```bash
git clone https://github.com/victor-224/Bowen-Li.git
cd Bowen-Li
```

## 环境

- Python 3.10+（建议）
- 浏览器（前端通过本地 HTTP 访问，不要用 `file://` 直接打开 `index.html`）

安装依赖：

```bash
pip install -r requirements.txt
```

## 本地运行 Web（两个端口）

| 服务 | 地址 | 说明 |
|------|------|------|
| 后端 API | <http://127.0.0.1:5000> | Flask，提供 `/api/equipment`、`/api/scene` |
| 前端页面 | <http://127.0.0.1:3000> | 静态文件 + 调用上面 API |

**终端 1 — 启动后端**

```bash
python -m backend.api
```

**终端 2 — 启动前端**

```bash
cd frontend
python -m http.server 3000 --bind 127.0.0.1
```

在浏览器打开：**<http://127.0.0.1:3000>**（或 `http://localhost:3000`）。

**一键脚本**（仓库根目录）：

```bash
chmod +x scripts/dev.sh   # 仅需执行一次
./scripts/dev.sh
```

同样用浏览器访问 **3000** 端口。

## 数据文件

- Excel：`data/Copy of Annexe 2_Equipment_liste_et_taille.xlsx`（后端读取，前端不直连文件）
- 平面图：`data/plan_hd.png`（采点等功能用）

## 其它命令

- 引擎管线（无 UI）：`python -m backend.main`
- 交互采点（需图形界面）：`python -m backend.pickpoint`

## 许可

以仓库内 LICENSE 为准（若未添加则待补充）。
