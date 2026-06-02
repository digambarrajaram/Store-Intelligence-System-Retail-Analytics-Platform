# Dashboard Build Verification Guide

## Quick Start Build Test

This guide verifies all UI fixes are working correctly.

### Step 1: Verify Dependencies

```bash
cd dashboard

# Check package.json has build deps
npm list tailwindcss
npm list postcss
npm list autoprefixer

# Expected output:
# tailwindcss@3.3.5
# postcss@8.4.31  
# autoprefixer@10.4.16
```

### Step 2: Clean Build

```bash
# Remove old build artifacts
rm -rf node_modules dist build .parcel-cache

# Reinstall dependencies
npm install

# Build
npm run build

# Expected:
# ✓ built 1234 modules
# ✓ dist/index.html
# ✓ dist/assets/index-XXXX.css (30-50 KB)
# ✓ dist/assets/index-XXXX.js
```

### Step 3: Verify CSS Generation

```bash
# Check CSS file exists and has size
ls -lh dist/assets/index-*.css

# Expected: something like
# -rw-r--r-- 1 user group 42K Jun 02 12:34 dist/assets/index-abc123.css

# Check CSS contains Tailwind classes
grep "bg-slate-950" dist/assets/index-*.css

# Expected: (empty means Tailwind not generated correctly)
# Should find the class definition
```

### Step 4: Verify HTML References CSS

```bash
# Check index.html links CSS
grep "<link" dist/index.html

# Expected output including:
# <link rel="stylesheet" href="/assets/index-abc123.css">
```

### Step 5: Start Dev Server

```bash
# In dashboard directory
npm run dev

# Expected:
# ➜  Local:   http://localhost:5173/
# ➜  press h to show help
```

### Step 6: Test in Browser

Open browser console (F12) and verify:

1. **No build errors** in Console tab
   - Should see API calls
   - Should NOT see Vite/build errors

2. **CSS loaded** 
   - Check Network tab
   - Find `index-*.css` file
   - Status: 200
   - Size: 30-50 KB

3. **Components render**
   - Dashboard visible with dark theme
   - Cards have rounded corners and shadows
   - Layout is in grid (not stacked)

4. **Data loading logs**
   ```javascript
   // In console, you should see:
   // [OccupancyChart] API Response: {status: 200, payload: {...}, historyCount: 12}
   // [OccupancyChart] Data loaded successfully: {count: 12, containerHeight: 420}
   // [FunnelChart] API Response: {status: 200, payload: [...], count: 4}
   // [FunnelChart] Data loaded successfully: {count: 4, containerHeight: 340}
   ```

5. **Charts render**
   - Occupancy area chart visible
   - Funnel chart visible  
   - Both have proper dimensions
   - No empty white space where charts should be

---

## Production Docker Build

### Build Command

```bash
cd dashboard

# Build image
docker build \
  --arg VITE_API_URL="http://api:8000/api/v1" \
  --arg VITE_WS_URL="ws://api:8000" \
  -t store-intelligence-dashboard:latest .

# Expected output:
# Step 1/X : FROM node:18-alpine
# ...
# Step 12/12 : CMD ["nginx", "-g", "daemon off;"]
# Successfully built abc123def456
```

### Run Docker Container

```bash
docker run -p 3000:3000 \
  -e API_HOST=localhost \
  -e API_PORT=8000 \
  store-intelligence-dashboard:latest

# Expected:
# Container starts
# Nginx listens on 0.0.0.0:3000
```

### Verify Docker Build

```bash
# Get container ID
CONTAINER_ID=$(docker ps | grep dashboard | awk '{print $1}')

# Check CSS was built and copied
docker exec $CONTAINER_ID ls -lh /usr/share/nginx/html/assets/index-*.css

# Expected: ~35 KB CSS file present

# Check build output
docker logs $CONTAINER_ID | tail -20

# Should show nginx startup, no errors
```

---

## Common Issues & Fixes

### Issue: CSS File Not Generated

**Symptoms**:
- No `index-*.css` in dist/assets/
- Dashboard appears unstyled
- Console has no CSS errors

**Fix**:
```bash
# 1. Verify tailwindcss installed
npm list tailwindcss

# 2. Check tailwind.config.js content paths
cat tailwind.config.js

# 3. Rebuild
rm -rf node_modules dist
npm install
npm run build

# 4. Verify CSS generated
ls -lh dist/assets/
```

### Issue: CSS Generated But Not Applied

**Symptoms**:
- CSS file exists (35+ KB)
- Dashboard still unstyled
- No HTML link to CSS

