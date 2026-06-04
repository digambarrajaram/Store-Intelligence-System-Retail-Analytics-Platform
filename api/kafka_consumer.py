import json
import time
import asyncio
import os

from aiokafka import AIOKafkaConsumer


async def consume_kafka(app):
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "analytics-group")
    topic = os.getenv("KAFKA_DETECTIONS_TOPIC", "cv.detections")
    retry_delay = int(os.getenv("KAFKA_CONSUMER_RETRY_DELAY", 5))

    redis = app.state.redis

    while True:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8"))
        )

        try:
            print(f"Starting Kafka consumer for topic {topic} on {bootstrap_servers}")
            await consumer.start()
            print("Kafka consumer started")

            async for msg in consumer:
                event = msg.value
                if not isinstance(event, dict):
                    continue

                # Extract store_id, camera_id from event
                store_id = event.get("store_id", "store_1")
                camera_id = event.get("camera_id", "unknown")
                detections = event.get("detections", [])
                now = time.time()
                current_tracks = set()

                for det in detections:
                    track_id = str(det.get("track_id"))
                    if not track_id:
                        continue

                    current_tracks.add(track_id)
                    # Store-specific entry tracking
                    exists = await redis.zscore(f"store:{store_id}:camera:{camera_id}:entries", track_id)
                    if exists is None:
                        await redis.zadd(f"store:{store_id}:camera:{camera_id}:entries", {track_id: now})
                    # Also add to store-wide aggregation
                    store_exists = await redis.zscore(f"store:{store_id}:entries", f"{camera_id}:{track_id}")
                    if store_exists is None:
                        await redis.zadd(f"store:{store_id}:entries", {f"{camera_id}:{track_id}": now})

                # Track camera-specific active tracks
                stored_tracks = await redis.smembers(f"store:{store_id}:camera:{camera_id}:active_tracks")
                stored_tracks = set(stored_tracks or [])
                exited_tracks = stored_tracks - current_tracks

                for track_id in exited_tracks:
                    # Camera-specific exit tracking
                    already_exited = await redis.zscore(f"store:{store_id}:camera:{camera_id}:exits", track_id)
                    if already_exited is None:
                        await redis.zadd(f"store:{store_id}:camera:{camera_id}:exits", {track_id: now})
                        entry_time = await redis.zscore(f"store:{store_id}:camera:{camera_id}:entries", track_id)
                        if entry_time is not None:
                            dwell_time = now - float(entry_time)
                            await redis.hset(f"store:{store_id}:camera:{camera_id}:dwell_times", track_id, dwell_time)
                    # Also add to store-wide
                    store_already_exited = await redis.zscore(f"store:{store_id}:exits", f"{camera_id}:{track_id}")
                    if store_already_exited is None:
                        await redis.zadd(f"store:{store_id}:exits", {f"{camera_id}:{track_id}": now})

                # Update active tracks per camera
                await redis.delete(f"store:{store_id}:camera:{camera_id}:active_tracks")
                if current_tracks:
                    await redis.sadd(f"store:{store_id}:camera:{camera_id}:active_tracks", *list(current_tracks))

                # Camera-specific occupancy
                occupancy = len(current_tracks)
                current_peak = int(await redis.get(f"store:{store_id}:camera:{camera_id}:peak_occupancy") or 0)
                if occupancy > current_peak:
                    await redis.set(f"store:{store_id}:camera:{camera_id}:peak_occupancy", occupancy)
                
                # Store current occupancy for this camera
                await redis.set(f"store:{store_id}:camera:{camera_id}:current_occupancy", occupancy)
                
                # Store-wide peak occupancy (across all cameras in this store)
                all_cameras_occupancy = 0
                for cam_num in range(1, 5):
                    cam_occ = int(await redis.get(f"store:{store_id}:camera:camera_{cam_num}:current_occupancy") or 0)
                    all_cameras_occupancy += cam_occ
                store_peak = int(await redis.get(f"store:{store_id}:peak_occupancy") or 0)
                if all_cameras_occupancy > store_peak:
                    await redis.set(f"store:{store_id}:peak_occupancy", all_cameras_occupancy)
                
                # FPS tracking per camera
                await redis.set(f"store:{store_id}:camera:{camera_id}:fps", event.get("fps", 0))
                await redis.set("metrics:last_updated", now)

                # Anomaly detection per camera (occupancy > 5)
                if occupancy > 5:
                    anomaly_count = int(await redis.get(f"store:{store_id}:camera:{camera_id}:anomaly_count") or 0)
                    await redis.set(f"store:{store_id}:camera:{camera_id}:anomaly_count", anomaly_count + 1)

                # Update store-wide active anomalies count (sum of all camera anomaly counts)
                total_anomalies = 0
                for cam_num in range(1, 5):
                    cam_anomalies = int(await redis.get(f"store:{store_id}:camera:camera_{cam_num}:anomaly_count") or 0)
                    total_anomalies += cam_anomalies
                await redis.set(f"store:{store_id}:active_anomalies", total_anomalies)

        except asyncio.CancelledError:
            print("Kafka consumer task cancelled")
            raise
        except Exception as exc:
            print(f"Kafka consumer error: {exc}")
            await asyncio.sleep(retry_delay)
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass

        print(f"Restarting Kafka consumer after {retry_delay} seconds")
        await asyncio.sleep(retry_delay)
