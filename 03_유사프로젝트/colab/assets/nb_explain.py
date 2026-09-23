# 한 케이스를 SemIf와 똑같은 방식으로 판정하면서, 위젯에 보여 줄 중간값을 함께 모아요.
# - 판정 숫자(확률)는 SemIf 원본 함수 semif_phase1.direct.score()가 낸 값을 그대로 씁니다.
# - 토큰 색칠, 전체 어휘 상위 후보, 층별 점수(logit lens), 보기 순서 바꾸기는 "보여 주기용" 추가 계산이에요.
import itertools
import json
import time

ROLE_NAMES = {
    "template": "채팅 틀(특수 토큰)",
    "system": "지시문(system)",
    "json": "JSON 키·기호",
    "evidence": "상황(state)",
    "criterion": "질문(question)",
    "letter": "보기 글자",
    "option": "보기 설명",
    "gen": "답이 올 자리",
}


def _payload_spans(row, letters):
    """SemIf direct_messages()가 만드는 JSON 문자열을 똑같이 조립하면서 부분별 글자 위치를 기록해요."""
    parts = []

    def add(text, role, label=None):
        parts.append((text, role, label))

    add('{"evidence": ', "json")
    add(json.dumps(row["state"], ensure_ascii=False), "evidence")
    add(', "criterion": ', "json")
    add(json.dumps(row["question"], ensure_ascii=False), "criterion")
    add(', "options": [', "json")
    for index, option in enumerate(row["options"]):
        if index:
            add(", ", "json")
        add('{"letter": ', "json")
        add(json.dumps(letters[index], ensure_ascii=False), "letter", letters[index])
        add(', "description": ', "json")
        add(json.dumps(option["description"], ensure_ascii=False), "option", letters[index])
        add("}", "json")
    add("]}", "json")
    text, spans, cursor = "", [], 0
    for piece, role, label in parts:
        spans.append((cursor, cursor + len(piece), role, label))
        text += piece
        cursor += len(piece)
    return text, spans


def _role_spans(prompt, messages, row, letters):
    system_text = messages[0]["content"]
    user_text = messages[1]["content"]
    built, payload_spans = _payload_spans(row, letters)
    if built != user_text:
        raise ValueError("SemIf 프롬프트 조립 방식이 바뀌었어요. 색칠 규칙을 고쳐야 해요.")
    spans = []
    s0 = prompt.index(system_text)
    spans.append((s0, s0 + len(system_text), "system", None))
    u0 = prompt.index(user_text, s0 + len(system_text))
    for start, end, role, label in payload_spans:
        spans.append((u0 + start, u0 + end, role, label))
    spans.append((u0 + len(user_text), len(prompt), "gen_or_template", None))
    return spans, u0 + len(user_text)


def _token_role(spans, start, end, user_end, prompt):
    if end <= start:
        return "template", None
    best, best_len = ("template", None), 0
    for s, e, role, label in spans:
        overlap = min(end, e) - max(start, s)
        if overlap > best_len:
            best, best_len = (role, label), overlap
    if best[0] == "gen_or_template":
        # 사용자 턴이 끝난 뒤: assistant 머리말은 틀, 그 뒤 빈 생각 블록은 '답이 올 자리' 앞부분
        tail = prompt[user_end:]
        head = tail.find("assistant")
        cut = user_end + (head + len("assistant") if head >= 0 else 0)
        return ("gen", None) if start >= cut else ("template", None)
    if best[0] in ("evidence", "criterion", "letter", "option") and not prompt[start:end].strip(' {}[]":,'):
        return "json", None  # 따옴표·쉼표만 있는 토큰은 JSON 기호로 칠해요
    return best


