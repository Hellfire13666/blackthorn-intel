"""Readable offline BLACKTHORN evidence report with escaped content."""
import base64
import datetime as dt
import html, json, os, subprocess, shutil, uuid
from pathlib import Path
from urllib.parse import urlsplit

ART = Path(__file__).resolve().parents[1] / "art" / "BLACKTHORN-APPROVED-ROSIE-TATTOO.png"
TITLES={1:"NAMEHUNT",2:"SHADOWSEARCH",3:"VEILMAIL",4:"NUMBERHEX",5:"NETSPECTER",
        6:"GEOHUNT",7:"SIGNALTRACE",8:"PIXELCRYPT",9:"WEBSCOUT",10:"LINKFORGE",11:"CASEVAULT"}
def summary(module,result):
    if module==3 and result.get("email_domain"):
        return ("Email-domain format and public DNS inspected" if result.get("live_requested") else "Email-domain format inspected", "MX, SPF and DMARC describe public domain configuration, not mailbox existence.")
    if module==4 and result.get("digits"):
        return ("Telephone metadata analyzed", "Numbering validity does not establish subscriber identity or location.")
    if module==7 and result.get("bssid"):
        return ("BSSID identifier inspected", "Offline identifier flags are not wireless geolocation.")
    if module==10:
        count=len(result.get("retrieved_candidates", []))
        return (f"{count} public entity candidates" if count else result.get("status","No results"),
                "Public indexed entities may not represent the intended organization; verify independently.")
    if module==1:
        links=sum(map(len,result.get("categories",{}).values()))
        hits=len(result.get("retrieved_candidates",[]))
        return (f"{links} research pathways · {hits} unverified API candidates",
                "Search pathways are not retrieved matches. Manually verify any candidate.")
    if result.get('domain_registration', {}).get('status') == 'public registration record retrieved':
        n = len(result.get('retrieved_candidates', []))
        return (f"Domain registration found · {n} public index candidates",
                "RDAP registration information retrieved independently of Bing search. Registrant identity is not verified.")
    if "sources" in result:
        hits = len(result.get("retrieved_candidates", []))
        if hits:
            return (f"{hits} public index candidates · {len(result['sources'])} research pathways",
                    "Indexed titles and links are unverified; linked pages have not been independently checked.")
        if result.get("live_requested"):
            return (f"0 indexed candidates · {len(result['sources'])} research pathways",
                    "Live search returned no candidates or was unavailable. Research links remain available.")
        return (f"{len(result['sources'])} search pathways", "No results fetched; enable live search to try the public index.")
    if "public_addresses" in result:
        count=sum(map(len,result.get("records",{}).values()))
        return (f"{count} public DNS records · {len(result['public_addresses'])} public IPs","A domain can have DNS records even without a website address. DNS is not personal location.")
    if "map" in result: return ("Map created","Coordinates were supplied by the operator.")
    if "sha256" in result: return ("Local fingerprint","No data uploaded.")
    return (result.get("status","Local output"),"Evidence status depends on module.")
