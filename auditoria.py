import re, json, sys, html
from collections import Counter

FILES = ["estudio-fisico.html","manual-entrenamiento.html","programa-semanal.html"]
issues=[]
def bug(sev,f,msg): issues.append((sev,f,msg))

# ---------- 1. ESTRUCTURA HTML ----------
VOID={'br','hr','img','input','meta','link','area','base','col','embed','source','track','wbr','path','circle','line','rect','polyline','polygon','use','animate','animateTransform','set','stop','ellipse'}
for f in FILES:
    s=open(f,encoding='utf-8').read()
    # etiquetas sin cerrar (aprox)
    tags=re.findall(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>', s)
    stack=Counter()
    for close,name,selfc in tags:
        n=name.lower()
        if n in VOID or selfc=='/': continue
        stack[n]+= -1 if close else 1
    for n,c in stack.items():
        if c!=0: bug("ALTA",f,"desbalance de <%s>: %+d"%(n,c))
    # ids duplicados
    ids=re.findall(r'\sid="([^"]+)"',s)
    for i,c in Counter(ids).items():
        if c>1: bug("ALTA",f,"id duplicado: %s (%d)"%(i,c))
    # href rotos internos
    anchors=set(ids)
    for h in re.findall(r'href="#([^"]+)"',s):
        if h not in anchors: bug("MEDIA",f,"ancla interna rota: #%s"%h)
    # accesibilidad basica
    for m in re.finditer(r'<svg\b([^>]*)>',s):
        at=m.group(1)
        if 'role="img"' in at and 'aria-label' not in at: bug("MEDIA",f,"svg role=img sin aria-label")
    if '<table' in s:
        for m in re.finditer(r'<table[^>]*>(.*?)</table>',s,re.S):
            if '<thead' not in m.group(1) and 'caption' not in m.group(1)[:200]:
                pass
    # color literal fuera de tokens (riesgo de tema)
    for m in re.finditer(r'(?<!-)(#[0-9a-fA-F]{6})',s):
        ctx=s[max(0,m.start()-120):m.start()]
        if '--' not in ctx.split('\n')[-1] and 'keyframes' not in ctx:
            pass

# ---------- 2. SMIL: sincronia y validez ----------
s=open("manual-entrenamiento.html",encoding='utf-8').read()
figs=re.findall(r'<figure class="ex-fig">(.*?)</figure>',s,re.S)
print("figuras encontradas:",len(figs))
for i,fg in enumerate(figs,1):
    durs=set(re.findall(r'dur="([^"]+)"',fg))
    if len(durs)>1: bug("ALTA","manual","figura %d: duraciones no sincronizadas %s"%(i,durs))
    for m in re.finditer(r'<animate[^>]*>',fg):
        a=m.group(0)
        kt=re.search(r'keyTimes="([^"]+)"',a); vals=re.search(r'values="([^"]+)"',a)
        ks=re.search(r'keySplines="([^"]+)"',a)
        if kt and vals:
            nk=len(kt.group(1).split(';')); nv=len(vals.group(1).split(';'))
            if nk!=nv: bug("ALTA","manual","figura %d: keyTimes(%d)!=values(%d)"%(i,nk,nv))
            if ks:
                nsp=len([x for x in ks.group(1).split(';') if x.strip()])
                if nsp!=nk-1: bug("ALTA","manual","figura %d: keySplines(%d)!=keyTimes-1(%d)"%(i,nsp,nk-1))
            if not kt.group(1).split(';')[0].strip().startswith('0'): bug("ALTA","manual","figura %d: keyTimes no empieza en 0"%i)
        # polilineas: mismo numero de puntos entre poses
        if 'attributeName="points"' in a and vals:
            counts={len(v.split(',')) for v in vals.group(1).split(';')}
            if len(counts)>1: bug("ALTA","manual","figura %d: nº de puntos distinto entre poses %s"%(i,counts))
    if 'aria-label' not in fg: bug("MEDIA","manual","figura %d sin aria-label"%i)
    if '<figcaption' not in fg: bug("BAJA","manual","figura %d sin figcaption"%i)

# ---------- 3. PROGRAMA: matematica de menus y macros ----------
p=open("programa-semanal.html",encoding='utf-8').read()
mblock=re.search(r'var MENUS = \{(.*?)\n\};',p,re.S).group(1)
menus={}
for key in ['A','B','C']:
    mk=re.search(r'\b%s:\[(.*?)\n  \]'%key,mblock,re.S)
    days=re.findall(r'\[\[.*?\]\]',mk.group(1),re.S)
    menus[key]=[[int(x) for x in re.findall(r',(\d+)\]',d)] for d in days]

print("\n--- SUMAS DE MENÚ POR DÍA ---")
for k,ds in menus.items():
    tot=[sum(d) for d in ds]
    print(" menú %s: %s  media=%d  min=%d max=%d"%(k,tot,sum(tot)/len(tot),min(tot),max(tot)))
    for i,t in enumerate(tot):
        if abs(t-2200)>150: bug("ALTA","programa","menú %s día %d suma %d kcal (objetivo base 2.200, desvío %+d)"%(k,i+1,t,t-2200))

# macros declarados por semana
weeks=re.findall(r'\{n:(\d+), ph:"(\w+)".*?kcal:(\d+)',p)
print("\n--- MACROS POR SEMANA (declarados en la app) ---")
for n,ph,kc in weeks:
    kc=int(kc); P,F=165,70
    hc=(kc-P*4-F*9)/4
    print(" S%-2s %s  %d kcal -> P165 G70 HC%.0f"%(n,ph,kc,hc))
if 'HC' not in p and 'Carbohidrato' not in p and 'carbohidrato' not in p.split('<script')[0]:
    bug("ALTA","programa","el panel de macros muestra proteína y grasa fijas pero NO muestra el carbohidrato, que es el único macro que varía entre semanas")

# extras vs objetivo
print("\n--- COHERENCIA EXTRAS vs OBJETIVO ---")
for n,ph,kc in weeks:
    kc=int(kc)
    ex = 300 if kc>=2450 else 250 if kc>=2400 else 150 if kc>=2300 else 0
    mk = re.search(r'\{n:%s,.*?menu:"(\w)"'%n,p,re.S).group(1)
    tot=[sum(d)+ex for d in menus[mk]]
    dev=[t-kc for t in tot]
    print(" S%-2s obj=%d menú=%s extra=+%d -> desvío diario %s"%(n,kc,mk,ex,dev))
    if max(abs(d) for d in dev)>200:
        bug("ALTA","programa","S%s: algún día se desvía %+d kcal del objetivo"%(n,max(dev,key=abs)))

# ---------- 4. JS: riesgos ----------
print("\n--- JS ---")
if 'Math.floor((t - BASE)/86400000)' in p:
    bug("MEDIA","programa","cálculo de semana por milisegundos: vulnerable al cambio de hora (DST). Usar componentes de fecha")
if 'role="tablist"' in p and 'role="tabpanel"' not in p:
    bug("MEDIA","programa","patrón ARIA tablist incompleto: hay role=tab sin role=tabpanel")
if 'localStorage' in p and 'import' not in p.lower():
    bug("MEDIA","programa","persistencia solo en localStorage sin importación: si se borran datos del navegador no hay forma de restaurar")
if 'confirm(' in p: bug("BAJA","programa","uso de confirm() nativo")
if re.search(r'aria-current="\'\+\(.*?\)\+\'"',p) or 'aria-current="false"' in p or "aria-current=\"'+(w.n===S.sel)+'\"" in p:
    bug("BAJA","programa","aria-current se emite como 'false'; debe omitirse cuando no aplica")

# ---------- 5. INFO CRUZADA ----------
st=open("estudio-fisico.html",encoding='utf-8').read()
for doc,txt in [("estudio",st),("programa",p),("manual",s)]:
    for m in re.finditer(r'(\d[\d.,]*)\s*kcal',txt):
        pass
if '2.200' in st and '2200' in p: pass

print("\n================ INFORME ================")
sev_order={"ALTA":0,"MEDIA":1,"BAJA":2}
issues.sort(key=lambda x: sev_order[x[0]])
for sev,f,msg in issues:
    print("[%s] %s — %s"%(sev,f,msg))
print("\nTotal: %d hallazgos (%d altas)"%(len(issues),sum(1 for i in issues if i[0]=="ALTA")))
