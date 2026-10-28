"""Public name discovery: no account probing, no claims without retrieval."""
import json
import re
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

DEFAULT_PER_PROVIDER = 100
AGENT = "BlackthornIntel/0.6.0 (public-source research; one-off search)"

def validate_name(query):
    name = query.strip()
    if not (2 <= len(name) <= 120) or any(ord(c) < 32 for c in name):
        raise ValueError("NAMEHUNT expects a name of 2-120 printable characters.")
    return name

def search_plans(name):
    exact = '"' + name + '"'
    buckets = {
        "GENERAL WEB": [("Google exact name", "https://www.google.com/search?q=", exact),
            ("Bing exact name", "https://www.bing.com/search?q=", exact),
            ("Brave Search", "https://search.brave.com/search?q=",exact),
            ("DuckDuckGo", "https://duckduckgo.com/?q=", exact)],
        "PUBLIC PROFILES": [
            ("LinkedIn public pages","https://www.google.com/search?q=",f'site:linkedin.com/in/ {exact}'),
            ("GitHub public mentions","https://github.com/search?q=",name),
            ("Reddit public posts","https://www.google.com/search?q=",f'site:reddit.com {exact}'),
            ("Public social mentions","https://www.google.com/search?q=",f'{exact} (site:x.com OR site:instagram.com OR site:facebook.com)')],
        "NEWS & MEDIA": [
            ("Google News","https://www.google.com/search?tbm=nws&q=",exact),
            ("Bing News","https://www.bing.com/news/search?q=",exact),
            ("Interview mentions","https://www.google.com/search?q=",f'{exact} interview'),
            ("Press releases","https://www.google.com/search?q=",f'{exact} "press release"')],
        "PUBLIC WRITING & RESEARCH": [
            ("Wikipedia articles","https://en.wikipedia.org/w/index.php?search=", name),
            ("OpenAlex authors","https://openalex.org/authors?search=",name),
            ("Books & citations","https://www.google.com/search?tbm=bks&q=",exact),
            ("Open Library authors","https://openlibrary.org/search/authors?q=",name),
            ("Public talks","https://www.google.com/search?q=",f'{exact} conference OR speaker')],
        "ARCHIVED & ORGANIZATIONAL": [
            ("Public organization mentions","https://www.google.com/search?q=",f'{exact} organization OR company'),
            ("Public PDF documents","https://www.google.com/search?q=",f'{exact} filetype:pdf'),
            ("Archive.org search","https://archive.org/search?query=",exact),
            ("Wikidata entities","https://www.wikidata.org/w/index.php?search=",name),
            ("Name with alternate context","https://www.bing.com/search?q=",f'{exact} profile OR biography')]
    }
    return {category:[{"label":label,"url":prefix+quote_plus(q),"query":q} for label,prefix,q in rows]
            for category,rows in buckets.items()}

def _request_json(url):
    req=Request(url,headers={"User-Agent":AGENT,"Accept":"application/json"})
    with urlopen(req,timeout=8) as response:
        return json.load(response)


def _paged_api(url_maker, parse, per_provider, provider, progress=None):
    out=[]
    for offset in range(0,per_provider,50):
        size=min(50,per_provider-offset)
        data=_request_json(url_maker(offset,size))
        batch=parse(data)
        out.extend(batch)
        if progress:progress(f"[LIVE] {provider}: {len(out)} records")
        if len(batch)<size:break
    return out[:per_provider]
