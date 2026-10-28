"""BLACKTHORN INTEL: public-source, privacy-first field console."""
import argparse
import datetime as dt
import ipaddress
import json
import os
import re
import socket
import urllib.request
import urllib.error
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from . import VERSION
from .hunt import namehunt, live_public_search
from .report import write_report
from .presentation import present

PINK="\033[95m"
CYAN="\033[96m"
GRAY="\033[90m"
RESET="\033[0m"
TOOL_ART = Path(__file__).resolve().parents[1] / "art" / "BLACKTHORN-TOOL-COMMAND-DECK.png"
BOARD_ART = Path(__file__).resolve().parents[1] / "art" / "BLACKTHORN-APPROVED-ROSIE-TATTOO.png"

BANNER=r"""
     .        *                   /\_/\
   *   .        .               ( o.o )   ✦
          /\                  ___ > ^ < ___
      /\ /  \ /\         .   /  BLACKTHORN \
     /  V /\ V  \           /  INTEL  v0.8.1 \
    /____/  \____\         /________________\
  +======================================================+
  |   GLITCHBYTE PHANTOM LABS // PUBLIC INTELLIGENCE     |
  |   ROSE SIGNAL ONLINE   •   EVIDENCE > ASSUMPTIONS    |
  +======================================================+
"""

MENU="""  ╔══════════════ BLACKTHORN // INTEL SWITCHBOARD ══════════════╗
  ║  [01] NAMEHUNT      Public name research and live sources           ║
  ║  [02] SHADOWSEARCH  Username/profile search references      ║
  ║  [03] VEILMAIL      Offline email-domain validation          ║
  ║  [04] NUMBERHEX     Offline number format analysis         ║
  ║  [05] NETSPECTER    Public DNS records (opt-in network)     ║
  ║  [06] GEOHUNT       Offline supplied coordinate map         ║
  ║  [07] SIGNALTRACE   Offline BSSID identifier inspection           ║
  ║  [08] PIXELCRYPT    Local image/file examination            ║
  ║  [09] WEBSCOUT      Public web links + opt-in indexed results           ║
  ║  [10] LINKFORGE     Public organization index (opt-in)  ║
  ║  [11] CASEVAULT     Save evidence notes to local JSON       ║
  ║  [12] TOOLKIT       Built-in help and examples              ║
  ║  [00] EXIT          Leave the console                        ║
  ╚═════════════════════════════════════════════════════════════╝
  Public sources only. Do not infer private location from a phone.
"""

EXAMPLES="""  ./RUN.sh
  ./RUN.sh --menu
  ./RUN.sh --cover            # Open full original Rosie art
  ./RUN.sh --original-cover   # Original Rosie-and-wolf art
  ./RUN.sh --board-art        # Original art in full-page HTML evidence board
  ./RUN.sh --terminal-art     # Optional low-detail terminal preview
  ./RUN.sh --module 1 --query "Example Person" --popup-results\n  ./RUN.sh --module 1 --query "Example Person" --live --popup-results
  ./RUN.sh --module 2 --query "example_handle" --dump --popup-results
  ./RUN.sh --module 3 --query "person@example.org"
  ./RUN.sh --module 4 --query "+1 415 555 2671"
  ./RUN.sh --module 5 --query "example.org" --live --dump --popup-results\n  ./RUN.sh --module 5 --query "jedisec.com" --live --verbose --dump --popup-results
  ./RUN.sh --module 6 --query "40.7128,-74.0060"
  ./RUN.sh --module 8 --query "./own-image.png"
  ./RUN.sh --module 9 --query "site:facebook.com Jedisec" --live --dump --popup-results
  ./RUN.sh --module 9 --query "site:github.com Jedisec" --dump
  ./RUN.sh --module 11 --query "Example case note" --out "./BlackthornReports"
"""

def paint(s, color, enabled=True):
    return (color+s+RESET) if enabled else s

def show_screen(color=True):
    print(paint(BANNER,PINK,color))
    print(paint(MENU,CYAN,color))

