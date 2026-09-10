"""TASK-AS01–AS04: immutable provider PNG source, never Patient Space.

Inventory order is numeric source filename order, not anatomical identification.
Overlapping folders remain alternate locations, not hash-proven equivalent bytes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.request import Request, urlopen
from zipfile import ZipFile, ZipInfo, ZIP_STORED

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://data.lhncbc.nlm.nih.gov/public/Visible-Human/Female-Images/'
REGIONS = ('abdomen', 'head', 'thorax', 'pelvis', 'thighs', 'legs')
ATTRIBUTION = 'Courtesy of the U.S. National Library of Medicine'
CLAIMS = dict(patientSpace=False, registeredCT=False, medicalValidation=False,
              medicalMaster=False, runtimeAsset=False)


def digest(data):
    return sha256(data).hexdigest()


def file_hash(path):
    h = sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def validate(value):
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT / 'schemas/assets' / (value['kind'] + '.v1.schema.json')).read_text())
    Draft202012Validator(schema).validate(value)
    return value


def write_json(path, value):
    validate(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.partial')
    tmp.write_bytes(encoded(value))
    tmp.replace(path)


class Listing(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr': self.row = {}
        if tag == 'td': self.cell = attrs.get('class')
        if tag == 'a' and self.row is not None: self.row['name'] = attrs.get('href', '')

    def handle_data(self, data):
        if self.row is not None and self.cell:
            self.row[self.cell] = self.row.get(self.cell, '') + data

    def handle_endtag(self, tag):
        if tag == 'td': self.cell = None
        if tag == 'tr' and self.row is not None:
            if 'name' in self.row: self.rows.append(self.row)
            self.row = None


def listing(path):
    parser = Listing()
    parser.feed(Path(path).read_text())
    return parser.rows


def source_order(name):
    match = re.fullmatch(r'avf(\d{4})([abc])\.png', name)
    if not match: raise ValueError('invalid source filename: ' + name)
    return int(match[1]) * 3 + 'abc'.index(match[2])


def inventory(evidence_dir, snapshot_at, chunk_size=64):
    if chunk_size < 1: raise ValueError('chunk size must be positive')
    p = Path(evidence_dir)
    urls = {'INDEX': BASE + 'INDEX', 'README': BASE + 'README',
            'fullcolor-readme.txt': BASE + 'Fullcolor/README',
            'terms.txt': 'https://www.nlm.nih.gov/databases/download/terms_and_conditions.html',
            'getting-data.txt': 'https://www.nlm.nih.gov/research/visible/getting_data.html',
            'overview.txt': 'https://www.nlm.nih.gov/research/visible/visible_human.html'}
    by_name = {}
    for region in REGIONS:
        key = f'png-{region}.txt'
        urls[key] = BASE + f'PNG_format/{region}/index.html'
        found = 0
        for row in listing(p / key):
            name = row['name']
            if not re.fullmatch(r'avf\d{4}[abc]\.png', name): continue
            found += 1
            src = dict(path=f'PNG_format/{region}/{name}',
                       url=BASE + f'PNG_format/{region}/{name}',
                       listedByteSize=int(row['size']), listedModified=row['date'])
            if name not in by_name:
                by_name[name] = dict(filename=name, source=src, alternateLocations=[], navigationRegions=[region])
            else:
                by_name[name]['alternateLocations'].append(src)
                by_name[name]['navigationRegions'].append(region)
        if not found: raise ValueError('empty source listing: ' + region)
    frames = sorted(by_name.values(), key=lambda f: source_order(f['filename']))
    for i, f in enumerate(frames): f.update(index=i, chunkIndex=i // chunk_size)
    observed = {source_order(f['filename']) for f in frames}
    missing = [f'avf{n//3:04d}{"abc"[n%3]}.png' for n in range(min(observed), max(observed)+1) if n not in observed]
    chunks = [dict(index=i//chunk_size, firstFrame=i, lastFrame=min(i+chunk_size,len(frames))-1,
                   frameCount=len(frames[i:i+chunk_size]),
                   listedByteSize=sum(f['source']['listedByteSize'] for f in frames[i:i+chunk_size]))
              for i in range(0,len(frames),chunk_size)]
    modalities = []
    for folder in ('radiological', 'PNG_format/radiological'):
        for modality in ('normalCT','normalCTHeaders','mri','mriHeaders'):
            key = folder.replace('/','-') + '-' + modality + '.txt'
            urls[key] = BASE + folder + '/' + modality + '/index.html'
            rows = [r for r in listing(p/key) if r.get('size','').isdigit()]
            modalities.append(dict(path=folder+'/'+modality, fileCount=len(rows),
                listedByteSize=sum(int(r['size']) for r in rows),
                status='inventoried-only; not acquired; registration unestablished'))
    evidence = [dict(filename=k,url=v,byteSize=(p/k).stat().st_size,sha256=file_hash(p/k)) for k,v in sorted(urls.items())]
    return validate(dict(schemaVersion='1',kind='vhf-whole-body-inventory',sourceArchiveId='source.nlm.vhp-female',
        snapshotAt=snapshot_at,coordinateSpace='source-image-stack',claims=dict(CLAIMS),
        terms=dict(url=urls['terms.txt'],attribution=ATTRIBUTION,publicDomainEvidenceUrl=urls['overview.txt'],
            conditions=['Attribute NLM conspicuously.', 'Do not imply NLM endorsement.',
                'Redistributed snapshot may not reflect current or accurate NLM data; display this notice.',
                'NLM provides no accuracy or fitness warranty; preserve applicable terms.'],
            scope='Public-domain VHP data; current NLM documentation removes access-license requirement since 2019. Modification, derivatives, commercial applications and redistribution remain subject to attribution, no endorsement and snapshot notice; not a medical approval.'),
        documentedGeometry=dict(widthPixels=2048,heightPixels=1216,nominalSpacingMm=0.33,
            evidence='Fullcolor/README and NLM overview; actual PNG IHDR checked on acquisition',
            limitation='Nominal spacing only; filename order does not establish origin, orientation, calibrated z position or CT registration.'),
        selectionPolicy='One provider PNG per filename; folder priority abdomen, head, thorax, pelvis, thighs, legs preserves A05 URLs. Alternate locations are listed but byte equivalence is not asserted. Raw and PNG radiology are inventory-only.',
        frameCount=len(frames),listedByteSize=sum(f['source']['listedByteSize'] for f in frames),
        chunkFrameLimit=chunk_size,frames=frames,chunks=chunks,missingWithinBounds=missing,supportingModalities=modalities,
        evidence=evidence,knownGaps=['NLM overview reports 5189 sections; current PNG listings and historical Fullcolor/fullbody INDEX enumerate 5186 unique sections.',
            'Interior missing filenames: '+', '.join(missing)+'. No interpolated replacements.',
            'Final observed section avf2730b; no inference that avf2730c exists.',
            'Directory names describe provider partitions, not validated anatomical regional labels.',
            'PNG provider encoding is retained; not claimed byte-identical to legacy raw.Z.',
            'Source archive is not a Medical Master. Supporting CT/MRI are not registered.']))


def check_inventory(inv):
    validate(inv)
    frames = inv['frames']
    if not frames or len(frames) != inv['frameCount']: raise ValueError('inventory frame count mismatch')
    if [f['index'] for f in frames] != list(range(len(frames))): raise ValueError('non-contiguous frame indices')
    names = [f['filename'] for f in frames]
    if names != sorted(set(names), key=source_order): raise ValueError('duplicate or unordered frames')
    if sum(f['source']['listedByteSize'] for f in frames) != inv['listedByteSize']: raise ValueError('inventory byte count mismatch')
    for f in frames:
        s = f['source']
        if s['url'] != BASE+s['path'] or s['path'] != f'PNG_format/{s["path"].split("/")[1]}/{f["filename"]}':
            raise ValueError('source URL/path mismatch')
        if s['path'].split('/')[1] not in REGIONS: raise ValueError('unknown source folder')
        if f['chunkIndex'] != f['index']//inv['chunkFrameLimit']: raise ValueError('invalid chunk membership')
    expected = []
    for i in range(0,len(frames),inv['chunkFrameLimit']):
        group=frames[i:i+inv['chunkFrameLimit']]
        expected.append(dict(index=len(expected),firstFrame=i,lastFrame=i+len(group)-1,frameCount=len(group),listedByteSize=sum(f['source']['listedByteSize'] for f in group)))
    if inv['chunks'] != expected: raise ValueError('invalid chunk plan')


def download_frame(frame, output):
    from PIL import Image
    src = frame['source']
    # Provider responses can be transiently incomplete/non-PNG during a multi-GB
    # acquisition. Retry the exact same authoritative URL only; never substitute
    # an alternate location whose byte equivalence has not been established.
    retry_delays = (1, 2, 4, 8, 12, 16, 24)
    for attempt in range(len(retry_delays) + 1):
        try:
            with urlopen(Request(src['url'], headers={
                'User-Agent':'procedural-human-source/1',
                'Accept':'image/png,application/octet-stream;q=0.9,*/*;q=0.1',
                'Cache-Control':'no-cache',
            }), timeout=90) as response:
                data=response.read(src['listedByteSize']+1)
                headers=response.headers
            if len(data)!=src['listedByteSize']: raise ValueError('source changed size: '+src['path'])
            with Image.open(io.BytesIO(data)) as im:
                if im.format!='PNG' or im.size!=(2048,1216): raise ValueError('unexpected PNG source geometry')
                im.verify()
            output.write_bytes(data)
            return dict(index=frame['index'],filename=frame['filename'],sourcePath=src['path'],sourceUrl=src['url'],
                sha256=digest(data),byteSize=len(data),widthPixels=2048,heightPixels=1216,
                retrievedAt=datetime.now(timezone.utc).isoformat(),lastModified=headers.get('Last-Modified'),etag=headers.get('ETag'))
        except (OSError,ValueError) as e:
            if attempt==len(retry_delays): raise RuntimeError('acquisition failed: '+src['path']) from e
            time.sleep(retry_delays[attempt])


def verify_chunk(path, inv, inventory_hash, chunk_index):
    planned=[f for f in inv['frames'] if f['chunkIndex']==chunk_index]
    if not planned: raise ValueError('chunk outside inventory')
    with ZipFile(path) as z:
        manifest_bytes=z.read('manifest.json')
        m=validate(json.loads(manifest_bytes))
        if m['inventorySha256']!=inventory_hash or m['chunkIndex']!=chunk_index: raise ValueError('chunk lineage mismatch')
        if len(m['frames'])!=len(planned): raise ValueError('incomplete chunk')
        expected=['manifest.json']+[f['source']['path'] for f in planned]
        if sorted(z.namelist())!=sorted(expected): raise ValueError('unexpected, duplicate or missing ZIP members')
        for f,r in zip(planned,m['frames']):
            if (r['index'],r['filename'],r['sourcePath'],r['sourceUrl'],r['byteSize']) != (f['index'],f['filename'],f['source']['path'],f['source']['url'],f['source']['listedByteSize']): raise ValueError('frame lineage mismatch')
            data=z.read(r['sourcePath'])
            if len(data)!=r['byteSize'] or digest(data)!=r['sha256']: raise ValueError('source integrity failure: '+r['sourcePath'])
    return m,digest(manifest_bytes)


def acquire(inv_path, output, first=0, last=None, workers=4):
    inv_path=Path(inv_path); inv=json.loads(inv_path.read_text()); check_inventory(inv)
    ih=file_hash(inv_path); output=Path(output); output.mkdir(parents=True,exist_ok=True)
    if last is None: last=len(inv['chunks'])-1
    if first<0 or last<first or last>=len(inv['chunks']): raise ValueError('invalid chunk range')
    if not 1<=workers<=8: raise ValueError('workers must be 1–8 bounded download threads')
    for ci in range(first,last+1):
        target=output/f'vhf-source-{ci:04d}.zip'
        if target.exists():
            verify_chunk(target,inv,ih,ci)
            print('verified existing '+target.name,flush=True); continue
        frames=[f for f in inv['frames'] if f['chunkIndex']==ci]
        with tempfile.TemporaryDirectory(dir=output) as tmp:
            tmp=Path(tmp)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                records=list(pool.map(lambda f:download_frame(f,tmp/f['filename']),frames))
            m=validate(dict(schemaVersion='1',kind='vhf-source-chunk',inventorySha256=ih,chunkIndex=ci,
                coordinateSpace='source-image-stack',claims=dict(CLAIMS),attribution=ATTRIBUTION,frames=records))
            partial=target.with_suffix('.partial')
            with ZipFile(partial,'w',compression=ZIP_STORED) as z:
                for f in frames:
                    info=ZipInfo(f['source']['path'],date_time=(1980,1,1,0,0,0)); info.external_attr=0o444<<16
                    z.writestr(info,(tmp/f['filename']).read_bytes())
                z.writestr(ZipInfo('manifest.json',date_time=(1980,1,1,0,0,0)),encoded(m))
            verify_chunk(partial,inv,ih,ci)
            partial.replace(target)
        print(f'completed chunk={ci} frames={len(records)} bytes={target.stat().st_size} sha256={file_hash(target)}',flush=True)


def archive_index(inv_path, directory):
    inv_path=Path(inv_path); inv=json.loads(inv_path.read_text()); check_inventory(inv); ih=file_hash(inv_path)
    chunks=[]; missing=[]
    for c in inv['chunks']:
        path=Path(directory)/f'vhf-source-{c["index"]:04d}.zip'
        if not path.exists(): missing.append(c['index']); continue
        m,mh=verify_chunk(path,inv,ih,c['index'])
        chunks.append(dict(index=c['index'],filename=path.name,sha256=file_hash(path),byteSize=path.stat().st_size,
            frameCount=len(m['frames']),manifestSha256=mh))
    return validate(dict(schemaVersion='1',kind='vhf-source-archive-index',inventorySha256=ih,
        coordinateSpace='source-image-stack',claims=dict(CLAIMS),expectedFrameCount=inv['frameCount'],
        verifiedFrameCount=sum(c['frameCount'] for c in chunks),complete=not missing,chunks=chunks,missingChunkIndices=missing))


def extract(inv_path, index_path, directory, output, first, last, crop=None):
    from PIL import Image
    inv_path=Path(inv_path); index_path=Path(index_path)
    inv=json.loads(inv_path.read_text()); check_inventory(inv); idx=validate(json.loads(index_path.read_text()))
    ih=file_hash(inv_path)
    if idx['inventorySha256']!=ih: raise ValueError('archive/inventory mismatch')
    if first<0 or last<first or last>=len(inv['frames']): raise ValueError('selection outside inventory')
    if crop is not None and (len(crop)!=4 or not 0<=crop[0]<crop[2]<=2048 or not 0<=crop[1]<crop[3]<=1216): raise ValueError('invalid source crop')
    output=Path(output)
    if output.exists(): raise ValueError('output must not exist; source never overwritten')
    selected=inv['frames'][first:last+1]
    # Verify every required chunk before emitting any derived output.
    chunks={c['index']:c for c in idx['chunks']}; verified={}
    for ci in sorted({f['chunkIndex'] for f in selected}):
        if ci not in chunks: raise ValueError('required chunk unavailable')
        c=chunks[ci]; path=Path(directory)/f'vhf-source-{ci:04d}.zip'
        if c['filename']!=path.name or file_hash(path)!=c['sha256']: raise ValueError('archive integrity failure')
        m,mh=verify_chunk(path,inv,ih,ci)
        if mh!=c['manifestSha256']: raise ValueError('manifest integrity failure')
        verified[ci]={r['index']:r for r in m['frames']}
    output.mkdir(parents=True); records=[]
    for f in selected:
        ci=f['chunkIndex']; c=chunks[ci]; r=verified[ci][f['index']]
        with ZipFile(Path(directory)/c['filename']) as z: data=z.read(r['sourcePath'])
        target=output/f['filename']
        if crop is None: target.write_bytes(data)
        else:
            with Image.open(io.BytesIO(data)) as im: im.crop(tuple(crop)).save(target,format='PNG',optimize=False)
        records.append(dict(index=f['index'],sourceFilename=f['filename'],sourcePath=r['sourcePath'],sourceSha256=r['sha256'],
            chunkSha256=c['sha256'],outputFilename=target.name,outputSha256=file_hash(target),
            derivation='byte-exact source copy' if crop is None else 'Pillow lossless rectangular crop; new derived PNG'))
    result=dict(schemaVersion='1',kind='vhf-source-region',inventorySha256=ih,archiveIndexSha256=file_hash(index_path),
        coordinateSpace='source-image-stack',claims=dict(CLAIMS),selection=dict(firstFrame=first,lastFrame=last,cropPixels=crop),frames=records)
    write_json(output/'region-manifest.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('inventory'); s.add_argument('--evidence',required=True); s.add_argument('--snapshot-at',required=True); s.add_argument('--output',required=True); s.add_argument('--chunk-size',type=int,default=64)
    s=sub.add_parser('acquire'); s.add_argument('--inventory',required=True); s.add_argument('--output',required=True); s.add_argument('--first',type=int,default=0); s.add_argument('--last',type=int); s.add_argument('--workers',type=int,default=4)
    s=sub.add_parser('index'); s.add_argument('--inventory',required=True); s.add_argument('--archive',required=True); s.add_argument('--output',required=True)
    s=sub.add_parser('extract'); s.add_argument('--inventory',required=True); s.add_argument('--index',required=True); s.add_argument('--archive',required=True); s.add_argument('--output',required=True); s.add_argument('--first',type=int,required=True); s.add_argument('--last',type=int,required=True); s.add_argument('--crop',type=int,nargs=4)
    a=p.parse_args()
    if a.command=='inventory': write_json(a.output,inventory(a.evidence,a.snapshot_at,a.chunk_size))
    elif a.command=='acquire': acquire(a.inventory,a.output,a.first,a.last,a.workers)
    elif a.command=='index': write_json(a.output,archive_index(a.inventory,a.archive))
    elif a.command=='extract': extract(a.inventory,a.index,a.archive,a.output,a.first,a.last,a.crop)


if __name__=='__main__': main()
