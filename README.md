# Industrial Equipment Digital Twin (Auto Pipeline)

用户只需把文件放到 `data/`，系统自动识别并生成 3D 场景。

## 核心特性

- 自动文件分类（layout / excel / reference / gad / structure）
- PDF 自动转图（layout page -> runtime/layout.png）
- OCR 驱动设备定位（图纸决定坐标）
- Excel 属性融合（Excel 只补属性）
- 墙体/房间解析与空间关系计算
- Three.js 实时渲染（localhost:3000）

## 数据目录（任意命名）

把文件直接放进 `data/`，无需固定文件名：

- 二维布局图：PDF / PNG / JPG
- 设备清单：XLSX
- 参考图：PDF
- GAD：PDF
- 结构/墙体图：PDF / PNG

系统会自动分类并写入 `data/runtime/` 缓存文件。

## 必须使用的启动命令

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

启动后端（5000）：

```bash
python3 -m backend.api
```

启动前端（3000）：

```bash
cd frontend
python3 -m http.server 3000
```

打开浏览器：`http://localhost:3000`

## 使用方式（零手动配置）

1. 把文件丢进 `data/`
2. 启动后端与前端
3. 打开 `localhost:3000`
4. 点击【加载项目】（或直接调用 API）
5. 系统自动完成：
   - 文件识别
   - PDF 转图
   - OCR 定位
   - Excel 属性融合
   - 墙体解析
   - 关系计算
   - 3D 场景更新

## 主要 API

- `GET /api/files`：当前识别文件
- `GET /api/status`：文件完整性状态
- `GET /api/scene`：场景数据
- `GET /api/relations`：空间关系
- `GET /api/walls`：墙体/房间/中心
- `GET /api/pipeline`：统一总输出 `{scene, relations, walls}`
- `POST /api/upload`：上传并自动重算

## 说明

- 在无 GUI 服务器环境下，如果 OCR 无法识别且无法人工采点，接口会返回结构化错误信息。
