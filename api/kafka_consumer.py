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

                detections = event.get("detections", [])
                now = time.time()
                current_tracks = set()

                for det in detections:
                    track_id = str(det.get("track_id"))
                    if not track_id:
                        continue

                    current_tracks.add(track_id)
                    exists = await redis.zscore("entries", track_id)
                    if exists is None:
                        await redis.zadd("entries", {track_id: now})

                stored_tracks = await redis.smembers("active_tracks")
                stored_tracks = set(stored_tracks or [])
                exited_tracks = stored_tracks - current_tracks

                for track_id in exited_tracks:
                    already_exited = await redis.zscore("exits", track_id)
                    if already_exited is None:
                        await redis.zadd("exits", {track_id: now})
                        entry_time = await redis.zscore("entries", track_id)
                        if entry_time is not None:
                            dwell_time = now - float(entry_time)
                            await redis.hset("dwell_times", track_id, dwell_time)

                await redis.delete("active_tracks")
                if current_tracks:
                    await redis.sadd("active_tracks", *list(current_tracks))

                occupancy = len(current_tracks)
                current_peak = int(await redis.get("peak_occupancy") or 0)
                if occupancy > current_peak:
                    await redis.set("peak_occupancy", occupancy)

                await redis.set("camera_fps", event.get("fps", 0))
                await redis.set("metrics:last_updated", now)

                if occupancy > 5:
                    anomaly_count = int(await redis.get("anomaly_count") or 0)
                    await redis.set("anomaly_count", anomaly_count + 1)

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