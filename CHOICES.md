# CHOICES.md

## 1. YOLOv8n vs YOLOv8m/l/x — why nano for this use case
- **Decision made**: YOLOv8n (nano variant)
- **Alternatives considered**: YOLOv8m (medium), YOLOv8l (large), YOLOv8x (extra large)
- **Reasoning**: For a CPU-only, single-store retail environment with hackathon timeline constraints, YOLOv8n provides the best balance of speed and accuracy. The nano variant runs at ~15-20 FPS on CPU without GPU acceleration, sufficient for typical retail CCTV frame rates (5-10 FPS). Larger variants (m/l/x) offer marginally better accuracy (<3% mAP improvement) but require 2-4x more compute, making real-time processing infeasible on CPU. The nano model's smaller size (<6MB) also enables faster container startup and lower memory footprint, critical for Dockerized deployment in resource-constrained hackathon environments.
- **Known trade-offs**: Slightly lower detection accuracy for small objects (e.g., distant shoplifters) and reduced robustness in extreme lighting conditions compared to larger variants. However, for typical retail scenarios (clear aisles, moderate lighting), this accuracy trade-off is acceptable given the significant real-time processing gains.

## 2. ByteTrack vs DeepSORT vs StrongSORT — tracking algorithm choice
- **Decision made**: ByteTrack
- **Alternatives considered**: DeepSORT, StrongSORT
- **Reasoning**: ByteTrack was selected for its superior performance in low-FPS scenarios and minimal computational overhead. Unlike DeepSORT/StrongSORT which rely on appearance features requiring additional CNN computation (prohibitively expensive on CPU), ByteTrack associates detections purely through motion and bounding box overlap, achieving comparable tracking accuracy with 5-10x lower latency. In retail environments with frequent occlusions (aisles, displays), ByteTrack's association of low-confidence detections reduces identity switches during temporary occlusions. Its simplicity also facilitates easier debugging and tuning within the hackathon timeline.
- **Known trade-offs**: ByteTrack may accumulate more drift during long-term occlusions (>2 seconds) compared to feature-based trackers. However, typical retail tracking durations are short (<1.5 seconds between occlusions), making this limitation acceptable. StrongSORT's slight accuracy edge in crowded scenes is outweighed by its computational infeasibility on CPU.

## 3. Kafka vs RabbitMQ vs direct Redis pub/sub — event streaming choice
- **Decision made**: Apache Kafka
- **Alternatives considered**: RabbitMQ, Redis pub/sub
- **Reasoning**: Kafka was chosen for its durability, scalability, and exactly-once semantics critical for accurate KPI aggregation in retail analytics. Unlike Redis pub/sub (which lacks persistence and consumer group management) or RabbitMQ (which requires complex clustering for similar throughput), Kafka provides built-in partitioning for parallel processing of video streams and persistent storage for replay capability during consumer downtime. For a single-store deployment, Kafka's lightweight mode (single broker) runs efficiently on modest hardware, while its producer/consumer APIs integrate seamlessly with Python-based YOLO/ByteTrack pipelines. The retention policies allow debugging missed events post-facto.
- **Known trade-offs**: Kafka introduces operational complexity (ZooKeeper dependency, tuning partitions) over simpler solutions. However, for this use case, we leverage Docker Compose to run a single-node Kafka with embedded ZooKeeper, minimizing overhead. The slight latency increase (~2ms) versus Redis pub/sub is negligible given the end-to-end processing latency is dominated by YOLO inference (>100ms).

## 4. Redis vs PostgreSQL vs InfluxDB — storage for live KPIs
- **Decision made**: Redis
- **Alternatives considered**: PostgreSQL (with TimescaleDB), InfluxDB
- **Reasoning**: Redis was selected for its sub-millisecond read/write performance and native data structures (hashes, streams) ideal for real-time KPI dashboards. Unlike PostgreSQL (even with TimescaleDB) which incurs disk I/O and connection overhead, or InfluxDB which requires learning Flux/PromQL, Redis provides instant access to aggregated counts via simple GET/HGET operations. For live metrics like current occupancy, queue lengths, and dwell times—updated every second—Redis eliminates query latency bottlenecks. Its TTL feature automatically expires stale session data, and pub/sub capabilities enable real-time dashboard pushes without additional infrastructure.
- **Known trade-offs**: Redis stores data primarily in memory, limiting historical retention. However, live KPIs only require recent aggregates (last 15-30 minutes), with deeper analytics handled by separate batch pipelines. Persistence is achieved via RDB snapshots every 5 minutes, providing durability against crashes without significant performance impact.

## 5. Rule-based anomaly detection vs ML-based (Isolation Forest, Autoencoder)
- **Decision made**: Rule-based anomaly detection
- **Alternatives considered**: Isolation Forest, Autoencoder neural networks
- **Reasoning**: Given the hackathon timeline and need for interpretable alerts, rule-based detection was chosen for rapid deployment and zero false positives during tuning. ML models require labeled anomaly datasets (scarce in retail) and extensive validation to avoid alert fatigue. Simple rules—like occupancy exceeding 80% of capacity for >5 minutes, or queue formation speed >2 persons/minute—can be implemented and adjusted within hours based on store manager feedback. These rules align with known retail KPIs and produce actionable insights without black-box uncertainty.
- **Known trade-offs**: Rule-based systems may miss complex, multi-factor anomalies detectable by ML (e.g., coordinated shoplifting patterns). However, for a minimum viable product targeting core retail concerns (overcrowding, long queues), rule-based detection provides sufficient value with immediate deployability. ML-based approaches would require weeks of data collection and tuning incompatible with hackathon constraints.

