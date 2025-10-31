import os,time,json,argparse,urllib.parse,signal,requests,sys,re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor,as_completed
from PyPDF2 import PdfReader
from requests.adapters import HTTPAdapter,Retry

TIMEOUT,THREADS=15,10
RETRIES=Retry(total=2,backoff_factor=.2,status_forcelist=[429,500,502,503,504],allowed_methods=["GET"],raise_on_status=False)
MIN_SIZE,MIN_CHARS=15000,100

SafeFileName=lambda s:"".join(c if c.isalnum()or c in"-_.()"else"_"for c in s)[:200]
TextCheck=lambda p:(os.path.getsize(p)>=MIN_SIZE and len("".join(filter(None,map(lambda pg:pg.extract_text(),PdfReader(p).pages[:2]))).strip())>=MIN_CHARS)if os.path.exists(p)else False
DownloadPDF=lambda s,u,p:(lambda r:(True,None)if r.status_code==200 and(open(p,"wb").write(b"".join(r.iter_content(1_048_576)))or True)else(False,f"http_{r.status_code}"))(s.get(u,stream=True,timeout=TIMEOUT))

def ParseBooleanExpr(expr):
    expr=re.sub(r'\s+',' ',expr.strip())
    def tokenize(e):
        tokens,depth,start=[],None,0
        for i,c in enumerate(e):
            if c=='(':depth,start=i,i
            elif c==')'and depth is not None:
                tokens.append(('SUBEXPR',ParseBooleanExpr(e[start+1:i])));depth=None
        buf="".join(c if depth is None or i<depth or i>start else""for i,c in enumerate(e)if c not in'()')
        tokens.extend(list(filter(lambda x:x,map(lambda t:t.strip()if t.strip()in('AND','OR')else('TERM',t.strip())if t.strip()else None,re.split(r'\s+(AND|OR)\s+',buf)))))
        return tokens
    def build_evaluator(toks):
        if not toks:return lambda _:True
        stack=[]
        for i,tok in enumerate(toks):
            if tok in('AND','OR'):continue
            tp,val=tok if isinstance(tok,tuple)else('TERM',tok)
            pred=build_evaluator(val)if tp=='SUBEXPR'else(lambda v:lambda txt:v.lower()in txt.lower())(val)
            op=toks[i-1]if i>0 and toks[i-1]in('AND','OR')else None
            stack.append((pred,op))
        def evaluate(txt):
            if not stack:return True
            result=stack[0][0](txt)
            for pred,op in stack[1:]:
                result=(result and pred(txt))if op=='AND'else(result or pred(txt))if op=='OR'else pred(txt)
            return result
        return evaluate
    return build_evaluator(tokenize(expr))

def SearchCrossRef(s,q,y):
    base="https://api.crossref.org/works";items,cursor,pg=[],["*"],0
    print(f"  >> Year {y}: querying CrossRef...",end="",flush=True)
    while cursor:
        try:
            r=s.get(base,params={"query":q,"filter":f"from-pub-date:{y}-01-01,until-pub-date:{y}-12-31","rows":1000,"cursor":cursor[0]},timeout=TIMEOUT)
            if r.status_code!=200:print(f"\r  [X] Year {y}: HTTP {r.status_code}",flush=True);break
            m=r.json().get("message",{});b=m.get("items",[])
            if not b:break
            items+=b;pg+=1;cursor=[m.get("next-cursor")]if m.get("next-cursor")and len(items)<60000 else[]
            print(f"\r  >> Year {y}: {len(items)} entries (pg. {pg})...",end="",flush=True)
            time.sleep(.03)
        except requests.Timeout:print(f"\r  [X] Year {y}: timeout",flush=True);break
        except Exception as e:print(f"\r  [X] Year {y}: {type(e).__name__}",flush=True);break
    print(f"\r  [OK] Year {y}: {len(items)} harvested{' '*20}",flush=True)
    return items

