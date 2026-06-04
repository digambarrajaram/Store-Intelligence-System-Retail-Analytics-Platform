# Task Progress - Fix Dashboard Widgets

## Investigation & Fix Plan

- [x] 1. Map complete data flow for each broken widget
- [x] 2. Fix Conversion Rate (0%) - Root cause: No POS data seeded → `converted` set empty
- [x] 3. Fix Conversion Funnel (empty) - Root cause: Demo mode synthetic detections at 640x480 don't match zone polygons at 1920x1080
- [x] 4. Fix Live Alerts ("Waiting for alerts...") - Root cause: AlertEngine thresholds too high + no customer events generated
- [x] 5. Fix Active Anomalies (0) - Root cause: `store:store_1:active_anomalies` key never written
- [x] 6. Fix Top Performers ("No salesperson data available") - Root cause: No POS data seeded
- [x] 7. Apply all code changes
- [ ] 8. Verify all fixes
- [ ] 9. Run git diff --stat and summarize
