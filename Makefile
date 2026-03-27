# MediaCrawler — 常用命令（含 review_intel 子系统）
.PHONY: help review-intel-test review-intel-api review-intel-demo review-intel-keyword-pipeline review-intel-xhs-demo

help:
	@echo "Targets:"
	@echo "  review-intel-test      - pytest review_intel/tests/"
	@echo "  review-intel-api       - uvicorn review_intel.api.app:app (port 8090)"
	@echo "  review-intel-demo      - python review_intel/jobs/runner.py (Dummy 闭环)"
	@echo "  review-intel-keyword-pipeline - 关键词→Runner→清洗→SQLite→打印入库（Dummy，见 README）"
	@echo "  review-intel-xhs-demo  - 小红书真实验收（需登录，见 adapters/README_XHS.md）"

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
