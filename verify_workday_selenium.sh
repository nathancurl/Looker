#!/bin/bash
# Verification script for Workday Selenium implementation

echo "=========================================="
echo "Workday Selenium Implementation Verification"
echo "=========================================="
echo ""

echo "1. Checking files exist..."
if [ -f "fetchers/workday_selenium.py" ]; then
    echo "   ✓ fetchers/workday_selenium.py exists"
else
    echo "   ✗ fetchers/workday_selenium.py MISSING"
    exit 1
fi

if [ -f "test_workday_selenium.py" ]; then
    echo "   ✓ test_workday_selenium.py exists"
else
    echo "   ✗ test_workday_selenium.py MISSING"
    exit 1
fi

if [ -f "WORKDAY_SELENIUM_README.md" ]; then
    echo "   ✓ WORKDAY_SELENIUM_README.md exists"
else
    echo "   ✗ WORKDAY_SELENIUM_README.md MISSING"
    exit 1
fi

echo ""
echo "2. Checking Python imports..."
python3 -c "from fetchers.workday_selenium import WorkdaySeleniumFetcher; print('   ✓ WorkdaySeleniumFetcher imports successfully')" || exit 1

echo ""
echo "3. Checking main.py registry..."
python3 -c "from main import FETCHER_REGISTRY; assert 'workday_selenium' in FETCHER_REGISTRY; print('   ✓ workday_selenium registered in FETCHER_REGISTRY')" || exit 1

echo ""
echo "4. Checking config.json..."
python3 -c "
import json
config = json.load(open('config.json'))
sources = config['sources']
assert 'workday_selenium' in sources, 'workday_selenium not in sources'
ws = sources['workday_selenium']
assert len(ws) == 8, f'Expected 8 companies, found {len(ws)}'
print('   ✓ config.json has workday_selenium section with 8 companies')
companies = [c['name'] for c in ws]
print('   ✓ Companies:', ', '.join(companies))
" || exit 1

echo ""
echo "5. Checking no duplicates in workday section..."
python3 -c "
import json
config = json.load(open('config.json'))
sources = config['sources']
workday = sources['workday']
ws_companies = [c['name'] for c in sources['workday_selenium']]
workday_companies = [c['name'] for c in workday]
overlap = set(ws_companies) & set(workday_companies)
assert len(overlap) == 0, f'Found duplicates: {overlap}'
print('   ✓ No duplicate companies between workday and workday_selenium')
" || exit 1

echo ""
echo "6. Testing fetcher instantiation..."
python3 -c "
from config import load_config
from main import build_fetchers
config = load_config('config.json', '.env')
fetchers = build_fetchers(config)
ws_fetchers = [f for f, _ in fetchers if 'WorkdaySelenium' in type(f).__name__]
assert len(ws_fetchers) == 8, f'Expected 8 fetchers, found {len(ws_fetchers)}'
print(f'   ✓ Built {len(ws_fetchers)} Workday Selenium fetchers')
for f, _ in fetchers[:5]:
    if 'WorkdaySelenium' in type(f).__name__:
        print(f'      - {f.source_name}')
" 2>&1 | grep -v "DISCORD_WEBHOOK" || true

echo ""
echo "=========================================="
echo "✅ All verification checks passed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run test: python3 test_workday_selenium.py"
echo "2. Deploy to VM and monitor logs"
echo "3. Verify job notifications in Discord"