def live_public_search(name, per_provider=100, progress=None):
    """Two bounded public APIs; errors surfaced instead of inventing hits."""
    if not 1 <= per_provider <= 1000:
        raise ValueError("per_provider must be between 1 and 1000")
    sources=[]
    errors=[]
    counts={}
    def collect(label, items):
        sources.extend(items)
        counts[label]=len(items)
        if progress:progress(f"[LIVE] {label}: {len(items)} retrieved candidates")
    url="https://en.wikipedia.org/w/api.php?"+urlencode({
        "action":"query","list":"search","srsearch":f'"{name}"',
        "srlimit":min(per_provider,50),"format":"json","formatversion":"2"})
    try:
        data=_request_json(url)
        for row in data.get("query",{}).get("search",[])[:per_provider]:
            title=str(row.get("title",""))
            pageid=row.get("pageid")
            if title and isinstance(pageid,int):
                sources.append({"provider":"Wikipedia","title":title,
                    "url":"https://en.wikipedia.org/?curid="+str(pageid),
                    "record_type":"encyclopedia article","evidence":"API returned article title; identity match not verified"})
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        errors.append("Wikipedia: "+type(exc).__name__)
    url="https://api.github.com/search/users?"+urlencode({"q":f'{name} in:fullname',"per_page":min(per_provider,50)})
    try:
        data=_request_json(url)
        for row in data.get("items",[])[:per_provider]:
            login=str(row.get("login",""))
            link=str(row.get("html_url",""))
            if login and link.startswith("https://github.com/"):
                sources.append({"provider":"GitHub","title":login,"url":link,
                    "record_type":"public account","evidence":"Public user search candidate; same-name does not prove identity"})
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        errors.append("GitHub: "+type(exc).__name__)
    # OpenAlex public scholarly author directory. Public profile candidates only.
    url="https://api.openalex.org/authors?"+urlencode({"search":name,"per-page":min(per_provider,50)})
    try:
        data=_request_json(url)
        for row in data.get("results",[])[:per_provider]:
            label=str(row.get("display_name", ""))
            target=str(row.get("id", ""))
            if label and target.startswith("https://openalex.org/A"):
                sources.append({"provider":"OpenAlex","title":label,"url":target,
                    "record_type":"academic author","evidence":"Public academic author record; not a confirmed personal identity"})
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        errors.append("OpenAlex: "+type(exc).__name__)
    # Structured public knowledge entities. Includes topics and organizations,
    # not solely people: candidates are explicitly typed in the output.
    url="https://www.wikidata.org/w/api.php?"+urlencode({
        "action":"wbsearchentities","search":name,"language":"en",
        "limit":min(per_provider,50),"format":"json"})
    try:
        data=_request_json(url)
        for row in data.get("search",[])[:per_provider]:
            identifier=str(row.get("id",""))
            label=str(row.get("label",""))
            if re.fullmatch(r"Q[0-9]+",identifier) and label:
                sources.append({"provider":"Wikidata","title":label,
                    "url":"https://www.wikidata.org/wiki/"+identifier,
                    "record_type":"knowledge entity",
                    "evidence":str(row.get("description", "Public structured entity"))[:180]+"; not a confirmed identity"})
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        errors.append("Wikidata: "+type(exc).__name__)
    # Book authors catalog, not identity verification.
    url="https://openlibrary.org/search/authors.json?"+urlencode({"q":name,"limit":min(per_provider,50)})
    try:
        data=_request_json(url)
        for row in data.get("docs",[])[:per_provider]:
            key=str(row.get("key",""))
            label=str(row.get("name",""))
            if re.fullmatch(r"OL[0-9]+A",key) and label:
                sources.append({"provider":"Open Library","title":label,
                    "url":"https://openlibrary.org/authors/"+key,
                    "record_type":"author catalog",
                    "evidence":"Public library author listing; not a confirmed identity"})
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        errors.append("Open Library: "+type(exc).__name__)
    # Archive public items may mention the term and are not person profiles.
    url="https://archive.org/advancedsearch.php?"+urlencode({
        "q":"title:(\""+name+"\")", "fl[]":["identifier","title"],
        "rows":min(per_provider,50),"page":1,"output":"json"},doseq=True)
    try:
        data=_request_json(url)
        for row in data.get("response",{}).get("docs",[])[:per_provider]:
            ident=str(row.get("identifier",""))
            title=str(row.get("title",""))
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,150}",ident) and title:
                sources.append({"provider":"Internet Archive","title":title,
                    "url":"https://archive.org/details/"+ident,
                    "record_type":"archive item",
                    "evidence":"Public archive item title, not a personal identity"})
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        errors.append("Internet Archive: "+type(exc).__name__)
    # Additional pages for large collections, without the former five-result cutoff.
    from urllib.parse import urlsplit, parse_qs
    if per_provider > 50:
        configurations = [
          ("Wikipedia", "https://en.wikipedia.org/w/api.php", lambda offset,n:{"action":"query","list":"search","srsearch":'"'+name+'"',"sroffset":offset,"srlimit":n,"format":"json","formatversion":"2"},
             lambda d:[{"provider":"Wikipedia","title":str(x["title"]),"url":"https://en.wikipedia.org/?curid="+str(x["pageid"]),"record_type":"encyclopedia article","evidence":"Public article candidate"} for x in d.get("query",{}).get("search",[]) if x.get("title") and isinstance(x.get("pageid"),int)]),
          ("Open Library","https://openlibrary.org/search/authors.json",lambda offset,n:{"q":name,"limit":n,"offset":offset},
             lambda d:[{"provider":"Open Library","title":str(x["name"]),"url":"https://openlibrary.org/authors/"+str(x["key"]),"record_type":"author catalog","evidence":"Public author record"} for x in d.get("docs",[]) if x.get("name") and re.fullmatch(r"OL[0-9]+A",str(x.get("key","")))]),
          ("OpenAlex","https://api.openalex.org/authors",lambda offset,n:{"search":name,"per-page":n,"page":offset//50+1},
             lambda d:[{"provider":"OpenAlex","title":str(x["display_name"]),"url":str(x["id"]),"record_type":"academic author","evidence":"Public author candidate"} for x in d.get("results",[]) if x.get("display_name") and str(x.get("id","")).startswith("https://openalex.org/A")]),
          ("GitHub","https://api.github.com/search/users",lambda offset,n:{"q":name+" in:fullname","per_page":n,"page":offset//50+1},
             lambda d:[{"provider":"GitHub","title":str(x["login"]),"url":str(x["html_url"]),"record_type":"public account","evidence":"Public account candidate"} for x in d.get("items",[]) if x.get("login") and str(x.get("html_url","")).startswith("https://github.com/")]),
          ("Internet Archive","https://archive.org/advancedsearch.php",lambda offset,n:{"q":'title:("'+name+'")',"fl[]":["identifier","title"],"rows":n,"page":offset//50+1,"output":"json"},
             lambda d:[{"provider":"Internet Archive","title":str(x["title"]),"url":"https://archive.org/details/"+str(x["identifier"]),"record_type":"archive item","evidence":"Public archive item"} for x in d.get("response",{}).get("docs",[]) if x.get("title") and re.fullmatch(r"[A-Za-z0-9_.-]{1,150}",str(x.get("identifier","")))])]
        for provider,base,query,parse in configurations:
            current=sum(1 for item in sources if item.get("provider")==provider)
            if current < 50:continue
            for offset in range(50,per_provider,50):
                amount=min(50,per_provider-offset)
                try:
                    result=parse(_request_json(base+"?"+urlencode(query(offset,amount),doseq=True)))
                    sources.extend(result)
                    if progress:progress(f"[LIVE] {provider}: {sum(1 for x in sources if x.get('provider')==provider)} records")
                    if len(result)<amount:break
                except (HTTPError,URLError,TimeoutError,ValueError,OSError,KeyError,TypeError) as exc:
                    errors.append(provider+" page "+str(offset//50+1)+": "+type(exc).__name__)
                    break
    for record in sources:
        name_key=record.get("provider","Unknown")
        counts[name_key]=counts.get(name_key,0)+1
    if progress:
        for name_key,count in counts.items():progress(f"[LIVE] {name_key}: {count} collected")
    return sources,errors,counts

def namehunt(query,live=False,per_provider=100,progress=None):
    name=validate_name(query)
    result={"module":1,"query":name,"mode":"search links only; live public API candidates if requested",
       "categories":search_plans(name),"sources":{"Web search":"https://www.google.com/search?q="+quote_plus("\""+name+"\"")},"retrieved_candidates":[],
       "live_requested":bool(live),"provider_errors":[],"provider_counts":{},
       "notice":"Search links are leads, not findings. Live API candidates are unverified namesake matches. No private data collected."}
    if live:
        result["retrieved_candidates"],result["provider_errors"],result["provider_counts"]=live_public_search(name,per_provider,progress)
        result["retrieved_candidates"] = rank_candidates(name, result["retrieved_candidates"])
    return result


def rank_candidates(query, candidates):
    """Name-string relevance ONLY, never identity confidence or verification."""
    target=" ".join(query.casefold().split())
    result=[]
    seen=set()
    for item in candidates:
        url=item.get("url", "")
        if url in seen:continue
        seen.add(url)
        title=" ".join(item.get("title", "").casefold().split())
        if title==target:
            label="Exact display-title text"
            group=0
        elif target in title:
            label="Partial display-title text"
            group=1
        else:
            label="Broad provider candidate"
            group=2
        result.append({**item,"relevance_label":label,"identity_verified":False,"_rank":group})
    result.sort(key=lambda x:(x["_rank"],x.get("provider",""),x.get("title","")))
    for item in result:item.pop("_rank",None)
    return result
