# 🔍 ROOT CAUSE ANALYSIS & PRODUCTION FIXES

## Root Causes Identified

### 1. **Recharts Height Issue** ⚠️ CRITICAL
**Problem**: 
- `ResponsiveContainer` uses `height="100%"` but parent has `min-h-[420px]`
- Recharts requires explicit pixel height, not CSS min-height
- Parent div with only `min-height` doesn't provide a concrete height value
- Result: Charts render as invisible 0-height containers

**Evidence**:
```tsx
// BROKEN:
<div className="mt-6 min-h-[420px]">  {/* min-height ≠ explicit height */}
  <ResponsiveContainer width="100%" height="100%">  {/* 100% of what? */}
    <AreaChart data={dataWithPeak}>
```

**Impact**: Occupancy and Funnel charts completely invisible despite 200 API responses

---

### 2. **Tailwind CSS Height Classes** ⚠️ CRITICAL
**Problem**:
- Parent containers use `min-h-[420px]` which only sets minimum height
- Recharts `height="100%"` resolves to 100% of parent height
- If parent has no explicit height (only min-height), 100% = 0
- Tailwind doesn't know how to resolve arbitrary min-height to actual height

**Evidence**:
```css
/* Tailwind generates: */
.min-h-\[420px\] {
  min-height: 420px;  /* NOT height: 420px; */
}

/* When ResponsiveContainer tries height="100%": */
/* 100% of undefined height = 0 */
```

---

### 3. **Chart Component Issues** ⚠️ CRITICAL
**Problem**:
- No explicit height constraint on the responsive container wrapper
- No flex container to force height
- No CSS to enforce the parent-child height relationship

**Evidence**:
```tsx
// OccupancyChart.tsx, line 60
return (
  <ResponsiveContainer width="100%" height="100%">  {/* No parent height! */}
    <AreaChart data={dataWithPeak}>
```

---

### 4. **Tailwind Build Pipeline** ✓ VERIFIED
**Status**: Looks correct in config
- `tailwind.config.js`: Properly configured with `content` paths
- `postcss.config.js`: Has tailwindcss and autoprefixer plugins
- `index.css`: Has @tailwind directives
- **However**: No verification that output CSS exists or loads in browser

---

## Fixes

### FIX #1: Update Chart Container Heights

**Problem File**: `dashboard/src/App.tsx`

**Change**: Replace `min-h-[420px]` with `h-[420px]` + flex wrapper

---

### FIX #2: Fix Recharts Wrapper

**Problem Files**: 
- `dashboard/src/components/OccupancyChart.tsx`
- `dashboard/src/components/FunnelChart.tsx`

**Change**: Add explicit height to wrapper, ensure ResponsiveContainer inherits it

---

### FIX #3: Add API Response Logging

**Problem Files**:
- `dashboard/src/components/OccupancyChart.tsx`
- `dashboard/src/components/FunnelChart.tsx`

**Change**: Add console.log to verify API responses for debugging

---

### FIX #4: Update Tailwind Config for Better Dark Mode

**Problem File**: `dashboard/tailwind.config.js`

**Change**: Add explicit dark color palette

---

## Implementation