def webscout_relevance(query, candidates):
    """Keep only index entries that visibly match meaningful search terms.

    Search-index entries remain unverified; matching is not identity verification.
    """
    parts = re.findall(r'site:([^\s]+)|\"([^\"]+)\"|([^\s]+)', query, flags=re.I)
    terms = []
    sites = []
    for site, quoted, plain in parts:
        if site:
            sites.append(site.lower().lstrip('www.'))
        else:
            term = (quoted or plain).strip().lower()
            if term and term not in {'and', 'or', 'the', 'www'}:
                terms.append(term)
    # For unstructured 'facebook.com Jedisec', treat the platform as a site hint.
    for term in terms[:]:
        if term in {'facebook.com', 'www.facebook.com'}:
            sites.append('facebook.com')
            terms.remove(term)
    relevant, excluded = [], []
    for record in candidates:
        title=str(record.get('title','')).lower()
        url=str(record.get('url','')).lower()
        parsed=urllib.parse.urlsplit(url)
        host=(parsed.hostname or '').lower()
        site_ok=all(host == site or host.endswith('.'+site) for site in sites)
        # URL path may supply a match, but generic platform domain must not.
        path=urllib.parse.unquote(parsed.path).lower()
        description=str(record.get('description','')).lower()
        term_ok=all(term in (title+' '+path+' '+description) for term in terms) if terms else True
        if site_ok and term_ok:
            record['relevance_label']='Visible search-term match (unverified)'
            relevant.append(record)
        else:
            excluded.append(record)
    return relevant, excluded

def webscout_links(query, live=False, progress=None):
    """Multi-query public index discovery; never verifies identities or page content."""
    import html
    q = query.strip()
    if not (1 <= len(q) <= 250) or any(ord(c) < 32 for c in q):
        raise ValueError("WEBSCOUT expects 1-250 printable characters")
    encoded = urllib.parse.quote_plus(q)
    result = {
        "module": 9, "query": q, "status": "search links generated; no search results fetched",
        "mode": "public indexed-search discovery (unverified)",
        "sources": {
            "Google web search": "https://www.google.com/search?q=" + encoded,
            "Bing web search": "https://www.bing.com/search?q=" + encoded,
            "Brave web search": "https://search.brave.com/search?q=" + encoded,
            "DuckDuckGo web search": "https://duckduckgo.com/?q=" + encoded,
        },
        "retrieved_candidates": [], "provider_errors": [], "live_requested": bool(live),
        "note": "Index entries are unverified leads, not verified site content or identity matches."
    }
    if not live:
        return result

    # Limit scope and request volume. Try exact phrase, site-qualified query and
    # bare distinctive name, never invent a claimed result from a search link.
    variants = [q]
    site_match = re.match(r"^site:([^\s]+)\s+(.+)$", q, re.I)
    plain_match = re.match(r"^(?:https?://)?(?:www\.)?([\w-]+\.[\w.-]+)\s+(.+)$", q, re.I)
    exact_domain = re.fullmatch(r"(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)/?", q, re.I)
    if site_match:
        site, needle = site_match.groups()
        variants.extend(['"' + needle.strip('"') + '" site:' + site, '"' + needle.strip('"') + '"'])
    elif plain_match:
        site, needle = plain_match.groups()
        variants.extend(['site:' + site + ' ' + needle, '"' + needle.strip('"') + '" site:' + site])
    elif exact_domain:
        host = exact_domain.group(1).lower()
        variants.extend(['"' + host + '"', '"' + host.split('.')[0] + '"', 'site:' + host])
    elif not q.startswith('"'):
        variants.append('"' + q + '"')
    variants = list(dict.fromkeys(variants))[:4]
    result['attempted_queries'] = variants
    result['indexed_total'] = 0
    result['excluded_irrelevant'] = 0
    result['duplicate_entries'] = 0
    result['queries_completed'] = 0
    seen = set()
    gathered = []
    navigation_paths = ('/login', '/recover', '/r.php', '/login.php', '/login/identify', '/accounts/login')
    def is_navigation(url, title):
        p = urllib.parse.urlsplit(url)
        path = p.path.lower().rstrip('/')
        t = title.lower()
        return (not path or path == '/index.php' or any(path.startswith(x) for x in navigation_paths)
                or ('log in' in t and 'facebook' in t) or ('sign up' in t and 'facebook' in t))

    def get_rss(search):
        url = 'https://www.bing.com/search?' + urllib.parse.urlencode({'q': search, 'format':'rss'})
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; BlackthornPublicIndex/0.8.1)', 'Accept':'application/rss+xml, application/xml'})
        with urllib.request.urlopen(req, timeout=9) as response:
            payload = response.read(524289)
        if len(payload) > 524288:
            raise ValueError('RSS feed larger than 512 KiB')
        root = ET.fromstring(payload)
        items = []
        for item in root.findall('.//channel/item')[:30]:
            title = html.unescape((item.findtext('title') or '').strip())[:240]
            link = html.unescape((item.findtext('link') or '').strip())
            description = html.unescape((item.findtext('description') or '').strip())[:500]
            u = urllib.parse.urlsplit(link)
            if title and u.scheme == 'https' and u.hostname and not (u.username or u.password):
                items.append({'provider':'Bing RSS index', 'title':title, 'url':link,
                              'record_type':'public search-index candidate',
                              'description':description,
                              'evidence':'Indexed title, link and description; page not independently checked',
                              'identity_verified':False})
        return items

    for search in variants:
        if progress: progress('[LIVE] Bing RSS query: ' + search)
        try:
            records = get_rss(search)
            result['queries_completed'] += 1
            result['raw_entries_seen'] = result.get('raw_entries_seen', 0) + len(records)
            for item in records:
                p = urllib.parse.urlsplit(item['url'])
                normalized = (p.hostname or '').lower() + p.path.rstrip('/').lower()
                if normalized in seen:
                    result['duplicate_entries'] += 1
                    continue
                seen.add(normalized)
                gathered.append(item)
        except (OSError, ValueError, ET.ParseError, urllib.error.URLError, TimeoutError) as exc:
            result['provider_errors'].append('Bing RSS for ' + search[:70] + ': ' + type(exc).__name__ + ': ' + str(exc)[:120])
        if len(gathered) >= 60:
            break
    result['indexed_total'] = len(gathered)
    relevant, excluded = webscout_relevance(q, gathered)
    cleaned = []
    for entry in relevant:
        if is_navigation(entry['url'], entry['title']):
            excluded.append(entry)
        else:
            cleaned.append(entry)
    # Independent domain intelligence: report RDAP even if Bing index is irrelevant.
    if exact_domain:
        result['domain_registration'] = blackthorn_rdap_lookup(exact_domain.group(1), progress)
    result['retrieved_candidates'] = cleaned[:50]
    result['excluded_irrelevant'] = len(excluded)
    result['status'] = ('relevant public search-index candidates retrieved; unverified' if cleaned else
                        'no visibly relevant index entries retrieved' if result['queries_completed'] else
                        'live retrieval unavailable; search links remain available')
    if progress:
        progress('[LIVE] Queries complete: ' + str(result['queries_completed']) +
                 '; unique leads: ' + str(len(cleaned)) +
                 '; excluded: ' + str(len(excluded)) +
                 '; duplicates: ' + str(result['duplicate_entries']))
    return result

