#!/usr/bin/env python3
"""Partition Trizium fallbacks, including a previously partitioned neighboring archive."""
import argparse
import json
from collections import Counter
from pathlib import Path
from split_caelitus_fallback import ROOT, decode, sha
from split_banpo_fallbacks import partition
from split_prestige_fallbacks import replay, triangle_signatures, canonical_sha
from publish_bespoke_models import replace_batch, encoded, read


def prepare():
    folder=ROOT/'public/models';base=read(folder/'manifest.json');matches=read(folder/'footprint-matches.json');current=read(folder/'generic-corrections.json')
    identity=read(ROOT/'docs/model-audit/jamsil-trizium-source-identity.json');towers={t['number']:t['sourceId'] for t in identity['towers']}
    assert len(towers)==45 and 304 not in towers
    source=next(a for a in base['assets'] if a['id']=='apt-a13822002')
    assert source['sha256']=='55e71d045111ca044ca96ec12a043bbdb024e6c574e97fe127d58212ce451937'
    numbers=[n for n,fid in towers.items() if fid in matches[source['id']]]
    assert numbers==list(range(317,326))+list(range(327,332))
    cfg={'site':'jamsil-trizium-main','source':source['id'],'sha':source['sha256'],'count':49,'removeApartmentCode':True,
         'remainingName':'트리지움 대상 외 원천 건물 (기존 추정 모형)',
         'parts':[(f'fallback-jamsil-trizium-{n}',f'잠실트리지움 {n}동',towers[n]) for n in numbers],
         'limits':['Only archived indexed triangles are partitioned. Unrelated source buildings keep their original attributes/materials and shared terrain anchor.','No photo-model credit for fallback partitions. Number304 remains unbound.']}
    correction,documents,proof=partition(cfg,folder,base,matches)
    original=(folder/source['model']).read_bytes();owners,authoring=replay(source,original,matches[source['id']],'docs/DISTRICT_LANDMARK_PROVENANCE.json')
    gltf,primitives=decode(original);signatures={fid:Counter() for fid in matches[source['id']]}
    for primitive,attributes,indices in primitives:
        assert len(owners[primitive['material']])==len(indices)
        material=json.dumps(gltf['materials'][primitive['material']],sort_keys=True,separators=(',',':')).encode()
        for fid,index in zip(owners[primitive['material']],indices):
            signatures[fid][sha(material+b''.join(k.encode()+attributes[k][index].tobytes() for k in sorted(attributes)))]+=1
    for asset in correction['assets']:
        expected=sum((signatures[fid] for fid in asset['footprintIds']),Counter())
        assert triangle_signatures(documents[folder/asset['model']])==expected
    proof['sourceAuthoringReplay']=authoring
    documents[ROOT/'docs/model-audit/jamsil-trizium-main-generic-split.json']=encoded(proof)
    prior=next(c for c in current['corrections'] if c['sourceId']=='apt-a13822003')
    residual=next(a for a in prior['assets'] if a['id']==prior['sourceId'])
    assert residual['sha256']=='08e7245fc08dd4b90b563daf9402e8456d8d2b56c2f31a306950e64fee84751e'
    assert len(residual['footprintIds'])==3 and towers[305] in residual['footprintIds']
    preserved=[fid for fid in residual['footprintIds'] if fid!=towers[305]]
    cfg={'site':'jamsil-trizium-305','source':residual['id'],'sha':residual['sha256'],'count':3,'removeApartmentCode':True,
         'parts':[(f'fallback-jamsil-trizium-305','잠실트리지움305동',towers[305])]+[(f'fallback-trizium-preserved-{i+1}',f'인접 보존 건물{i+1}',fid) for i,fid in enumerate(preserved)],
         'limits':['Second-stage partition of the immutable published Ricenz residual. Both the original compound and previous correction files remain archived unchanged.','305 source belongs to Trizium; the two other source buildings remain separate generic fallbacks without photo-completion credit.']}
    second,files,second_proof=partition(cfg,folder,{'assets':[residual]},{residual['id']:residual['footprintIds']})
    second['kind']='repartition'
    total=sum((triangle_signatures(files[folder/a['model']]) for a in second['assets']),Counter())
    assert total==triangle_signatures((folder/residual['model']).read_bytes())
    assert not any((folder/a['model']).exists() for a in second['assets']), 'Never overwrite prior residual bytes'
    documents.update(files)
    effective={a['id']:a for a in base['assets']};effective_matches=dict(matches)
    for c in [*current['corrections'],correction,second]:
        effective.pop(c['sourceId'],None);effective_matches.pop(c['sourceId'],None)
        for a in c['assets']:effective[a['id']]=a;effective_matches[a['id']]=a['footprintIds']
    bindings=[]
    for number,fid in towers.items():
        candidates=[a for a in effective.values() if fid in effective_matches.get(a['id'],[])]
        assert len(candidates)==1,(number,[a['id'] for a in candidates])
        asset=candidates[0];assert effective_matches[asset['id']]==[fid]
        bindings.append({'number':number,'sourceFootprintId':fid,'fallbackAssetId':asset['id'],'supersedes':[asset['id']],
                         'fallbackModel':asset['model'],'fallbackSha256':asset['sha256']})
    current['corrections'].extend([correction,second])
    documents[folder/'generic-corrections.json']=encoded(current)
    documents[ROOT/'docs/model-audit/jamsil-trizium-fallback-bindings.json']=encoded({'version':1,'complex':'잠실트리지움','bindings':bindings,
        'sourceIdentity':'docs/model-audit/jamsil-trizium-source-identity.json','preservedResidualSourceIds':[fid for fid in matches[source['id']] if fid not in towers.values()]+preserved,
        'secondStageSource':{'id':residual['id'],'sha256':residual['sha256'],'priorCorrectionCanonicalSha256':canonical_sha(prior)}})
    audit={'priorCorrectionCount':len(current['corrections'])-2,'priorCorrectionsCanonicalSha256':canonical_sha(current['corrections'][:-2]),'newCorrections':2,
           'mainOriginalTriangles':source['triangles'],'secondStageOriginalTriangles':residual['triangles'],'boundBuildings':len(bindings),'preservedNeighborSourceCount':35+2,
           'mainExactAuthoringReplay':authoring['byteExact'],'secondStageTriangleSignaturesMatch':True,'priorResidualFileUnchanged':True}
    documents[ROOT/'docs/model-audit/jamsil-trizium-generic-split.json']=encoded(audit)
    return documents,audit


def main(stage_only):
    documents,audit=prepare();stage=ROOT/'data/model-source/bespoke/jamsil-trizium-fallback-review'
    for path,data in documents.items():
        dest=stage/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    if not stage_only:
        path=ROOT/'public/data/deployment-assets.json';deployment=read(path)
        for file,data in documents.items():
            if file.is_relative_to(ROOT/'public/models'):deployment['files'][str(file.relative_to(ROOT))]=sha(data)
        documents[path]=encoded(deployment);replace_batch([],documents)
    print(json.dumps({'stageOnly':stage_only,**audit}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage-only',action='store_true');main(parser.parse_args().stage_only)
