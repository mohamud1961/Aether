# Browser sidecar image for Core's `browser` tool (browser.BROWSER_IMAGE). Build on the run host:
#   docker build --network host -t aether-browser:2 aether-core/images/browser
# Playwright must match what browser_session_src uses: Page.aria_snapshot(mode="ai") and the aria-ref= selector need
# the 1.6x line (qualified on 1.64.1, receipts/browser-session-e2e.json). aether-browser:1 on the GCP host (built 5 Nov)
# had Playwright 1.49.1, where snapshot() raised AttributeError. The image check at sidecar start states a mismatch.
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble
ENV BROWSER_USE_HEADLESS=true BROWSER_USE_DISABLE_EXTENSIONS=true ANONYMIZED_TELEMETRY=false \
    BROWSER_USE_CLOUD_SYNC=false
RUN pip install --no-cache-dir --break-system-packages playwright==1.64.1 browser-use==0.13.14 \
 && python3 -c "import playwright, browser_use; from playwright.sync_api import Page; assert hasattr(Page, 'aria_snapshot'); print('ok')"
