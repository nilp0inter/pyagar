import asyncio


@asyncio.coroutine
def hub(in_queue, *out_queues):
    while True:
        data = yield from in_queue.get()
        for q in out_queues:
            q.put_nowait(data)