**Fix**:
```bash
# 1. Check Vite config
cat vite.config.ts

# 2. Check index.html links CSS
cat dist/index.html | grep -A5 "head"

# 3. Rebuild Vite
npm run build

# 4. Check dist/index.html explicitly references CSS
grep "index-.*css" dist/index.html
```

### Issue: Charts Not Rendering

**Symptoms**:
- API returns 200
- Data logged in console
- Charts area appears empty/white

**Fix**:
```bash
# 1. Open browser console (F12)
# 2. Check for Recharts errors

# 3. Verify chart heights
document.querySelector('[class*="recharts"]')?.offsetHeight
// Should return 420 (for occupancy) or 340 (for funnel)
// If returns 0, height propagation broken

# 4. Check ResponsiveContainer
document.querySelector('[class*="recharts-responsive-container"]')?.offsetHeight

# 5. Verify data exists
window.__data__  // Set this in component if needed
```

### Issue: Docker Build Fails

**Symptoms**:
```
ERROR: npm install failed
ERROR: npm run build failed
ERROR: No build output found
```

**Fix**:
```dockerfile
# 1. Add debug output to Dockerfile
RUN npm install --include=dev --legacy-peer-deps && npm list tailwindcss
RUN npm run build && ls -la dist/

# 2. Rebuild with verbose
docker build --progress=plain ...

# 3. Check build logs
docker logs <container-id>
```

---

## Performance Verification

### CSS Performance
```bash
# Measure CSS load time
# In browser DevTools Network tab

# Expected:
# - CSS file: 35 KB
# - Load time: <100ms
# - Cache: Use browser cache
```

### Chart Performance
```bash
# In browser console
console.time('chart-render');
// ... wait for charts to load ...
console.timeEnd('chart-render');

# Expected: <200ms
```

### Build Performance
```bash
# Measure build time
time npm run build

# Expected: <5 seconds

# Measure bundle size
npm list recharts
npm list react

# Expected reasonable sizes
```

---

## Validation Checklist

- [ ] `package.json` contains tailwindcss, postcss, autoprefixer
- [ ] `postcss.config.js` configured for v3
- [ ] `tailwind.config.js` has content paths and theme extensions
- [ ] `Dockerfile` doesn't override config with v4 packages
- [ ] `App.tsx` has proper height containers
- [ ] `OccupancyChart.tsx` has height propagation
- [ ] `FunnelChart.tsx` uses correct Recharts imports
- [ ] `dist/assets/index-*.css` exists and 30-50 KB
- [ ] No CSS errors in browser console
- [ ] No Recharts errors in browser console
- [ ] Charts render with correct dimensions
- [ ] Layout displays as grid (not stacked)
- [ ] Dark theme applied (dark background)
- [ ] All cards have rounded corners and shadows
- [ ] KPI cards show 4-column on desktop
- [ ] Responsive on tablet and mobile

---

## Deployment Verification

### Pre-Production
```bash
# 1. Run all tests
npm run typecheck
npm run build

# 2. Verify CSS size
du -h dist/assets/index-*.css

# 3. Check production readiness
ls -la dist/
# Should have: index.html, assets/index-*.css, assets/index-*.js, etc.

# 4. Run security scan (if applicable)
npm audit
```

### Production
```bash
# 1. Monitor build process
docker build ... --progress=plain

# 2. Verify container health
curl http://localhost:3000/health
# Expected: 200 OK

# 3. Test API routing
curl http://localhost:3000/api/v1/kpis
# Expected: 200 + JSON response

# 4. Test WebSocket
wscat -c ws://localhost:3000/ws/alerts
# Expected: Connection accepted
```

---

## Troubleshooting Commands

```bash
# Clear everything and rebuild
rm -rf node_modules dist .parcel-cache && npm install && npm run build

# Check specific Tailwind class
grep "grid-cols-4" dist/assets/index-*.css

# Verify all imports work
npm run typecheck

# Debug Tailwind config
npx tailwindcss init --help

# Check file sizes
du -h dist/assets/*

# Verify HTML structure
head -20 dist/index.html
tail -20 dist/index.html

# Monitor live rebuild
npm run dev -- --host
```

---

## Success Indicators

✅ **Build succeeds without errors**
✅ **CSS file 30-50 KB with Tailwind classes**
✅ **Charts render in browser**
✅ **Dark theme applied**
✅ **Layout responsive**
✅ **Console logs show data loading**
✅ **No JavaScript errors**
✅ **API endpoints respond correctly**
✅ **WebSocket connects**

---

See Also:
- [IMPLEMENTATION_SUMMARY_UI_FIXES.md](IMPLEMENTATION_SUMMARY_UI_FIXES.md)
- [ROOT_CAUSE_UI_ANALYSIS.md](ROOT_CAUSE_UI_ANALYSIS.md)

