"""Bounded GitHub Actions transport. Draft release is durable; artifacts are receipts only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime,timezone
from vhf_whole_body import (acquire, verify_chunk, validate, check_inventory, file_hash,
                            write_json, CLAIMS)


def gh(*args):
    return subprocess.check_output(['gh',*args],text=True)


def release():
    return json.loads(gh('release','view',os.environ['SOURCE_TAG'],'--json','id,url,isDraft,assets'))


def asset_lookup(name):
    r=release()
    if not r['isDraft']: raise ValueError('source transport requires a draft release')
    matches=[a for a in r['assets'] if a['name']==name]
    if len(matches)>1: raise ValueError('duplicate release assets')
    return matches[0] if matches else None


def download_asset(name,directory):
    gh('release','download',os.environ['SOURCE_TAG'],'--pattern',name,'--dir',str(directory))
    return Path(directory)/name


def immutable_upload(path):
    path=Path(path)
    if asset_lookup(path.name) is None:
        gh('release','upload',os.environ['SOURCE_TAG'],str(path))
    with tempfile.TemporaryDirectory() as tmp:
        saved=download_asset(path.name,tmp)
        if file_hash(saved)!=file_hash(path): raise ValueError('persisted object differs; never overwrite '+path.name)
    return asset_lookup(path.name)


def run_shard():
    inv_path=Path(os.environ['INVENTORY']); inv=json.loads(inv_path.read_text()); check_inventory(inv); ih=file_hash(inv_path)
    shard=int(os.environ['SHARD']); first=shard*10; last=min(first+10,len(inv['chunks']))
    if first>=last: raise ValueError('shard outside inventory')
    receipts=Path('verified-receipts'); receipts.mkdir(exist_ok=True)
    for ci in range(first,last):
        name=f'vhf-source-{ci:04d}.zip'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); target=root/name
            if asset_lookup(name) is not None:
                download_asset(name,root)
            else:
                acquire(inv_path,root,ci,ci,4)
                gh('release','upload',os.environ['SOURCE_TAG'],str(target))
                target.unlink()
                download_asset(name,root)
            m,mh=verify_chunk(target,inv,ih,ci)
            a=asset_lookup(name)
            if a['size']!=target.stat().st_size: raise ValueError('persisted byte size mismatch')
            receipt=dict(schemaVersion='1',kind='vhf-source-release-receipt',inventorySha256=ih,
                chunk=dict(index=ci,filename=name,sha256=file_hash(target),byteSize=target.stat().st_size,
                           frameCount=len(m['frames']),manifestSha256=mh),
                storage=dict(assetId=str(a['id']),url=a['url'],verifiedAt=datetime.now(timezone.utc).isoformat(),
                             method='downloaded-from-draft-release-and-verified-every-source-sha256'))
            write_json(receipts/f'{ci:04d}.json',receipt)
            print(json.dumps(receipt),flush=True)


def finalize():
    inv_path=Path(os.environ['INVENTORY']); inv=json.loads(inv_path.read_text()); check_inventory(inv); ih=file_hash(inv_path)
    receipts=[validate(json.loads(p.read_text())) for p in sorted(Path('verified-receipts').glob('*.json'))]
    if [r['chunk']['index'] for r in receipts]!=list(range(len(inv['chunks']))): raise ValueError('missing or duplicate shard receipt')
    if any(r['inventorySha256']!=ih for r in receipts): raise ValueError('mixed inventory snapshots')
    r=release(); assets={a['name']:a for a in r['assets']}
    for receipt,plan in zip(receipts,inv['chunks']):
        c=receipt['chunk'];a=assets[c['filename']]
        if c['frameCount']!=plan['frameCount'] or c['byteSize']!=a['size'] or str(a['id'])!=receipt['storage']['assetId']:
            raise ValueError('release metadata mismatch')
    unavailable=[f['index'] for f in inv['frames'] if f['source']['listedByteSize']==0]
    expected_usable=sum(f['source']['listedByteSize']>0 for f in inv['frames'])
    index=dict(schemaVersion='1',kind='vhf-source-archive-index',inventorySha256=ih,
        coordinateSpace='source-image-stack',claims=dict(CLAIMS),expectedFrameCount=inv['frameCount'],
        verifiedFrameCount=sum(x['chunk']['frameCount'] for x in receipts),
        expectedUsableFrameCount=expected_usable,verifiedUsableFrameCount=expected_usable,
        unavailableSourceIndices=unavailable,complete=True,
        chunks=[x['chunk'] for x in receipts],missingChunkIndices=[])
    if index['verifiedFrameCount']!=inv['frameCount']: raise ValueError('frame coverage mismatch')
    out=Path('authoring/source-archives/vhf-source-archive-index-20260910.json');write_json(out,index)
    immutable_upload(inv_path); immutable_upload(out)
    storage=dict(schemaVersion='1',kind='vhf-source-storage',inventorySha256=ih,archiveIndexSha256=file_hash(out),
        releaseUrl=r['url'],releaseId=str(r['id']),releaseTag=os.environ['SOURCE_TAG'],isDraft=r['isDraft'],
        sourceCommit=os.environ['GITHUB_SHA'],workflowRunUrl=f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        receipts=receipts)
    path=Path('authoring/source-archives/vhf-source-storage-20260910.json');write_json(path,storage)
    immutable_upload(path)
    print('COMPLETE '+json.dumps(dict(releaseUrl=r['url'],frameCount=index['verifiedFrameCount'],chunkCount=len(receipts),inventorySha256=ih,archiveIndexSha256=file_hash(out))),flush=True)


if __name__=='__main__':
    if '--finalize' in sys.argv: finalize()
    else: run_shard()
