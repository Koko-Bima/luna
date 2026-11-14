"""Собирает widget/nabory.html (E2) из content/prices.py и content/texts.py.

    python scripts/build_widget.py

Рамки платформы: ≤ 32 КБ, 600×600 без прокрутки, без сети, внешних файлов,
полей ввода и картинок. Шрифты — системные.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from content import prices, texts  # noqa: E402

LIMIT = 32 * 1024
OUT = ROOT / "widget" / "nabory.html"

TEMPLATE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=600,height=600">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:600px;height:600px;overflow:hidden}
body{font:16px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
background:#f6f1ec;color:#2b2420;display:flex;flex-direction:column}
.tabs{display:flex;gap:8px;padding:20px 24px 0}
.tab{flex:1;padding:12px 8px;border-radius:12px;background:#e9dfd6;text-align:center;
cursor:pointer;user-select:none;font-weight:600}
.tab span{display:block;font-weight:400;font-size:14px;opacity:.75}
.tab.on{background:#7a4b3a;color:#fff}
.card{flex:1;padding:18px 28px 0;overflow:hidden}
.card h2{font-size:26px;line-height:1.15}
.sub{font-size:16px;opacity:.8;margin-top:4px}
.price{font-size:34px;font-weight:700;margin-top:12px}
.note{font-size:14px;opacity:.75}
ul{list-style:none;margin-top:12px}
li{position:relative;padding-left:18px;margin-top:6px;font-size:15px}
li:before{content:"";position:absolute;left:2px;top:.55em;width:7px;height:7px;border-radius:50%;background:#7a4b3a}
.disc{height:66px;flex:none;display:flex;align-items:center;justify-content:center;
background:#2b2420;color:#fff;font-weight:700;font-size:19px;letter-spacing:.02em;text-align:center;padding:0 16px}
</style></head><body>
<div class="tabs" id="tabs"></div>
<div class="card" id="card"></div>
<div class="disc">__DISCLAIMER__</div>
<script>
var D=__DATA__,K="kovena_nabor";
function esc(s){return s.replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function load(){try{return localStorage.getItem(K)}catch(e){return null}}
function save(v){try{localStorage.setItem(K,v)}catch(e){}}
function show(key){
 var n=D.filter(function(x){return x.key==key})[0]||D[0];
 document.getElementById("tabs").innerHTML=D.map(function(x){
  return '<div class="tab'+(x.key==n.key?' on':'')+'" data-k="'+x.key+'">'+esc(x.title)+'<span>'+esc(x.price)+'</span></div>'}).join("");
 document.getElementById("card").innerHTML='<h2>'+esc(n.title)+'</h2><div class="sub">'+esc(n.subtitle)+
  '</div><div class="price">'+esc(n.price)+'</div><div class="note">'+esc(n.price_note)+'</div><ul>'+
  n.items.map(function(i){return '<li>'+esc(i)+'</li>'}).join("")+'</ul>';
 save(n.key);
}
document.getElementById("tabs").addEventListener("click",function(e){
 var t=e.target.closest(".tab");if(t)show(t.getAttribute("data-k"))});
show(load()||D[0].key);
</script></body></html>
"""


def build() -> str:
    data = json.dumps(prices.NABORY, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("__DATA__", data)
            .replace("__DISCLAIMER__", html.escape(texts.DISCLAIMER)))


def main() -> None:
    out = build()
    size = len(out.encode("utf-8"))
    if size > LIMIT:
        sys.exit(f"widget is {size} bytes, limit {LIMIT}")
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {size} bytes of {LIMIT}")


if __name__ == "__main__":
    main()
