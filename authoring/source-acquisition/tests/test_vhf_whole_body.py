from pathlib import Path
import sys
import tempfile
import unittest
import json
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import vhf_whole_body as v


class WholeBodyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.p=Path(self.temp.name)
        self.inv_path=self.p/'inventory.json'
        # A bounded fixture uses the production contract but never network.
        self.inv=json.loads((v.ROOT/'authoring/source-archives/vhf-whole-body-inventory-20260910.json').read_text())
        self.inv['frames']=self.inv['frames'][:2]
        self.inv['frameCount']=2
        for f in self.inv['frames']: f['source']['listedByteSize']=len(f['filename'].encode())
        self.inv['listedByteSize']=sum(f['source']['listedByteSize'] for f in self.inv['frames'])
        self.inv['chunks']=[dict(index=0,firstFrame=0,lastFrame=1,frameCount=2,listedByteSize=self.inv['listedByteSize'])]
        v.write_json(self.inv_path,self.inv)
        self.ih=v.file_hash(self.inv_path)
        self.archive=self.p/'vhf-source-0000.zip'
        records=[]
        with ZipFile(self.archive,'w') as z:
            for f in self.inv['frames']:
                data=f['filename'].encode(); s=f['source']; z.writestr(s['path'],data)
                records.append(dict(index=f['index'],filename=f['filename'],sourcePath=s['path'],sourceUrl=s['url'],sha256=v.digest(data),byteSize=len(data),widthPixels=2048,heightPixels=1216,retrievedAt='2026-09-10T00:00:00Z',lastModified=None,etag=None))
            self.receipt=dict(schemaVersion='1',kind='vhf-source-chunk',inventorySha256=self.ih,chunkIndex=0,coordinateSpace='source-image-stack',claims=dict(v.CLAIMS),attribution=v.ATTRIBUTION,frames=records)
            z.writestr('manifest.json',v.encoded(self.receipt))

    def tearDown(self): self.temp.cleanup()

    def test_verified_archive_and_byte_exact_selection(self):
        idx=v.archive_index(self.inv_path,self.p)
        self.assertTrue(idx['complete']); self.assertEqual(idx['verifiedFrameCount'],2)
        index=self.p/'archive.json'; v.write_json(index,idx)
        out=self.p/'region'
        result=v.extract(self.inv_path,index,self.p,out,1,1)
        self.assertEqual((out/self.inv['frames'][1]['filename']).read_bytes(),self.inv['frames'][1]['filename'].encode())
        self.assertEqual(result['frames'][0]['sourceSha256'],result['frames'][0]['outputSha256'])
        with self.assertRaises(ValueError): v.extract(self.inv_path,index,self.p,out,1,1)

    def test_missing_chunk_never_complete(self):
        self.archive.unlink(); idx=v.archive_index(self.inv_path,self.p)
        self.assertFalse(idx['complete']); self.assertEqual(idx['missingChunkIndices'],[0])
        index=self.p/'archive.json'; v.write_json(index,idx)
        with self.assertRaises(ValueError): v.extract(self.inv_path,index,self.p,self.p/'no-output',0,1)
        self.assertFalse((self.p/'no-output').exists())

    def test_tampered_source_rejected(self):
        with ZipFile(self.archive,'r') as z: content={n:z.read(n) for n in z.namelist()}
        content[self.inv['frames'][0]['source']['path']]=b'tampered'
        with ZipFile(self.archive,'w') as z:
            for n,b in content.items():z.writestr(n,b)
        with self.assertRaises(ValueError): v.archive_index(self.inv_path,self.p)

    def test_foreign_inventory_rejected(self):
        with self.assertRaises(ValueError):v.verify_chunk(self.archive,self.inv,'0'*64,0)

    def test_manifest_cannot_claim_patient_space(self):
        self.receipt['claims']['patientSpace']=True
        with self.assertRaises(Exception):v.validate(self.receipt)

    def test_order_duplicates_chunk_and_url_rejected(self):
        for mutate in [lambda x:x['frames'].reverse(),lambda x:x['frames'][0]['source'].update(url='https://example.org/x'),lambda x:x['frames'][0].update(chunkIndex=1),lambda x:x['chunks'][0].update(frameCount=3)]:
            bad=json.loads(json.dumps(self.inv));mutate(bad)
            with self.assertRaises(ValueError):v.check_inventory(bad)

    def test_full_inventory_gaps_and_a05_preserved(self):
        inv=json.loads((v.ROOT/'authoring/source-archives/vhf-whole-body-inventory-20260910.json').read_text())
        v.check_inventory(inv)
        self.assertEqual(inv['frameCount'],5186)
        self.assertEqual(inv['missingWithinBounds'],['avf2328c.png','avf2329a.png','avf2329b.png'])
        wrist=[f for f in inv['frames'] if 'avf1567a.png'<=f['filename']<='avf1717a.png']
        self.assertEqual(len(wrist),451)
        self.assertTrue(all(f['source']['path'].startswith('PNG_format/abdomen/') for f in wrist))
        self.assertEqual(len(inv['chunks']),82)

    def test_range_and_crop_fail_before_writing(self):
        index=self.p/'archive.json'; v.write_json(index,v.archive_index(self.inv_path,self.p))
        for first,last,crop in [(-1,1,None),(1,0,None),(0,2,None),(0,1,[0,0,3000,10])]:
            with self.assertRaises(ValueError):v.extract(self.inv_path,index,self.p,self.p/'bad',first,last,crop)
        self.assertFalse((self.p/'bad').exists())


if __name__=='__main__':unittest.main()
