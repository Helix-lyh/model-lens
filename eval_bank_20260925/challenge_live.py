"""加强版独立首轮校准。原始请求和每次成绩立即写入独立目录，不覆盖历史。"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import time
import uuid

from src.client import ChatClient, JsonlRecorder
from src.types import Endpoint
from .challenge import REVISION, reasoning_items, grade_reasoning, prompt_hash, salt_prompt, salted_prompt_hash
from .challenge_coding import coding_items, score_saved


# 题面难度对应的单题墙钟预算，单位秒；显式 --timeout 可覆盖，便于诊断。
TIMEOUT_BY_LEVEL = {'easy': 240.0, 'medium': 480.0, 'hard': 720.0, 'extreme': 960.0}
TIME_SCORE_FLOOR = 0.5


def time_score_factor(elapsed_ms, timeout_s):
    """Return a bounded efficiency multiplier for a judged response.

    The first half of the budget is the full-score baseline. After that line,
    the multiplier falls linearly to 0.5 at the timeout. Errors and missing
    elapsed values are handled by the caller and never receive a synthetic score.
    """
    if elapsed_ms is None or timeout_s <= 0:
        return None
    ratio = max(0.0, float(elapsed_ms) / (float(timeout_s) * 1000.0))
    return round(max(TIME_SCORE_FLOOR, 1.0 if ratio <= 0.5 else 1.5 - ratio), 6)


def apply_time_score(grade, elapsed_ms, timeout_s):
    """Add raw/timed score fields and make score10 the timed score."""
    raw = grade.get('score10')
    factor = time_score_factor(elapsed_ms, timeout_s) if raw is not None else None
    grade['score10_content'] = raw
    grade['time_score_factor'] = factor
    grade['score10'] = None if raw is None or factor is None else round(raw * factor, 4)
    return grade


def run_one(item, root, config, sample=0):
    base=config['base_url'].rstrip('/')
    if not base:raise ValueError('API base URL missing')
    if not base.endswith('/v1'):base+='/v1'
    endpoint=Endpoint(base_url=base,api_key_env=config['api_key_env'],model=config['model'],api='openai-completions')
    timeout_s = config['timeout_s'] if config['timeout_s'] is not None else TIMEOUT_BY_LEVEL[item.level]
    client=ChatClient(endpoint,JsonlRecorder(root/item.id/'requests.jsonl'),timeout_s=timeout_s,max_retries=0)
    salt = secrets.token_urlsafe(18)
    request_prompt = salt_prompt(item.prompt, salt)
    started = time.monotonic()
    record=client.complete([{'role':'user','content':request_prompt}],temperature=0.0,max_tokens=config['max_tokens'],extra={'reasoning_effort':'high'},kind=f'{REVISION}:{item.id}',stream=False)
    elapsed_s = time.monotonic() - started
    response_name = 'response.txt' if sample == 0 else f'response-s{sample}.txt'
    (root/item.id/response_name).write_text(record.content or '',encoding='utf-8')
    raw=record.raw if isinstance(record.raw,dict) else {}
    finish=raw.get('finish_reason')
    if not isinstance(finish, str):
        finish=(raw.get('choices') or [{}])[0].get('finish_reason')
    response_model=raw.get('model')
    tool_calls=any(choice.get('message',{}).get('tool_calls') for choice in raw.get('choices',[]) if isinstance(choice,dict))
    if record.error or record.status_code!=200:
        grade={'status':'error','reason_code':'request_error','points':None,'score10':None,'passed':None}
    elif elapsed_s > timeout_s or (record.latency_ms is not None and record.latency_ms > timeout_s * 1000):
        grade={'status':'error','reason_code':'timeout','points':None,'score10':None,'passed':None}
    elif finish == 'length':
        grade={'status':'error','reason_code':'response_truncated','points':None,'score10':None,'passed':None}
    elif tool_calls:
        grade={'status':'error','reason_code':'tool_call_returned','points':None,'score10':None,'passed':None}
    elif item.kind=='reasoning':
        grade=grade_reasoning(item,record.content or '')
    else:
        grade=score_saved(item.id, record.content or '', seed=config['seed'], language='python')
    apply_time_score(grade, record.latency_ms, timeout_s)
    return {'revision':REVISION,'seed':config['seed'],'item':item.id,'kind':item.kind,'difficulty':item.level,'sample':sample,'timeout_s':timeout_s,'salt':salt,'base_prompt_sha256':prompt_hash(item),'prompt_sha256':salted_prompt_hash(request_prompt),'attempt_id':uuid.uuid4().hex,'model_requested':config['model'],'model_returned':response_model,'finish_reason':finish,'truncated':finish=='length','latency_ms':record.latency_ms,'usage':record.usage,'http_status':record.status_code,**grade}


def pass_at_k(rows, k):
    """Estimate independent pass@k per item, excluding non-judged attempts.

    An item is eligible only when at least k independent samples were judged.
    Missing, timeout, and request errors remain visible in diagnostics and do
    not become synthetic failures.
    """
    if k < 1:
        raise ValueError('pass_at_k requires k >= 1')
    grouped = {}
    for row in rows:
        grouped.setdefault(row.get('item'), []).append(row)
    estimates = []
    eligible = 0
    for item_rows in grouped.values():
        judged = [row for row in item_rows if row.get('status') in {'pass', 'fail'}]
        n = len(judged)
        if n < k:
            continue
        c = sum(row.get('passed') is True for row in judged)
        if c == 0:
            estimate = 0.0
        elif c == n or n - c < k:
            estimate = 1.0
        else:
            estimate = 1.0 - __import__('math').comb(n - c, k) / __import__('math').comb(n, k)
        estimates.append(estimate)
        eligible += 1
    return (round(sum(estimates) / len(estimates), 4) if estimates else None), eligible, len(grouped)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,default=92501)
    p.add_argument('--items',default='')
    p.add_argument('--kind',choices=('reasoning','coding','all'),default='reasoning')
    p.add_argument('--max-tokens',type=int,default=384000)
    p.add_argument('--samples',type=int,default=1,help='每题独立采样次数；默认 1')
    p.add_argument('--pass-at',type=int,default=1,dest='pass_k',help='报告 pass@k；必须不大于 --samples')
    p.add_argument('--timeout',type=float,default=None,help='覆盖按难度预算；默认简单/普通/困难/超难为 240/480/720/960 秒')
    p.add_argument('--concurrency',type=int,default=2,help='并发请求数；官方 DeepSeek 端点可按配额提高到 16 以上')
    p.add_argument('--base-url',default=os.environ.get('BOOSTER_BASE_URL',''),help='API origin 或 /v1 根路径，默认 BOOSTER_BASE_URL')
    p.add_argument('--api-key-env',default='BOOSTER_API_KEY',help='API key 所在环境变量，默认 BOOSTER_API_KEY')
    p.add_argument('--model',default='deepseek-flash',help='请求模型 id，默认 deepseek-flash')
    args=p.parse_args()
    if args.concurrency < 1:p.error('--concurrency must be >= 1')
    if args.timeout is not None and args.timeout <= 0:p.error('--timeout must be > 0')
    if args.max_tokens < 1:p.error('--max-tokens must be >= 1')
    if args.samples < 1:p.error('--samples must be >= 1')
    if args.pass_k < 1 or args.pass_k > args.samples:p.error('--pass-at must satisfy 1 <= k <= --samples')
    if not args.base_url:p.error('--base-url 或 BOOSTER_BASE_URL required')
    if not os.environ.get(args.api_key_env):p.error(f'{args.api_key_env} missing')
    items=list(reasoning_items(args.seed)) if args.kind in ('reasoning','all') else []
    if args.kind in ('coding','all'):
        items.extend(coding_items(args.seed))
    if args.items:
        requested=set(x for x in args.items.split(',') if x);known={i.id for i in items}
        if requested-known:p.error('unknown items')
        items=[i for i in items if i.id in requested]
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root=Path('out')/f'{REVISION}-{stamp}-{uuid.uuid4().hex[:6]}'
    root.mkdir(parents=True,exist_ok=False)
    config={'revision':REVISION,'seed':args.seed,'temperature':0.0,'reasoning_effort':'high','max_tokens':args.max_tokens,'samples':args.samples,'pass_k':args.pass_k,'timeout_s':args.timeout,'timeout_by_level':TIMEOUT_BY_LEVEL,'time_score_floor':TIME_SCORE_FLOOR,'time_score_formula':'1.0 through half-budget, then max(floor, 1.5 - elapsed/timeout)','salt_mode':'per_item_random_urlsafe_18','concurrency':args.concurrency,'retries':0,'base_url':args.base_url,'api_key_env':args.api_key_env,'model':args.model,'items':[i.id for i in items],'started_at':stamp,'goal_pass_at_1':[0.3,0.5],'goal_mean_score10':[4.5,5.5]}
    (root/'meta.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (root/'prompts.json').write_text(json.dumps({i.id:i.prompt for i in items},ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'goldens.json').write_text(json.dumps({i.id:i.expected for i in items},ensure_ascii=False,indent=2),encoding='utf-8')
    print('run_dir='+str(root),flush=True)
    rows=[]
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        jobs={pool.submit(run_one,item,root,config,sample): (item,sample) for item in items for sample in range(args.samples)}
        for future in as_completed(jobs):
            item,sample=jobs[future]
            try:row=future.result()
            except Exception as exc:
                row={'revision':REVISION,'seed':config['seed'],'item':item.id,'kind':item.kind,
                     'difficulty':item.level,'sample':sample,'timeout_s':config['timeout_s'] or TIMEOUT_BY_LEVEL[item.level],
                     'salt':None,'base_prompt_sha256':None,'prompt_sha256':None,
                     'attempt_id':uuid.uuid4().hex,'model_requested':config['model'],'model_returned':None,
                     'finish_reason':None,'truncated':False,'latency_ms':None,'usage':None,'http_status':None,
                     'status':'error','reason_code':'runner_error','exception_type':type(exc).__name__,
                     'points':None,'score10':None,'passed':None,'detail':repr(exc)}
            rows.append(row)
            with (root/'results.jsonl').open('a',encoding='utf-8') as fh:
                fh.write(json.dumps(row,ensure_ascii=False)+'\n');fh.flush();os.fsync(fh.fileno())
            print(json.dumps({k:row.get(k) for k in ('item','status','points','latency_ms','finish_reason','reason_code')},ensure_ascii=False),flush=True)
    valid=[r for r in rows if r['status'] in ('pass','fail')]
    pass1, eligible1, item_count = pass_at_k(rows, 1)
    passk, eligiblek, _ = pass_at_k(rows, args.pass_k)
    mean_score10=sum(r['score10'] for r in valid)/len(valid) if valid else None
    target_reached=(pass1 is not None and config['goal_pass_at_1'][0] <= pass1 <= config['goal_pass_at_1'][1]
                    and mean_score10 is not None and config['goal_mean_score10'][0] <= mean_score10 <= config['goal_mean_score10'][1])
    summary={'attempted':len(rows),'items':item_count,'judged':len(valid),'errors':sum(r['status']=='error' for r in rows),'pending_review':sum(r['status']=='pending_review' for r in rows),'passed':sum(r['passed'] is True for r in valid),'pass_at_1':pass1,'pass_at_1_eligible':eligible1,'pass_at_k':passk,'pass_at_k_eligible':eligiblek,'pass_k':args.pass_k,'mean_score10':mean_score10,'target_reached':target_reached,'target_basis':'pass_at_1 and mean_score10; errors are excluded from capability denominator but reported separately','note':'temperature=0 的重复样本衡量稳定性，不代表答案多样性。'}
    (root/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
