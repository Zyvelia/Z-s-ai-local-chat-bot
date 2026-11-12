"""Opt-in bounded local load probe. Default exercises /health only.

Examples:
 python backend/loadtests/run_load.py --base-url http://127.0.0.1:8000 --requests 40 --concurrency 4
 python backend/loadtests/run_load.py --mode stream --token "$TOKEN" --conversation-id "$ID" --requests 4 --concurrency 2
Only run against a server you operate or are authorized to test.
"""
import argparse
import asyncio
import os
import statistics
import time
from collections import Counter
import httpx

async def probe(client, sem, args, durations, codes):
    async with sem:
        start = time.perf_counter()
        try:
            if args.mode == 'health':
                response = await client.get('/health')
                codes[response.status_code] += 1
            else:
                response = await client.post(f'/api/v1/conversations/{args.conversation_id}/messages/stream',
                    json={'content': 'Briefly say hello.'}, headers={'Authorization': f'Bearer {args.token}'})
                codes[response.status_code] += 1
                if response.status_code == 200 and 'event: done' not in response.text:
                    codes['incomplete_stream'] += 1
        except httpx.HTTPError:
            codes['network_error'] += 1
        finally:
            durations.append((time.perf_counter() - start) * 1000)

async def main(args):
    durations, codes = [], Counter()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=httpx.Timeout(args.timeout)) as client:
        sem = asyncio.Semaphore(args.concurrency)
        await asyncio.gather(*(probe(client, sem, args, durations, codes) for _ in range(args.requests)))
    ordered = sorted(durations)
    print('Requests:', args.requests, 'status counts:', dict(codes))
    print('Latency ms: mean=%.1f p50=%.1f p95=%.1f max=%.1f' % (
        statistics.mean(ordered), ordered[(len(ordered)-1)//2],
        ordered[max(0, int(.95 * len(ordered))-1)], ordered[-1]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--mode', choices=('health', 'stream'), default='health')
    parser.add_argument('--token', default=os.getenv('CHAT_TEST_TOKEN', ''))
    parser.add_argument('--conversation-id', default=os.getenv('CHAT_TEST_CONVERSATION', ''))
    parser.add_argument('--requests', type=int, default=40)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=150)
    args = parser.parse_args()
    if not 1 <= args.requests <= 200 or not 1 <= args.concurrency <= 16 or args.concurrency > args.requests:
        parser.error('Keep requests within 1..200, concurrency within 1..16 and <= requests')
    if args.mode == 'stream' and (not args.token or not args.conversation_id):
        parser.error('Stream mode requires --token and --conversation-id')
    asyncio.run(main(args))
