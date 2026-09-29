# JustOne 项目开发日志

## 2026-05-26

### 威胁情报模块完善计划

#### 一、现状分析

当前 modules/intelligence/ 目录仅有占位 __init__.py（空 __all__），collect.py 未注册情报模块，settings.py 的 intelligence_enable 字段未被引用。

威胁情报模块定位：区别于搜索引擎（网页抓取）和数据集（特定 API），TI 模块从威胁情报平台获取被动 DNS 数据、域名关联信息，数据来源包括恶意软件分析、沙箱、威胁情报订阅等。

#### 二、计划建设的模块

| 模块 | 来源 | API Key | 优先级 | 说明 |
|------|------|---------|--------|------|
| AlienVault OTX | otx.alienvault.com | 免费注册 | 高 | 被动 DNS + 域名关联，数据量大 |
| URLScan.io | urlscan.io/api | 免费注册 | 高 | 扫描结果中的子域名关联 |
| ThreatCrowd | threatcrowd.org | 无需认证 | 高 | 域名报告 API，接口简单 |
| ThreatMiner | threatminer.org | 无需认证 | 中 | 域名相关子域名查询 |
| VirusTotal | virustotal.com | 需 API Key | 中 | domains/report 端点，数据权威 |
| RiskIQ | community.riskiq.com | 免费注册 | 中 | 被动 DNS + WHOIS 关联 |

#### 三、实施步骤

Phase 1（当天）:
1. 创建 modules/intelligence/alienvault.py — OTX API v2 被动 DNS
2. 创建 modules/intelligence/urlscan.py — URLScan.io 搜索 API
3. 创建 modules/intelligence/threatcrowd.py — ThreatCrowd 域名报告
4. 更新 modules/intelligence/__init__.py — 注册导出
5. 更新 modules/collect.py — 添加 _init_intelligence_modules() + _run_intelligence_modules()
6. 更新 config/settings.py — 添加 OTX/URLScan API 字段
7. 更新 config/.env.example / .env — 添加 API 字段
8. 运行测试验证零回归

Phase 2（后续）:
- 添加 threatminer.py / virustotal_api.py / riskiq_api.py
- 增加模块间结果交叉验证逻辑
- 性能优化（批量查询、缓存）

#### 四、状态更新 — 2026-05-26

已存在模块: alienvault.py, urlscan.py, threatbook.py, virustotal_api.py, threatminer.py
均已注册到 collect.py 的 _init_intelligence_modules()。

VirusTotal 相关改进:
- page_delay / max_pages 从硬编码改为 settings 配置项
- 新增 VIRUSTOTAL_PAGE_DELAY(16) 和 VIRUSTOTAL_MAX_PAGES(50)
- 泛解析检测后自动限流 max_pages: 50→5

#### 五、模块设计模式

与 datasets 模块一致：继承 common.module.Module，run() 返回 Set[str]，通过 modules/__init__.py 导出，collect.py 注册调用。

---

*日期: 2026-05-26*
*状态: VT 配置化完成，模块实现待推进*