def blackthorn_rdap_lookup(domain, progress=None):
    """Public registration metadata, independent of search-index availability."""
    domain = domain.strip().lower()
    if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", domain):
        return {"status": "invalid hostname", "domain": domain}
    # For .com use the registry's published RDAP endpoint directly.
    # For other domains use IANA's public RDAP bootstrap redirect service.
    if domain.endswith('.com'):
        endpoint = 'https://rdap.verisign.com/com/v1/domain/' + urllib.parse.quote(domain)
    else:
        endpoint = 'https://rdap.org/domain/' + urllib.parse.quote(domain)
    if progress:
        progress('[RDAP] Checking public domain registration: ' + domain)
    try:
        request = urllib.request.Request(endpoint, headers={
            'User-Agent': 'BLACKTHORN-Public-Domain-Research/0.8.1',
            'Accept': 'application/rdap+json, application/json'})
        with urllib.request.urlopen(request, timeout=12) as response:
            if not response.geturl().startswith('https://'):
                raise ValueError('Insecure redirect declined')
            payload = response.read(524289)
        if len(payload) > 524288:
            raise ValueError('RDAP response too large')
        obj = json.loads(payload)
        if not isinstance(obj, dict) or not obj.get('ldhName'):
            raise ValueError('Invalid RDAP domain response')
        events = {}
        for event in obj.get('events', []):
            if isinstance(event, dict) and event.get('eventAction') and event.get('eventDate'):
                events[event['eventAction']] = event['eventDate']
        registrars = []
        for entity in obj.get('entities', []):
            if not isinstance(entity, dict) or 'registrar' not in entity.get('roles', []):
                continue
            card = entity.get('vcardArray', [])
            if isinstance(card, list) and len(card) == 2 and isinstance(card[1], list):
                registrars += [str(line[3]) for line in card[1]
                               if isinstance(line, list) and len(line) > 3 and line[0] in ('fn','org')]
            if not registrars and entity.get('handle'):
                registrars.append('Registrar handle: ' + str(entity['handle']))
        nss = sorted({str(ns.get('ldhName','')).lower() for ns in obj.get('nameservers', [])
                      if isinstance(ns, dict) and ns.get('ldhName')})
        return {
            'status': 'public registration record retrieved',
            'domain': str(obj.get('ldhName',domain)).lower(),
            'registry_id': str(obj.get('handle','')),
            'registrar': ', '.join(dict.fromkeys(registrars)) or 'Not specified in registry RDAP',
            'created': events.get('registration', 'Not listed'),
            'updated': events.get('last changed', 'Not listed'),
            'expires': events.get('expiration', 'Not listed'),
            'nameservers': nss,
            'domain_statuses': [str(x) for x in obj.get('status',[])][:20],
            'source': endpoint,
            'privacy_note': 'Registrar privacy service records do not identify a domain owner.'
        }
    except (OSError, ValueError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {'status': 'RDAP unavailable', 'domain': domain,
                'error': type(exc).__name__ + ': ' + str(exc)[:150], 'source': endpoint}

def reference_links(category, q):
    if not q or len(q)>250:
        raise ValueError("Provide a short research term (1–250 characters)")
    quoted=urllib.parse.quote_plus('"'+q+'"')
    sites={
        1: {"Web search":"https://www.google.com/search?q="+quoted,
            "Bing search":"https://www.bing.com/search?q="+quoted},
        2: {"Web username references":"https://www.google.com/search?q="+urllib.parse.quote_plus('"'+q+'" profile OR username'),
            "Bing username references":"https://www.bing.com/search?q="+quoted},
        3: {"Public email references":"https://www.google.com/search?q="+quoted,
            "Bing email references":"https://www.bing.com/search?q="+quoted},
        4: {"Public number references":"https://www.google.com/search?q="+quoted,
            "Bing number references":"https://www.bing.com/search?q="+quoted},
        9: {"Public site references":"https://www.google.com/search?q="+urllib.parse.quote_plus('site:'+q),
            "Bing site references":"https://www.bing.com/search?q="+urllib.parse.quote_plus('site:'+q)}
    }
    return {"module":category,"query":q,"mode":"search links only; no automatic scraping", "sources":sites[category]}

def domain_dns(host):
    """Opt-in public DNS record discovery, independent of web-host A/AAAA records.

    Uses DNS-over-HTTPS with two public resolvers; no extra Python packages.
    No hostname address resolution is required for the target domain.
    """
    host = host.strip().lower().rstrip(".")
    if host.startswith(("https://", "http://")):
        host = urllib.parse.urlsplit(host).hostname or ""
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError("Expected a valid public hostname") from None
    labels = host.split(".")
    if (len(host) > 253 or len(labels) < 2 or
        any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels) or
        not re.fullmatch(r"[a-z]{2,63}", labels[-1])):
        raise ValueError("Expected a public domain, e.g. example.org")
    types = {"A":1, "AAAA":28, "MX":15, "NS":2, "TXT":16, "CNAME":5, "SOA":6, "CAA":257}
    endpoints = ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve")
    records = {}
    errors = {}
    sources = {}
    rcode = {0:"NOERROR", 1:"FORMERR", 2:"SERVFAIL", 3:"NXDOMAIN", 4:"NOTIMP", 5:"REFUSED"}
    for name, number in types.items():
        messages=[]
        for endpoint in endpoints:
            url = endpoint + "?" + urllib.parse.urlencode({"name":host,"type":number})
            req=urllib.request.Request(url,headers={"Accept":"application/dns-json", "User-Agent":"BlackthornIntel/0.8.1"})
            try:
                with urllib.request.urlopen(req,timeout=5) as response:
                    payload=json.load(response)
                if not isinstance(payload,dict):
                    raise ValueError("Malformed resolver response")
                status=payload.get("Status")
                if not isinstance(status,int):
                    raise ValueError("Resolver omitted DNS status")
                if status not in (0,3):
                    messages.append(endpoint.split('/')[2]+": "+rcode.get(status,str(status)))
                    continue
                answers=payload.get("Answer",[])
                records[name] = [str(x.get("data",""))[:4096] for x in answers
                                 if isinstance(x,dict) and x.get("type")==number and x.get("data")]
                sources[name] = endpoint.split('/')[2]
                if status == 3:
                    errors[name] = "NXDOMAIN (no such DNS name)"
                break
            except (OSError, ValueError, TimeoutError, urllib.error.URLError) as exc:
                messages.append(endpoint.split('/')[2]+": "+str(exc)[:160])
        else:
            records[name]=[]
            errors[name]="; ".join(messages) or "No DNS response"
    addresses=[]
    for name in ("A", "AAAA"):
        for item in records[name]:
            try:
                ip=ipaddress.ip_address(item)
            except ValueError:
                continue
            if ip.is_global:
                addresses.append(str(ip))
    found=sum(len(items) for items in records.values())
    return {"hostname":host, "status": "records found" if found else ("lookup incomplete" if errors else "no matching records"),
            "public_addresses":sorted(set(addresses)), "records":records, "resolver_errors":errors,
            "resolvers_used":sources,
            "note":"Public DNS only. No A/AAAA address does not imply missing MX, NS or TXT records; historical intel requires separate sources. DNS is not identity or device GPS."}