QueryUnpaywall=lambda s,d,e:(lambda r:r.json()if r.status_code==200 else None)(s.get(f"https://api.unpaywall.org/v2/{urllib.parse.quote(d)}",params={"email":e},timeout=TIMEOUT))
ChoosePDFUnpaywall=lambda d:(lambda r:r if r!=(None,None)else(None,None))(next(((l[k],l.get("version"))for l in filter(None,[d.get("best_oa_location")]+d.get("oa_locations",[]))for k in("url_for_pdf","url")if l.get("version")in("publishedVersion","acceptedVersion")and l.get(k,"").lower().endswith(".pdf")),(None,None)))if d else(None,None)
QuerySemanticScholar=lambda s,d:(lambda p:p if p and p.lower().endswith(".pdf")else None)((lambda r:r.json().get("openAccessPdf",{}).get("url","")if r.status_code==200 else"")(s.get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(d)}",params={"fields":"openAccessPdf"},timeout=TIMEOUT)))
QueryOpenAlex=lambda s,d:(lambda p:p if p and p.lower().endswith(".pdf")else None)((lambda r:r.json().get("open_access",{}).get("oa_url","")if r.status_code==200 else"")(s.get(f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(d)}",timeout=TIMEOUT)))

def process_item(it,s,a,filt):
    doi,title,year=it.get("DOI")," ".join(it.get("title",[]))if it.get("title")else"",next(iter(it.get("issued",{}).get("date-parts",[["NA"]])[0]),"NA")
    authors,abstract=[x.get("family","")for x in it.get("author",[])if x.get("family")],it.get("abstract","")
    fulltext=f"{title} {abstract}".strip()
    if not filt(fulltext):return{"status":"filtered","doi":doi}
    if not doi:return{"status":"no_doi"}
    rec={"doi":doi,"title":title,"year":year}
    for fn,src in[(lambda:ChoosePDFUnpaywall(QueryUnpaywall(s,doi,a.email)),"Unpaywall"),
                  (lambda:(QuerySemanticScholar(s,doi),None),"SemanticScholar"),
                  (lambda:(QueryOpenAlex(s,doi),None),"OpenAlex")]:
        try:
            result=fn()
            pdf,ver=result if isinstance(result,tuple)else(result,None)
            if pdf:rec.update({"pdf_url":pdf,"source":src,"version":ver});break
        except:continue
    if not rec.get("pdf_url"):return{**rec,"status":"no_pdf"}
    fname=SafeFileName(f"{year}_{authors[0]if authors else'unk'}_{title[:60]}")+".pdf"
    path=os.path.join(a.output,fname)
    ok,err=DownloadPDF(s,rec["pdf_url"],path)
    if not ok:return{**rec,"status":"fail","error":err}
    try:
        if not TextCheck(path):os.remove(path);return{**rec,"status":"empty"}
    except:return{**rec,"status":"corrupt"}
    return{**rec,"status":"ok","local_path":path,"size":os.path.getsize(path)}

graceful_exit=lambda sig,frame:(print("\n[!] Ceased by operator.",flush=True),os._exit(0))

def main():
    signal.signal(signal.SIGINT,graceful_exit);os.system("cls"if os.name=="nt"else"clear")
    ap=argparse.ArgumentParser()
    ap.add_argument("--keywords",required=True);ap.add_argument("--start",type=int,required=True)
    ap.add_argument("--end",type=int,required=True);ap.add_argument("--email",required=True)
    ap.add_argument("--output",required=True);a=ap.parse_args()
    os.makedirs(a.output,exist_ok=True);meta=os.path.join(a.output,"metadata.jsonl")

    s=requests.Session();ad=HTTPAdapter(max_retries=RETRIES,pool_connections=20,pool_maxsize=20)
    s.mount("http://",ad);s.mount("https://",ad)
    s.headers.update({"User-Agent":f"Harvester/v0.8.7 (mailto:{a.email})"})

    print(f"\n{'='*58}\n  Alpha Harvest v0.8.7 — Automated Article Farm\n{'='*58}")
    print(f"\n[>] Query: '{a.keywords}'")
    bool_filter=ParseBooleanExpr(a.keywords)
    search_terms=re.sub(r'[()]','',re.sub(r'\s+(AND|OR)\s+',' ',a.keywords))
    print(f"[>] Time Span: {a.start}–{a.end} ({a.end-a.start+1} years)")
    print(f"[>] Destination: {a.output}\n{'-'*60}\n");sys.stdout.flush()

    all_items=sum(list(filter(None,map(lambda y:SearchCrossRef(s,search_terms,y),range(a.start,a.end+1)))),[])
    
    print(f"\n{'-'*60}\n[#] Aggregate yield: {len(all_items)} entries (pre-filter)\n{'-'*60}\n");sys.stdout.flush()
    if not all_items:print("[X] Null harvest. Verify parameters.\n",flush=True);return

    print(f"[>>] Engaging parallel fetch ({THREADS} threads) w/ boolean sieve...\n",flush=True);time.sleep(.5)
    with ThreadPoolExecutor(max_workers=THREADS)as ex:
        futs=[ex.submit(process_item,it,s,a,bool_filter)for it in all_items]
        for f in tqdm(as_completed(futs),total=len(futs),desc="Processing",unit="doc",dynamic_ncols=True,colour="cyan"):
            try:r=f.result()
            except Exception as e:r={"status":"thread_err","error":str(e)}
            open(meta,"a",encoding="utf-8").write(json.dumps(r,ensure_ascii=False)+"\n")

    all_res=list(map(json.loads,open(meta,encoding="utf-8").read().splitlines()))
    valids=list(filter(lambda r:r.get("status")=="ok",all_res))
    filtered=list(filter(lambda r:r.get("status")=="filtered",all_res))
    
    print(f"\n{'-'*60}\n[#] Came across {len(filtered)} entries (non-conformant to boolean logic)")
    print(f"[OK] Terminus: {len(valids)}/{len(all_items)-len(filtered)} valid PDFs ({100*len(valids)//max(len(all_items)-len(filtered),1)}%)")
    print(f"[#] Metadata: {meta}\n");sys.stdout.flush()

if __name__=="__main__":main()
