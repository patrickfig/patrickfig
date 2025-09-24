#!/usr/bin/env python3
import json, os, re, sys, random, datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

README_PATH = "README.md"
START = "<!--CURIOSIDADE:START-->"
END   = "<!--CURIOSIDADE:END-->"
DATA_DIR = "data"
USED_PATH = os.path.join(DATA_DIR, "facts-used.json")
CONFIG = ".curiosidades.yml"

def read_file(p): return open(p, "r", encoding="utf-8").read()
def write_file(p, s): open(p, "w", encoding="utf-8").write(s)
def now_tz(tz):
    # para estampas simples, a Action roda em UTC; mostramos horário local do tz escolhido
    return datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(0)))
def load_yaml():
    if not os.path.exists(CONFIG):
        return {"language":"both","max_length":220,"timezone":"America/Sao_Paulo"}
    import yaml  # PyYAML é nativa no runner
    with open(CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def clean(text, maxlen):
    if not text: return ""
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"\[[^\]]*?\]", "", t)  # remove refs [1]
    return (t if len(t)<=maxlen else t[:maxlen-1] + "…")

def http_get(url, headers=None):
    req = Request(url, headers=headers or {"User-Agent":"readme-facts-bot"})
    with urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")

def pick_wikipedia(lang, mm, dd, maxlen):
    # https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/MM/DD
    url = f"https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/{mm}/{dd}"
    data = json.loads(http_get(url))
    events = data.get("events", [])
    if not events: raise RuntimeError("wiki vazia")
    e = random.choice(events)
    year = e.get("year")
    text = e.get("text") or (e.get("pages",[{}])[0].get("extract"))
    if not text: raise RuntimeError("wiki sem texto")
    txt = clean(text, maxlen)
    return (f"Em {year}, {txt}", f"Wikipedia ({lang})", f"https://{lang}.wikipedia.org/wiki/{e.get('pages',[{}])[0].get('titles',{}).get('normalized','')}" )

def pick_numbers_api(maxlen):
    data = json.loads(http_get("http://numbersapi.com/random/trivia?json"))
    return (clean(data.get("text",""), maxlen), "Numbers API", "http://numbersapi.com/")

def pick_useless_facts(maxlen):
    data = json.loads(http_get("https://uselessfacts.jsph.pl/api/v2/facts/random"))
    txt = data.get("text") or data.get("fact") or data.get("data") or ""
    return (clean(txt, maxlen), "Useless Facts", "https://uselessfacts.jsph.pl/")

def load_used():
    if not os.path.exists(USED_PATH): return {"seen": []}
    try: return json.loads(read_file(USED_PATH))
    except: return {"seen": []}

def save_used(obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    write_file(USED_PATH, json.dumps(obj, ensure_ascii=False, indent=2))

def h(s):
    x = 0
    for ch in s: x = (x*31 + ord(ch)) & 0xFFFFFFFF
    return str(x)

def main():
    cfg = load_yaml()
    maxlen = int(cfg.get("max_length", 220))
    language = (cfg.get("language","both") or "both").lower()

    today = datetime.datetime.utcnow()
    mm = str(today.month).zfill(2)
    dd = str(today.day).zfill(2)

    providers = []
    if language in ("pt","both"):
        providers.append(lambda: pick_wikipedia("pt", mm, dd, maxlen))
    if language in ("en","both"):
        providers.append(lambda: pick_wikipedia("en", mm, dd, maxlen))
        providers.append(lambda: pick_numbers_api(maxlen))
        providers.append(lambda: pick_useless_facts(maxlen))

    fact, source_name, source_url = None, None, None
    for p in providers:
        try:
            fact, source_name, source_url = p()
            if fact: break
        except Exception:
            continue

    used = load_used()
    if fact:
        k = h(fact)
        if k in used["seen"]:
            # tenta outra fonte para evitar repetição
            for p in providers:
                try:
                    f2 = p()
                    if f2 and h(f2[0]) not in used["seen"]:
                        fact, source_name, source_url = f2
                        break
                except Exception:
                    pass
        used["seen"] = (used["seen"] + [h(fact)])[-1000:]
        save_used(used)

    stamp = today.strftime("%Y-%m-%d")
    if not fact:
        block = f"""{START}
> 💭 vixi… me perdi nas curiosidades hoje. Tenta voltar mais tarde!  
> _Falha temporária ao consultar as fontes._

<sub>Atualizado {stamp} • Fontes: Wikipedia / Numbers / Useless Facts</sub>
{END}"""
    else:
        # monta bloco final curto e com fonte
        fonte = f"[{source_name}]({source_url})" if source_url else source_name
        block = f"""{START}
> {fact}

<sub>Fonte: {fonte} • Atualizado {stamp}</sub>
{END}"""

    md = read_file(README_PATH)
    new_md = re.sub(f"{re.escape(START)}[\\s\\S]*?{re.escape(END)}", block, md)
    if new_md != md:
        write_file(README_PATH, new_md)
        print("README atualizado.")
    else:
        print("Nenhuma alteração detectada.")

if __name__ == "__main__":
    main()
