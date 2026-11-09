import time


class ChannelTokenBucket:
    def __init__(self, capacity=5, refill_rate=1.0, clock=time.monotonic):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.clock = clock
        self._buckets = {}
        self._calls = 0

    def allow(self, guild_id, channel_id):
        key = (guild_id, channel_id)
        now = self.clock()
        state = self._buckets.get(key)
        if state is None:
            tokens = self.capacity
            updated = now
        else:
            tokens, updated = state
            elapsed = now - updated
            if elapsed > 0:
                tokens = min(self.capacity, tokens + elapsed * self.refill_rate)
                updated = now

        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, updated)
            allowed = True
        else:
            self._buckets[key] = (tokens, updated)
            allowed = False

        self._calls += 1
        if self._calls % 1000 == 0:
            self.prune()
        return allowed

    def prune(self, max_age=300.0):
        now = self.clock()
        self._buckets = {
            key: state for key, state in self._buckets.items() if now - state[1] < max_age
        }