def explain_case(model, tokenizer, row, metadata, *, topk=10, lens=True, permutations=True, max_perms=24):
    """SemIf 방식 판정 1건 + 위젯용 중간값. 반환값은 JSON으로 바로 저장할 수 있어요."""
    import torch
    from semif_phase1.core import LETTERS, direct_messages, validate_row
    from semif_phase1.direct import encode_prompt, score

    validate_row(row)
    official = score(model, tokenizer, row, metadata)  # ← SemIf 원본 판정 (확률은 이 값)
    messages = direct_messages(row)
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids, slots, prompt_hash = encode_prompt(tokenizer, row, 4096)
    assert prompt_hash == official["prompt_sha256"]
    letters = LETTERS[: len(row["options"])]

    # ① 토큰과 역할(색칠용)
    enc = tokenizer(prompt, add_special_tokens=False, return_offsets_mapping=True)
    if list(enc["input_ids"]) != list(ids):
        raise ValueError("토큰화 결과가 SemIf와 달라요")
    spans, user_end = _role_spans(prompt, messages, row, letters)
    # 브라우저(JavaScript)는 글자 위치를 UTF-16 단위로 세요. 이모지 같은 글자가 있어도 어긋나지 않게 바꿔 둬요.
    u16 = [0]
    for ch in prompt:
        u16.append(u16[-1] + (2 if ord(ch) > 0xFFFF else 1))
    tokens = []
    for token_id, (start, end) in zip(ids, enc["offset_mapping"]):
        role, label = _token_role(spans, start, end, user_end, prompt)
        tokens.append([int(token_id), u16[start], u16[end], role, label])

    # ② 모델 한 번 통과: 마지막 위치의 전체 어휘 점수 + 층별 점수(logit lens)
    device = next(model.parameters()).device
    x = torch.tensor([ids], dtype=torch.long, device=device)
    with torch.inference_mode():
        out = model(input_ids=x, attention_mask=torch.ones_like(x), use_cache=False,
                    output_hidden_states=lens, return_dict=True, logits_to_keep=1)
        vocab = out.logits[0, -1].float()
        logp = torch.log_softmax(vocab, dim=-1)
        top = torch.topk(logp, topk)
        slot_logits = vocab[slots]
        mass = float((slot_logits.logsumexp(-1) - vocab.logsumexp(-1)).exp())
        top_tokens = [[int(i), tokenizer.decode([int(i)]), float(p)]
                      for i, p in zip(top.indices.tolist(), top.values.exp().tolist())]
        lens_rows = []
        if lens:
            base = model.model
            states = out.hidden_states
            for index, state in enumerate(states):
                v = state[0, -1]
                if index < len(states) - 1:  # 마지막 항목은 이미 최종 정규화를 거친 값이에요
                    v = base.norm(v)
                lens_rows.append([round(float(z), 3) for z in model.lm_head(v).float()[slots].cpu().tolist()])
        del out
    same = max(abs(a - b) for a, b in zip(slot_logits.cpu().tolist(), official["option_logits"]))

    # ③ 보기 순서 바꾸기: 같은 보기, 순서만 바꿔 SemIf 판정을 다시 돌려요
    perms = []
    if permutations:
        n = len(row["options"])
        for k, order in enumerate(itertools.permutations(range(n))):
            if k >= max_perms:
                break
            shuffled = dict(row, id=f"{row['id']}#perm{k}", options=[row["options"][j] for j in order])
            r = score(model, tokenizer, shuffled, metadata)
            perms.append({
                "order": [row["options"][j]["id"] for j in order],
                "probs": {oid: round(p, 6) for oid, p in zip(r["option_ids"], r["probabilities"])},
                "logits": {oid: round(v, 4) for oid, v in zip(r["option_ids"], r["option_logits"])},
            })

    text_config = model.config
    return {
        "id": row["id"],
        "row": row,
        "system": messages[0]["content"],
        "payload": messages[1]["content"],
        "prompt": prompt,
        "prompt_sha256": prompt_hash,
        "tokens": tokens,
        "slots": [[letter, int(tid)] for letter, tid in zip(letters, slots)],
        "option_ids": official["option_ids"],
        "option_logits": official["option_logits"],
        "probabilities": official["probabilities"],
        "forward_seconds": official["forward_seconds"],
        "input_tokens": official["input_tokens"],
        "top_tokens": top_tokens,
        "allowed_mass": mass,
        "readout_check_max_abs_diff": same,
        "lens": lens_rows,
        "layer_types": list(getattr(text_config, "layer_types", []) or []),
        "perms": perms,
        "model": {k: metadata.get(k) for k in ("source", "revision", "dtype", "device", "torch_version", "transformers_version")},
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
    }


