import asyncio
import json
import websockets


async def main():
    uri = 'ws://127.0.0.1:8100/ws/monitor'
    async with websockets.connect(uri, ping_interval=None) as ws:
        await ws.send('ping')
        print('WS_CONNECTED=1', flush=True)
        for _ in range(90):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except TimeoutError:
                continue
            data = json.loads(msg)
            if data.get('type') == 'pong':
                continue
            print('WS_PAYLOAD_KEYS=' + ','.join(sorted(data.keys())), flush=True)
            print('WS_TICKER=' + str(data.get('ticker')) + ' WS_TIMEFRAME=' + str(data.get('timeframe')), flush=True)
            print('WS_HAS_DECISION=' + str(isinstance(data.get('decision'), dict)), flush=True)
            print('WS_HAS_ML=' + str(isinstance(data.get('ml'), dict)), flush=True)
            print('WS_DECISION=' + json.dumps(data.get('decision', {}), ensure_ascii=False), flush=True)
            return
        print('WS_PAYLOAD_TIMEOUT=1', flush=True)


asyncio.run(main())