def show_summary(module,query,result,verbose=False):
    headline, explain = summary(module,result)
    print(f"\n◆ BLACKTHORN | {TITLES.get(module,'MODULE')} | {headline}")
    print(f"  Query: {query}\n  {explain}")
    registration = result.get('domain_registration')
    if registration:
        print('  [RDAP] ' + str(registration.get('status', 'unknown')))
        for key in ('domain', 'registrar', 'created', 'updated', 'expires', 'registry_id'):
            if registration.get(key):
                print('  [RDAP:' + key.upper() + '] ' + str(registration[key]))
        for ns in registration.get('nameservers', []):
            print('  [RDAP:NS] ' + ns)
        for status in registration.get('domain_statuses', []):
            print('  [RDAP:STATUS] ' + status)
        if registration.get('error'):
            print('  [RDAP:ERROR] ' + str(registration['error']))
        if registration.get('source'):
            print('  [RDAP:SOURCE] ' + str(registration['source']))
    candidates=result.get('retrieved_candidates',[])
    if candidates:
        counts={}
        for row in candidates:
            source=row.get('provider','Unknown')
            counts[source]=counts.get(source,0)+1
        for source,count in sorted(counts.items()):
            print(f"  [SOURCE] {source}: {count} unverified records")
        if module == 10:
            for idx,row in enumerate(candidates[:15],1):
                print(f"  [{idx:02d}] {row.get('title','Untitled')} | {row.get('evidence','')}")
                print(f"       {row.get('url','')} [UNVERIFIED]")
        if module == 9:
            print("  [INDEX] Public search-index candidates, not verified page contents:")
            for idx, row in enumerate(candidates, 1):
                title = ' '.join(str(row.get('title', 'Untitled')).split())
                url = str(row.get('url', ''))
                print(f"  [{idx:02d}] {title[:180]}")
                print(f"       {url}")
                print(f"       SOURCE: {row.get('provider', 'Unknown')} | STATUS: Unverified index entry")
            print(f"  [TOTAL] {len(candidates)} unverified candidate(s)")
    if module == 9 and result.get('live_requested'):
        print(f"  [FILTER] {result.get('excluded_irrelevant',0)} unrelated index entries excluded")
        if not candidates:
            print('  [NOTICE] No indexed titles/URLs matched the requested terms; this does not prove absence online.')
    for category,links in result.get('categories',{}).items():
        print(f"  [PATHWAYS] {category}: {len(links)}")
    for warning in result.get('provider_errors',[]):
        print('  [PROVIDER] '+warning)
    if 'public_addresses' in result:
        for ip in result['public_addresses']:print('  [DNS] '+ip)
    if 'records' in result:
        for kind, items in result['records'].items():
            for value in items:
                print(f'  [DNS:{kind}] {value}')
        for kind, error in result.get('resolver_errors',{}).items():
            if 'NXDOMAIN' in error: print(f'  [DNS:{kind}] {error}')
        if result.get('status') == 'lookup incomplete':
            print('  [INFO] DNS resolvers unavailable; check connection or retry.')
    if 'map' in result: print('  [MAP] '+result['map'])
    if 'sha256' in result: print('  [SHA256] '+result['sha256'])
    if 'status' in result: print('  [STATUS] '+str(result['status']))
    if 'sources' in result:print(f"  [LINKS] {len(result['sources'])} public research links")
    if 'saved' in result: print('  [SAVED] '+result['saved'])
    if verbose:
        print('  [VERBOSE] Full raw result:')
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print('  [INFO] Full details are available in the local evidence board and exports.')

