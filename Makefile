.PHONY: audit shorts longform render upload

audit:
	@echo "Checking required environment variables..."
	@grep -o '^[^#]*=' .env.example | sed 's/=//' | while read var; do \
		if ! grep -q "^$$var=" .env; then \
			echo "WARNING: $$var is not set in .env"; \
		fi \
	done
	@echo "Audit complete."

shorts:
	@echo "Running Shorts pipeline (main_breaking.py)..."
	python main_breaking.py

longform:
	@echo "Running Long-form pipeline (main_daily.py)..."
	python main_daily.py

render:
	@echo "Rendering with Remotion..."
	node remotion/render.mjs --composition $(COMPOSITION) --data $(DATA) --output $(OUTPUT)

upload:
	@echo "YouTube Upload target (placeholder)"
	# To be implemented with YouTube upload module

schedule:
	@echo "Scheduling topics..."
	python scripts/schedule_week.py "$(TOPICS)"

auth-test:
	@echo "Testing YouTube Authentication..."
	python -c "from uploader.youtube_uploader import YouTubeUploader; u = YouTubeUploader(); print('Auth OK:', u.test_connection())"

preflight:
	@echo "Running Pre-Launch Checklist..."
	python scripts/preflight_check.py