# ── 6장: 같은 상황에 질문 여러 개 → SemIf 공유 모드(score_shared)와 따로 호출(score) 비교 ──
SHARED_STATE = (
    "Support ticket #4821 from Acme Corp (enterprise plan, customer for 6 years, renewal due next month). "
    "Message: 'Since 09:10 this morning every API call from our checkout service returns HTTP 502. "
    "Our online store has been down for two hours and we are losing orders. We were already promised a fix "
    "last week. If this is not resolved today we will cancel the contract and ask our lawyers to review the SLA.' "
    "Status page: all systems operational. Recent change: API gateway config deployed at 09:05. "
    "Gateway log excerpt: 09:05 config v412 applied; 09:10 upstream checkout-api unhealthy (502) x 1,204; "
    "09:40 retries exhausted; 10:55 still failing. Previous tickets from this customer: 2 in the last 30 days, "
    "both about slow responses, both closed with a promise to investigate."
)
SHARED_QUESTIONS = [
    ("severity", "How severe is this incident?", [("sev0", "Critical: production outage for a paying customer"), ("sev1", "High: major feature degraded"), ("sev2", "Medium: minor issue"), ("sev3", "Low: question or request")]),
    ("team", "Which team should own this ticket?", [("sre", "Infrastructure / SRE"), ("billing", "Billing"), ("sales", "Sales / account management"), ("docs", "Documentation")]),
    ("churn", "Is the customer at risk of leaving?", [("yes", "Yes"), ("no", "No")]),
    ("refund", "Should a refund or credit be offered?", [("yes", "Yes"), ("no", "No")]),
    ("legal", "Does this need legal review?", [("yes", "Yes"), ("no", "No")]),
    ("status", "Should the public status page show an incident?", [("yes", "Yes"), ("no", "No")]),
    ("phone", "Should someone call the customer now?", [("yes", "Yes"), ("no", "No")]),
    ("cause", "What is the most likely root cause area?", [("gateway", "API gateway configuration"), ("db", "Database"), ("client", "Customer's own code"), ("unknown", "Unknown")]),
]


def shared_demo_rows():
    return [dict(id=q, state=SHARED_STATE, question=text, options=[dict(id=i, description=d) for i, d in opts])
            for q, text, opts in SHARED_QUESTIONS]


def run_shared_demo(model, tokenizer, metadata, repeats=2):
    """질문 8개를 ① 따로 8번(score) ② 상황 앞부분을 한 번만 계산(score_shared)으로 판정하고 시간을 재요."""
    from semif_phase1.direct import score
    from semif_phase1.shared import score_shared

    rows = shared_demo_rows()
    score(model, tokenizer, rows[0], metadata)          # 워밍업(버림)
    score_shared(model, tokenizer, rows[:2], metadata)  # 워밍업(버림)
    runs = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        direct = [score(model, tokenizer, r, metadata) for r in rows]
        t_direct = time.perf_counter() - t0
        t0 = time.perf_counter()
        shared, timing = score_shared(model, tokenizer, rows, metadata)
        t_shared = time.perf_counter() - t0
        runs.append((t_direct, t_shared, timing))
    t_direct, t_shared, timing = min(runs, key=lambda x: x[0] + x[1])
    pick = lambda r: r["option_ids"][max(range(len(r["probabilities"])), key=r["probabilities"].__getitem__)]
    return {
        "questions": len(rows),
        "direct_seconds": t_direct,
        "shared_seconds": t_shared,
        "direct_tokens": sum(r["input_tokens"] for r in direct),
        "shared_tokens": timing["prefix_tokens"] + timing["true_suffix_tokens"],
        "prefix_tokens": timing["prefix_tokens"],
        "serving_config": shared[0]["model"].get("serving_config"),
        "same_picks": sum(pick(a) == pick(b) for a, b in zip(direct, shared)),
        "max_prob_diff": max(abs(p - q) for a, b in zip(direct, shared) for p, q in zip(a["probabilities"], b["probabilities"])),
        "answers": [{"id": a["id"], "direct": dict(zip(a["option_ids"], [round(p, 4) for p in a["probabilities"]])),
                     "shared": dict(zip(b["option_ids"], [round(p, 4) for p in b["probabilities"]]))}
                    for a, b in zip(direct, shared)],
        "repeats": repeats,
    }
