from aioredis import ResponseError

RETENTION_MS = 60_000


# ----- Key Management -----
class Keys:
    def sensor_key(self, sensor_id: int, device_id: int, metric: str) -> str:
        return f"sensor:{sensor_id}:device:{device_id}:{metric}"


def make_keys():
    return Keys()


async def make_timeseries(redis, log, key: str):
    try:
        await redis.execute_command(
            "TS.CREATE", key, "RETENTION", RETENTION_MS, "DUPLICATE_POLICY", "first"
        )
    except ResponseError as e:
        log.info(f"Timeseries already exists or error: {e}")


async def initialize_redis(redis, log):
    keys = make_keys()
    keys_to_create = [
        keys.sensor_key(1, 1, "position"),
        keys.sensor_key(2, 1, "speed"),
        keys.sensor_key(3, 1, "acceleration"),
        keys.sensor_key(4, 1, "load"),
        keys.sensor_key(7, 2, "grip_force"),
        keys.sensor_key(8, 2, "distance"),
    ]

    for key in keys_to_create:
        await make_timeseries(redis, log, key)
