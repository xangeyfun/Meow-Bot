from ratelimit import ChannelTokenBucket


def make_bucket():
    clock = [0.0]
    bucket = ChannelTokenBucket(
        capacity=5, refill_rate=1.0, clock=lambda: clock[0]
    )
    return bucket, clock


def test_five_allowed_then_denied():
    bucket, clock = make_bucket()
    results = [bucket.allow(1, 2) for _ in range(6)]
    assert results == [True, True, True, True, True, False]


def test_refill_one_per_second():
    bucket, clock = make_bucket()
    for _ in range(5):
        assert bucket.allow(1, 2)

    assert bucket.allow(1, 2) is False

    clock[0] += 1.0
    assert bucket.allow(1, 2) is True
    assert bucket.allow(1, 2) is False

    clock[0] += 5.0
    results = [bucket.allow(1, 2) for _ in range(6)]
    assert results == [True, True, True, True, True, False]


def test_channels_are_independent():
    bucket, clock = make_bucket()
    for _ in range(5):
        assert bucket.allow(1, 2)

    assert bucket.allow(1, 3) is True
    assert bucket.allow(2, 2) is True


def test_prune_removes_old_buckets():
    bucket, clock = make_bucket()
    bucket.allow(1, 2)
    assert len(bucket._buckets) == 1

    clock[0] += 301
    bucket.prune(max_age=300)
    assert bucket._buckets == {}
