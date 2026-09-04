# 本地开发

## 前端

```powershell
pnpm.cmd install
pnpm.cmd dev:web
```

浏览器访问 `http://localhost:3000`。

## API

使用 Python 3.12+：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload
```

API 文档位于 `http://localhost:8000/docs`。

## 数据管道

初始化本地数据库与种子定义：

```powershell
.venv\Scripts\python.exe -m app.cli init-db
```

采集四视角 World Bank 种子指标：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-world-bank
```

只采集一个视角：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-world-bank --geography JP
```

美国 BLS 月频数据：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-bls
```

美国财政部日频收益率曲线：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-treasury --start-year 2024 --end-year 2026
```

美国 Census 零售与餐饮销售：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-census-retail
```

日本 BOJ 月频及季度数据：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-boj --start 199001 --end 202608
```

构建指定 cutoff 下的统一月频特征：

```powershell
.venv\Scripts\python.exe -m app.cli build-features `
  --cutoff 2026-08-15T23:59:00+08:00
```

生成机器质量报告：

```powershell
.venv\Scripts\python.exe -m app.cli quality-report --output data/processed/quality-report.json
```

运行中国通胀严格版本回测：

```powershell
.venv\Scripts\python.exe -m app.cli backtest-cn-inflation `
  --start 2024-03 --end 2026-08 `
  --output data/processed/backtest-cn-inflation-v0.1.json
```

从已归档 CPI 页面派生核心 CPI，并运行 v0.2：

```powershell
.venv\Scripts\python.exe -m app.cli derive-nbs-cpi-components
.venv\Scripts\python.exe -m app.cli backtest-cn-inflation-v2 `
  --start 2024-03 --end 2026-08 `
  --output data/processed/backtest-cn-inflation-v0.2.json
```

运行三个子主题的 v0.3：

```powershell
.venv\Scripts\python.exe -m app.cli backtest-cn-inflation-v3 `
  --start 2024-03 --end 2026-08 `
  --output data/processed/backtest-cn-inflation-v0.3.json
```

中国官方 CSV 导入格式必须包含 `date,value` 两列：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-china-csv `
  --indicator-id INDICATOR_ID `
  --path path/to/official.csv `
  --source-url https://data.stats.gov.cn/
```

也可以直接采集国家统计局正式发布页面：

```powershell
.venv\Scripts\python.exe -m app.cli ingest-nbs-release `
  --indicator-id NBS_CN_CPI_YOY `
  --url https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260709_1964084.html
```

从国家统计局公开发布分页回补 CPI 或 PPI：

```powershell
.venv\Scripts\python.exe -m app.cli backfill-nbs-cpi `
  --indicator-id NBS_CN_PPI_YOY --start-page 0 --end-page 32
```

FRED 连接器需要在 `.env` 设置 `FRED_API_KEY`。BLS 在部分网络环境可能被其边缘网关以 403 阻断；采集器会立即失败且不写入伪数据。

## 检查

```powershell
pnpm.cmd lint:web
pnpm.cmd test:web
.venv\Scripts\python.exe -m ruff check apps/api
.venv\Scripts\python.exe -m pytest apps/api/tests
```

## 当前限制

- 首页和 API 使用明确标记的样例数据；
- API 已接入 World Bank、BOJ 和美国财政部真实数据，首页仍未使用这些指标生成状态；
- PostgreSQL 模型已定义，但本迭代不启动生产数据库；
- 个人画像按钮尚未开放。