def coordinates(value):
    try:
        values = [x.strip() for x in value.split(",")]
        if len(values) != 2: raise ValueError()
        lat,lon = map(float,values)
    except (TypeError, ValueError):
        raise ValueError("GEOHUNT expects LAT,LON, for example 40.7128,-74.0060. For a domain use [05] NETSPECTER.") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordinates outside valid latitude/longitude ranges")
    return {"supplied_latitude":lat,"supplied_longitude":lon,
            "map":"https://www.openstreetmap.org/?mlat="+str(lat)+"&mlon="+str(lon)+"#map=12/"+str(lat)+"/"+str(lon),
            "note":"Map for coordinates you supplied; no tracking performed"}

def image_info(name):
    p=Path(name).expanduser()
    if not p.is_file():
        raise ValueError("Local image not found")
    if p.stat().st_size>50_000_000:
        raise ValueError("Maximum supported file size is 50 MB")
    import hashlib
    with p.open("rb") as f:
        digest=hashlib.sha256(f.read()).hexdigest()
    return {"file":p.name,"bytes":p.stat().st_size,"sha256":digest,
            "note":"Local file fingerprint only; not uploaded"}

def save_note(note,out):
    if not note.strip() or len(note)>10000:
        raise ValueError("Provide a note of 1–10000 characters")
    dest=Path(out).expanduser()
    dest.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=dest/("BLACKTHORN-CASE-"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")+".json")
    data={"tool":"BLACKTHORN INTEL","version":VERSION,"timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
          "note":note,"status":"unverified user-supplied note"}
    with path.open("x",encoding="utf-8") as f:
        os.chmod(path,0o600)
        json.dump(data,f,indent=2)
    return {"saved":str(path),"privacy":"local report, owner-only permissions"}


# BLACKTHORN LEGACY MOD RECOVERY v1
# Original LittleBrother capabilities reimplemented without obsolete scrapers.
# BLACKTHORN VEILMAIL PUBLIC DNS v1

def veilmail_metadata(query, live=False, progress=None):
    """Format validation and optional public domain mail policy research.

    No mailbox verification, message sending, inbox access or account probing.
    """
    from email.utils import parseaddr
    raw=query.strip()
    _display,address=parseaddr(raw)
    if not raw or address!=raw or len(raw)>254 or not re.fullmatch(r"[^\s@]+@[^\s@]+",raw):
        raise ValueError('VEILMAIL expects a plain email address such as user@example.org')
    local,domain=raw.rsplit('@',1)
    domain=domain.lower().rstrip('.')
    try: domain=domain.encode('idna').decode('ascii')
    except UnicodeError: raise ValueError('Invalid email domain') from None
    if not local or len(local)>64 or len(domain)>253 or '.' not in domain or not all(
        re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',x) for x in domain.split('.')):
        raise ValueError('Invalid email structure')
    result={'module':3,'email':raw,'email_domain':domain,'local_part_length':len(local),
        'syntax':'plausible format only','verified_mailbox':False,
        'live_requested':bool(live),'records':{},'provider_errors':[],
        'status':'local format analyzed; domain DNS not requested',
        'note':'Public DNS never verifies a mailbox or identifies a person.'}
    if not live: return result
    # Public DNS-over-HTTPS; no API key or third-party Python dependencies.
    import urllib.parse, urllib.request, urllib.error
    lookups=[('MX',domain,'MX'),('SPF',domain,'TXT'),('DMARC','_dmarc.'+domain,'TXT')]
    for tag,host,kind in lookups:
        if progress: progress('[LIVE] VEILMAIL '+tag+' public DNS: '+host)
        url='https://cloudflare-dns.com/dns-query?'+urllib.parse.urlencode({'name':host,'type':kind})
        req=urllib.request.Request(url,headers={'Accept':'application/dns-json',
            'User-Agent':'BlackthornPublicResearch/0.8.1 (public mail DNS inspection)'})
        try:
            with urllib.request.urlopen(req,timeout=6) as conn:
                raw_response=conn.read(100001)
            if len(raw_response)>100000: raise ValueError('DNS response exceeded limit')
            payload=json.loads(raw_response)
            if not isinstance(payload,dict): raise ValueError('Invalid DNS response')
            if payload.get('Status') not in (0,3):
                raise ValueError('DNS response status '+str(payload.get('Status')))
            matches=[]
            for answer in payload.get('Answer',[])[:40]:
                if not isinstance(answer,dict):continue
                if answer.get('type') != (15 if kind=='MX' else 16):continue
                value=str(answer.get('data','')).strip().strip('"')[:1000]
                if tag=='SPF' and not value.lower().startswith('v=spf1'):continue
                if tag=='DMARC' and not value.lower().startswith('v=dmarc1'):continue
                if value and value not in matches:matches.append(value)
            result['records'][tag]=matches[:15]
        except (OSError,TimeoutError,ValueError,urllib.error.URLError,json.JSONDecodeError) as exc:
            result['provider_errors'].append(tag+': '+type(exc).__name__+': '+str(exc)[:120])
            result['records'][tag]=[]
    result['status']=('public mail DNS retrieved' if any(result['records'].values()) else
                      'public mail DNS unavailable or no published records')
    result['provider']='Cloudflare public DNS-over-HTTPS'
    result['source']='https://cloudflare-dns.com/dns-query'
    return result


def numberhex_metadata(query):
    """Local international telephone formatting with optional phonenumbers package."""
    raw=query.strip()
    if not re.fullmatch(r'\+?[\d\s().-]{7,28}',raw):
        raise ValueError('NUMBERHEX expects a phone number, preferably +countrycode')
    digits=re.sub(r'\D','',raw)
    if not 7<=len(digits)<=15: raise ValueError('Phone number length out of range')
    result={'module':4,'input':raw,'digits':digits,'international_prefix':raw.startswith('+'),
            'subscriber_identified':False, 'live_location':False,
            'note':'Number metadata does not identify a subscriber or track a phone.'}
    try:
        import phonenumbers
        parsed=phonenumbers.parse(raw,None if raw.startswith('+') else 'US')
        result.update({'e164':phonenumbers.format_number(parsed,phonenumbers.PhoneNumberFormat.E164),
            'possible_number':phonenumbers.is_possible_number(parsed),
            'valid_numbering_pattern':phonenumbers.is_valid_number(parsed),
            'country_code':parsed.country_code})
    except ImportError:
        result['metadata_note']='Optional phonenumbers package unavailable; basic validation only'
    except Exception as exc:
        result['metadata_note']='Could not interpret number: '+type(exc).__name__
    return result

def signaltrace_identifier(query):
    """Validate a supplied Wi-Fi BSSID locally. No location or tracking services."""
    raw=query.strip()
    hexchars=re.sub(r'[:-]','',raw).lower()
    if not re.fullmatch('[a-f0-9]{12}',hexchars):
        raise ValueError('SIGNALTRACE expects a 12-digit hexadecimal BSSID, e.g. 00:11:22:33:44:55')
    octets=[int(hexchars[i:i+2],16) for i in range(0,12,2)]
    return {'module':7,'bssid':':'.join(hexchars[i:i+2] for i in range(0,12,2)),
        'organizational_prefix':':'.join(hexchars[i:i+2] for i in range(0,6,2)),
        'locally_administered':bool(octets[0]&2),'multicast':bool(octets[0]&1),
        'note':'Offline identifier inspection only; MAC/BSSID is not proof of physical location.'}

# BLACKTHORN FIELD REPAIR v2

def linkforge_organization(query,live=False,progress=None):
    """Search public organization *candidates*, with a secondary Wikimedia endpoint.
    No account login, employees, or identity claims. Network only when live=True.
    """
    q=query.strip()
    if not (2<=len(q)<=100) or any(ord(c)<32 for c in q):
        raise ValueError('LINKFORGE expects an organization name (2-100 printable characters)')
    result={'module':10,'query':q,'retrieved_candidates':[],
            'status':'network not requested', 'provider_errors':[],
            'providers_attempted':[], 'note':'Public entity names are candidates only; not verified organizations or employee identities.'}
    if not live: return result
    import urllib.error
    endpoints=(
       ('Wikidata entity search','https://www.wikidata.org/w/api.php'),
       ('Wikimedia Commons entity search','https://commons.wikimedia.org/w/api.php'),
    )
    for label,base in endpoints:
        result['providers_attempted'].append(label)
        if progress: progress('[LIVE] LINKFORGE querying '+label)
        url=base+'?'+urllib.parse.urlencode({'action':'wbsearchentities','search':q,'language':'en',
                                              'format':'json','limit':10,'type':'item'})
        req=urllib.request.Request(url,headers={'User-Agent':'BlackthornPublicResearch/0.8.1 (public Wikimedia research; contact via repository)',
                                                  'Accept':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=7) as response:
                raw=response.read(200001)
            if len(raw)>200000: raise ValueError('Response exceeded 200 KB limit')
            entries=json.loads(raw).get('search',[])
            if not isinstance(entries,list): raise ValueError('Malformed entity response')
            for item in entries:
                if not isinstance(item,dict):continue
                entity_id=str(item.get('id',''))
                if not re.fullmatch(r'Q[0-9]+',entity_id):continue
                title=str(item.get('label',''))[:200]
                desc=str(item.get('description',''))[:400]
                result['retrieved_candidates'].append({
                    'provider':label, 'record_type':'public entity candidate',
                    'title':title, 'url':'https://www.wikidata.org/wiki/'+entity_id,
                    'evidence':desc or 'Description unavailable',
                    'relevance_label':'unverified public entity result',
                    'identity_verified':False})
            # A valid empty result is not a service outage; do not force fallback.
            result['status']=('public entity candidates retrieved; unverified' if result['retrieved_candidates']
                              else 'no public entity candidates returned')
            result['provider_used']=label
            break
        except (OSError,ValueError,TimeoutError,urllib.error.URLError) as exc:
            result['provider_errors'].append(label+': '+type(exc).__name__+': '+str(exc)[:120])
    else:
        result['status']='public sources unavailable'
    return result


def execute(module,query,live=False,out="./BlackthornReports",per_provider=100,progress=None):
    if module==1:
        return namehunt(query, live=live, per_provider=per_provider, progress=progress)
    if module==9:
        return webscout_links(query, live=live, progress=progress)
    if module==2:
        return reference_links(module,query)
    if module==3:
        return veilmail_metadata(query,live=live,progress=progress)
    if module==4:
        return numberhex_metadata(query)
    if module==5:
        if not live:
            return {"status":"network not used","next":"Add --live to resolve public DNS"}
        return domain_dns(query)
    if module==6:
        return coordinates(query)
    if module==8:
        return image_info(query)
    if module==11:
        # BLACKTHORN CASEVAULT PROFILE RECOVERY v1
        if query.strip().split(' ',1)[0].lower() in ('help','list','create','show','note','link'):
            from .casevault import run as casevault_run
            return casevault_run(query,out)
        return save_note(query,out)
    if module==7:
        return signaltrace_identifier(query)
    if module==10:
        return linkforge_organization(query,live=live,progress=progress)
    if module==12:
        return {"examples":EXAMPLES}
    raise ValueError("Choose a module number from 1–12")

def show_picture(terminal=False, board=False):
    art = BOARD_ART if board else TOOL_ART
    import shutil, subprocess
    if terminal:
        if not shutil.which("chafa"):
            print("[INFO] 'chafa' is optional. Debian install: sudo apt install chafa")
            print("[FALLBACK] Terminal banner available with --menu")
            return 0
        return subprocess.run(["chafa","--size","80x32",str(art)],check=False).returncode
    if not shutil.which("xdg-open"):
        print("[INFO] xdg-open unavailable. Artwork file:", art)
        return 0
    try:
        subprocess.Popen(["xdg-open",str(art)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        print("[INFO] Could not start picture viewer. Use --no-art for console-only mode.")
        return 1
    print("[ART] Opening approved full-resolution " + ("original Rosie artwork" if board else "tool command-deck artwork") + ".")
    return 0

def interactive_console():
    """Local opt-in operator console; no action until a numbered choice is selected."""
    while True:
        try:
            raw=input("\n  BLACKTHORN [00-12] > ").strip()
        except (EOFError,KeyboardInterrupt):
            print("\n[EXIT] Signal closed.")
            return 0
        if raw in ("0","00","exit","quit","q"):
            print("[EXIT] Signal closed.")
            return 0
        if not raw.isdigit() or int(raw) not in range(1,13):
            print("[INFO] Choose 01-12 or 00 to exit.")
            continue
        module=int(raw)
        if module==12:
            print(EXAMPLES)
            continue
        try:
            q=input("  QUERY > ").strip()
            if not q:
                print("[INFO] Empty query, returning to menu.")
                continue
            if module in (1,3,5,9,10):
                question = ("  Live public-source discovery? [y/N] > " if module==1 else
                            "  Public mail DNS lookup? [y/N] > " if module==3 else
                            "  Public DNS network lookup? [y/N] > " if module==5 else
                            "  Fetch public indexed search results? [y/N] > " if module==9 else
                            "  Look up public organizational data? [y/N] > ")
                opt=input(question).strip().lower()=="y"
            else:
                opt=False
            count=100
            if module==1 and opt:
                raw_count=input("  Records per provider [100, up to 1000] > ").strip()
                if raw_count:count=int(raw_count)
            value=execute(module,q,live=opt,per_provider=count,progress=print if opt and module in (1,3,9,10) else None)
            option=input("  Full terminal stream? [y/N] > ").strip().lower()=="y"
            present(module,q,value,"./BlackthornReports",verbose=option,
                    dump=True,popup=module in (1,2,3,4,5,6,8,9,11),html=False)
        except (ValueError,OSError,UnicodeError) as exc:
            print("[ERROR] "+str(exc))
        except (EOFError,KeyboardInterrupt):
            print("\n[EXIT] Signal closed.")
            return 0

def main(argv=None):
    parser=argparse.ArgumentParser(prog="blackthorn",description="Public-source field intelligence suite")
    parser.add_argument("--menu",action="store_true",help="Show full ASCII splash and numbered options")
    parser.add_argument("--cover",action="store_true",help="Open approved professional tool command-deck image")
    parser.add_argument("--original-cover",action="store_true",help="Open approved original Rosie and wolf artwork used on reports")
    parser.add_argument("--terminal-art",action="store_true",help="Show the real cover as terminal image, if chafa installed")
    parser.add_argument("--no-banner",action="store_true")
    parser.add_argument("--no-art",action="store_true",help="Do not open artwork on startup")
    parser.add_argument("--module",type=int,help="Module number (1–12)")
    parser.add_argument("--query",help="Name, public identifier, hostname, coordinates, note or file")
    parser.add_argument("--live",action="store_true",help="Enable public DNS for module 5 or indexed search results for module 9")
    parser.add_argument("--per-provider",type=int,default=100,help="Live NAMEHUNT results per provider, default 100, max 1000")
    parser.add_argument("--dump",action="store_true",help="Save full JSON, JSONL, CSV exports for any implemented module")
    parser.add_argument("--verbose",action="store_true",help="Print all available records and raw module data")
    parser.add_argument("--brief",action="store_true",help="Only live progress and concise summary (default)")
    parser.add_argument("--out",default="./BlackthornReports",help="Local case report directory")
    parser.add_argument("--popup-results",action="store_true",help="Save and open a local evidence board")
    parser.add_argument("--save-html",action="store_true",help="Save an HTML evidence board without opening it")
    parser.add_argument("--board-art",action="store_true",help="Create a standalone pop-out board using approved artwork, no research")
    parser.add_argument("--examples",action="store_true")
    parser.add_argument("--version",action="version",version="BLACKTHORN "+VERSION)
    args=parser.parse_args(argv)
    color=sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    if args.board_art:
        dest=write_report(12,"BLACKTHORN INTEL",{"status":"Illustrated module roadmap, no research executed"},args.out,open_browser=True)
        print("[BOARD] Opened artwork board: "+str(dest))
        return 0
    if args.cover:return show_picture()
    if args.original_cover:return show_picture(board=True)
    if args.terminal_art:return show_picture(True)
    if args.examples:
        print(EXAMPLES)
        return 0
    if args.menu or args.module is None:
        if not args.no_art and not args.no_banner and sys.stdout.isatty() and os.environ.get("DISPLAY", "") + os.environ.get("WAYLAND_DISPLAY", ""):
            show_picture()
        show_screen(color)
        if args.module is None:
            if not args.menu and sys.stdin.isatty():
                return interactive_console()
            return 0
    if not args.no_banner and not args.menu:
        print(paint("  ◆ BLACKTHORN INTEL // PUBLIC SIGNAL ACTIVE",PINK,color))
    if args.module==12:
        print(EXAMPLES)
        return 0
    if not args.query:
        parser.error("--module requires --query (except module 12)")
    try:
        answer=execute(args.module,args.query,args.live,args.out,args.per_provider,print if args.live and args.module in (1,3,9,10) else None)
    except (ValueError, OSError, UnicodeError) as exc:
        print("[ERROR] "+str(exc),file=sys.stderr)
        return 2
    present(args.module,args.query or "",answer,args.out,verbose=args.verbose,
            dump=args.dump,popup=args.popup_results,html=args.save_html)
    return 0