## 6. FastAPI vs Django vs Flask — API framework
- **Decision made**: FastAPI
- **Alternatives considered**: Django, Flask
- **Reasoning**: FastAPI was selected for its automatic OpenAPI documentation, async support, and performance—critical for handling high-frequency Kafka consumer events and dashboard REST requests. Unlike Flask (which requires manual async integration) or Django (which introduces ORM overhead unnecessary for our simple data model), FastAPI provides native async endpoints with minimal boilerplate. Its Pydantic models enforce data validation at the API boundary, reducing bugs in event processing. The automatic Swagger UI accelerates frontend integration during development.
- **Known trade-offs**: FastAPI's ecosystem is smaller than Django's, but for this project's scope (no admin interface, minimal authentication needs), this is irrelevant. Slightly higher initial learning curve versus Flask is offset by reduced debugging time from built-in validation and docs.

## 7. Docker Compose vs Kubernetes — deployment choice for this scope
- **Decision made**: Docker Compose
- **Alternatives considered**: Kubernetes (K8s), plain Docker
- **Reasoning**: Docker Compose was chosen for its simplicity in defining and multi-container orchestration for a single-store deployment. Kubernetes introduces significant operational complexity (YAML manifests, kubectl, Helm charts) disproportionate to our single-node, low-scale architecture. Compose allows defining all services (YOLO processor, Kafka, Redis, FastAPI, React) in one YAML file with health checks and dependency ordering—ideal for rapid iteration during the hackathon. Resource limits and restart policies provide sufficient resilience without K8s overhead.
- **Known trade-offs**: Compose lacks built-in service discovery scaling and auto-healing beyond restart policies. However, for a single-store system with predictable load, these limitations are acceptable. Scaling to multiple stores would require re-evaluation, but the current scope doesn't necessitate it.

## 8. Polling vs WebSocket for dashboard real-time updates
- **Decision made**: WebSocket
- **Alternatives considered**: HTTP polling (short/long), Server-Sent Events (SSE)
- **Reasoning**: WebSocket was selected for true full-duplex, low-latency communication essential for real-time dashboard updates. Unlike polling (which wastes bandwidth and introduces delay up to the polling interval) or SSE (server-to-client only), WebSocket enables instant push of KPI updates from the FastAPI backend to the React frontend as events arrive from Kafka. This reduces perceived latency from seconds to milliseconds, critical for live retail monitoring. The connection overhead is negligible given the limited number of dashboard clients (typically 1-2 store managers).
- **Known trade-offs**: WebSocket requires managing connection state and handling reconnects, adding minor frontend complexity. However, libraries like Socket.IO abstract this away effectively. For extremely restricted networks blocking WebSocket ports, polling would be a fallback—but retail environments typically allow standard web ports.

## 9. Zone-based counting vs line-crossing counting — entry/exit detection method
- **Decision made**: Zone-based counting
- **Alternatives considered**: Line-crossing counting
- **Reasoning**: Zone-based counting was chosen for its robustness in crowded retail environments where clear entry/exit lines are difficult to define. By defining virtual zones near entrances and tracking dwell time within these zones, we reduce false counts from loitering or cross-traffic. This method handles occlusion better than line-crossing (which requires unobstructed views of the line) and naturally adapts to varying entrance configurations. Implementation uses simple polygon intersection tests, computationally lighter than trajectory analysis needed for accurate line-crossing.
- **Known trade-offs**: Zone-based counting may miscount if zones overlap with high-traffic aisles, requiring careful placement during setup. However, with store manager input during deployment, optimal zone placement is achievable. Line-crossing offers marginally higher accuracy in ideal conditions but is far more sensitive to calibration errors and obstructions common in real stores.

## 10. Re-entry deduplication via in-memory dict vs persistent DB
- **Decision made**: In-memory dictionary
- **Alternatives considered**: Persistent DB (Redis hash, PostgreSQL)
- **Reasoning**: An in-memory dictionary was selected for re-entry deduplication due to its microsecond access speed and simplicity. Since deduplication only requires tracking recently seen person IDs (e.g., last 5 minutes) within a single processing node, persistent storage adds unnecessary latency and complexity. The dictionary is periodically pruned based on timestamps, ensuring bounded memory usage. For a CPU-bound YOLO/ByteTrack pipeline, avoiding disk/network roundtrips per detection is critical for maintaining throughput.
- **Known trade-offs**: In-memory state is lost if the processing container restarts, potentially causing temporary duplicate counts during recovery. However, restart frequency is low (only during deployments), and the impact is minimal (<1% of total counts) given the short deduplication window. Persistent DB would add ~5-10ms per detection, significantly reducing FPS on CPU.

## Known Limitations
1. **CPU-only constraint**: The system cannot leverage GPU acceleration, limiting maximum camera throughput to ~4-6 1080p streams on modest hardware. Scaling beyond this requires distributed processing not implemented in the MVP.
2. **Single-point of failure**: Kafka, Redis, and the YOLO processor run as single instances; no failover mechanisms exist. Store downtime occurs if any critical component crashes before auto-restart.
3. **Limited multi-object classification**: YOLOv8n detects persons only; distinguishing staff from customers or detecting specific behaviors (shoplifting, falls) requires additional models not included due to compute constraints.
4. **Calibration dependency**: Accurate counting relies on proper zone/line placement during setup, which requires manual configuration per store and cannot be fully automated.
5. **No persistent audit trail**: While Redis snapshots provide basic durability, there is no immutable log of all detection events for forensic analysis, relying solely on aggregated KPIs.