def write_report(module,query,result,out,open_browser=False):
    dest=Path(out).expanduser()
    dest.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=dest/("BLACKTHORN-"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")+"-"+uuid.uuid4().hex[:6]+".html")
    esc=lambda x:html.escape(str(x),quote=True)
    header,description=summary(module,result)
    def link(url,label):
        if urlsplit(url).scheme!="https":return esc(label)
        return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'
    sections=[]
    for cat,items in result.get("categories",{}).items():
        elements=''.join(f'<li>{link(item["url"],item["label"])}<small>{esc(item["query"])}</small></li>' for item in items)
        sections.append(f'<section class="card"><h2>{esc(cat)}</h2><ul>{elements}</ul></section>')
    if result.get("retrieved_candidates"):
        elements=''.join(f'<li>{link(i["url"],i["provider"]+": "+i["title"])}<small>{esc(i.get("record_type", "public candidate"))} · {esc(i.get("relevance_label", "Unranked candidate"))} · {esc(i["evidence"])}</small></li>' for i in result["retrieved_candidates"])
        sections.insert(0,f'<section class="card found"><h2>Retrieved public records (unverified; not identity proof)</h2><ul>{elements}</ul></section>')
    for err in result.get("provider_errors",[]):
        sections.append('<p class="warn">Provider unavailable: '+esc(err)+'</p>')
    for key,url in result.get("sources",{}).items():
        sections.append('<section class="card">'+link(url,key)+'</section>')
    for key in ("public_addresses","map","sha256","note","status","hostname","file","bytes","saved","privacy","supplied_latitude","supplied_longitude"):
        if key in result:
            val=result[key]
            sections.append(f'<section class="card"><h2>{esc(key.replace("_"," ").title())}</h2><p>{esc(val)}</p></section>')
    if 'records' in result:
        for kind,items in result['records'].items():
            elements=''.join(f'<li>{esc(item)}</li>' for item in items)
            sections.append(f'<section class="card"><h2>DNS {esc(kind)} ({len(items)})</h2><ul>{elements or "<li>No answer from queried resolvers</li>"}</ul></section>')
        if result.get('resolver_errors'):
            sections.append('<section class="card"><h2>DNS resolver notes</h2><pre>'+esc(json.dumps(result['resolver_errors'],indent=2))+'</pre></section>')
    if "retrieved_candidates" in result and not result["retrieved_candidates"]:
        sections.append('<section class="card"><h2>No retrieved candidates</h2><p>Search links are leads only; enable live supported providers where available.</p></section>')
    if not sections:sections=['<section class="card"><p>No verified external results were retrieved.</p></section>']
    raw=esc(json.dumps(result,indent=2,ensure_ascii=False))
    # Embed the exact approved image so saved offline reports remain portable.
    photo = "data:image/png;base64," + base64.b64encode(ART.read_bytes()).decode("ascii") if ART.is_file() else ""
    art_panel = f'<div class="hero"><img src="{photo}" alt="Approved BLACKTHORN Rosie and wolf artwork"></div>' if photo else ""
    candidate_note = "No identity matches verified. Review candidates and confirm through independent public sources."

    page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>BLACKTHORN INTEL | {esc(TITLES.get(module,'RESULT'))}</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#08080d;color:#d9f9ff;font:15px system-ui;padding:24px}}
main{{max-width:1380px;margin:auto}}.hero{{border:1px solid #502749;border-radius:13px;overflow:hidden;margin:14px 0 24px;background:#09080f}}
.hero img{{display:block;width:100%;height:auto;object-fit:contain}}
header{{border-bottom:2px solid #ff1493;margin-bottom:20px;padding:10px}}
h1{{font-size:clamp(30px,6vw,60px);color:#ff1493;margin:0}}h2{{color:#50dfee;margin-top:0}}
small{{display:block;color:#98a3b9;padding:6px 0;overflow-wrap:anywhere}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
.card{{background:#13131d;border:1px solid #40344c;padding:22px;border-radius:12px;margin-bottom:16px;overflow-wrap:anywhere}}
.found{{border-color:#42d5dd}}.warn{{border-left:4px solid #ff1493;padding:12px}}
a{{color:#ff6ecb}}li{{margin:15px 0}}ul{{padding-left:22px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#a4b3c6}}
p{{overflow-wrap:anywhere}}.meta{{color:#53deed;letter-spacing:2px;font-size:12px}}
</style></head><body><main><header><div class="meta">GLITCHBYTE PHANTOM LABS // PUBLIC EVIDENCE</div>
<h1>BLACKTHORN INTEL</h1><p>{esc(TITLES.get(module,'RESULT'))} · v0.8.1</p></header>
{art_panel}
<div class="grid"><section class="card"><div class="meta">RESEARCH SUMMARY</div><h2>{esc(header)}</h2><p>{esc(description)}</p></section>
<section class="card"><div class="meta">SEARCH INPUT</div><h2>{esc(query)}</h2>
<p>Generated UTC {esc(dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))}</p></section></div>
<p class="warn">{esc(candidate_note)} Research leads are NOT proof of identity. No candidate should be treated as a confirmed match without independent corroboration.</p>
<div class="grid">{''.join(sections)}</div><details class="card"><summary>Technical output (JSON)</summary><pre>{raw}</pre></details>
<p class="meta">LOCAL REPORT · NO TRACKERS OR REMOTE SCRIPTS</p></main></body></html>"""
    with path.open("x",encoding="utf-8") as f:
        os.chmod(path,0o600)
        f.write(page)
    if open_browser and shutil.which("xdg-open"):
        try: subprocess.Popen(["xdg-open",str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        except OSError: print("[INFO] Saved HTML; open it manually.")
    return path
