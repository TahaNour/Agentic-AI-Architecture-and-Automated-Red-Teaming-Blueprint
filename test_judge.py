import asyncio, json, os
from eval.evaluate import build_judge, score_trace

print("JUDGE_BACKEND       :", os.getenv("JUDGE_BACKEND", "gemini (defaut)"))
print("JUDGE_MODEL_GEMINI  :", os.getenv("JUDGE_MODEL_GEMINI", "gemini-3.5-flash (defaut)"))

async def main():
    traces = json.load(open("eval/traces/traces.json", encoding="utf-8"))[:2]
    judge = build_judge()
    for t in traces:
        print(await score_trace(t, judge))

asyncio.run(main())