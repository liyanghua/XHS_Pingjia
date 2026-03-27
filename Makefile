# MediaCrawler — 常用命令（含 review_intel 子系统）
.PHONY: help clean-data review-intel-test review-intel-api review-intel-demo review-intel-keyword-pipeline review-intel-xhs-demo review-intel-xhs-capture review-intel-ingest-capture review-intel-runner-xhs-acceptance review-intel-xhs-acceptance-report

# 验收 / 抓取默认落盘目录（与 REVIEW_INTEL_* 未设置时一致）；若你改用环境变量指向其它路径，请自行清理该路径
REVIEW_INTEL_DATA_DIR ?= review_intel_data
REVIEW_INTEL_CAPTURE_DIR ?= review_intel_capture

help:
	@echo "Targets:"
	@echo "  review-intel-test      - pytest review_intel/tests/"
	@echo "  review-intel-api       - uvicorn review_intel.api.app:app (port 8090)"
	@echo "  review-intel-demo      - python review_intel/jobs/runner.py (Dummy 闭环)"
	@echo "  review-intel-keyword-pipeline - 关键词→Runner→清洗→SQLite→打印入库（Dummy，见 README）"
	@echo "  review-intel-xhs-demo  - 小红书真实验收（需登录，见 adapters/README_XHS.md）"
	@echo "  review-intel-xhs-capture - 小红书抓取落盘 manifest+events.jsonl（需登录，见 docs/capture_ingest_layout.md）"
	@echo "  review-intel-ingest-capture - 从 capture 目录 ingest 到 store.db（见 README_review_intel.md）"
	@echo "  review-intel-runner-xhs-acceptance - Runner+SQLite 小范围验收（仅打印 JSON 摘要）"
	@echo "  review-intel-xhs-acceptance-report - 第一轮架构验收（JSON+Markdown 报告）"
	@echo "  clean-data - 清空 review_intel 本地数据目录（见 README_review_intel.md）"

clean-data:
	@echo "Removing $(REVIEW_INTEL_DATA_DIR)/ and $(REVIEW_INTEL_CAPTURE_DIR)/ ..."
	rm -rf "$(REVIEW_INTEL_DATA_DIR)" "$(REVIEW_INTEL_CAPTURE_DIR)"
	@echo "Done. 可重新跑验收以验证抓取与写库（stored_* 计数将反映本次 INSERT）。"

review-intel-test:
	python -m pytest review_intel/tests/ -q

review-intel-api:
	python -m uvicorn review_intel.api.app:app --reload --host 127.0.0.1 --port 8090

review-intel-demo:
	python review_intel/jobs/runner.py

review-intel-keyword-pipeline:
	python -m review_intel.jobs.keyword_pipeline_demo

review-intel-xhs-demo:
	python -m review_intel.adapters.xhs_demo --keyword 防晒 --max-notes 2 --max-comments 3

review-intel-xhs-capture:
	python -m review_intel.jobs.xhs_capture --keyword 防晒 --max-notes 2 --max-comments 3

review-intel-ingest-capture:
	@echo "用法: make review-intel-ingest-capture JOB_ID=your-job-id"
	@test -n "$(JOB_ID)" || (echo "请设置 JOB_ID= 与 xhs_capture 输出目录名一致" && false)
	python -m review_intel.jobs.ingest_capture --job-id "$(JOB_ID)"

review-intel-runner-xhs-acceptance:
	python -m review_intel.jobs.runner_acceptance_demo --db-path review_intel_data/xhs_acceptance/store.db

review-intel-xhs-acceptance-report:
	python -m review_intel.jobs.run_xhs_acceptance --db-path review_intel_data/xhs_acceptance/store.db --output-dir review_intel_data/xhs_acceptance/last_run
