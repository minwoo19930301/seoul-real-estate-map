"""Read pinned Flight source; record scale claims, without publishing placements.

Ratios below transcribe author comments. They are not independent measurements.
Unknown dimensions/coordinates remain unknown rather than assuming 1:1 accuracy.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import subprocess
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ['seoul-city-hall', 'ddp', 'amorepacific-hq', 'tower-palace',
            'hyperion', 'acro-seoul-forest', 'parc1-ifc', 'gfc',
            'samsung-town', 'seoul-dragon-city']

# (source planar fraction, scope, source vertical fraction, source spacing fraction).
# A pair denotes local X/Z anisotropy, not world-aligned bounding-box scaling.
CLAIMS = {
    'acro-seoul-forest': (.6, 'building-footprints', 1, None),
    'amorepacific-hq': (.55, 'building-footprints', 1, None),
    'amsa-prehistoric-site': (.55, 'complete-plan', 1, None),
    'cheongnyangni-skyl65': (.5, 'building-footprints', 1, None),
    'ddp': (.35, 'complete-plan', 1, None),
    'ewha-ecc': (.45, 'complete-plan', [.6, .7], None),
    'gangdong-arts-center': (.7, 'complete-plan', 1, None),
    'garden-five': (.22, 'complete-plan', 1, None),
    'gimpo-airport': (.45, 'complete-plan', 1, None),
    'gocheok-skydome': (.65, 'building-footprints', None, None),
    'hanseong-baekje-museum': (.7, 'complete-plan', 1, None),
    'hyperion': (.5, 'building-footprints', 1, None),
    'jamsil-sports-complex': (.4, 'building-footprints', .65, None),
    'korea-univ-main': (.73, 'complete-plan', 1, None),
    'kyunghee-peace-hall': (.8, 'building-footprints', 1, None),
    'lotte-castle-goldpark': (.45, 'building-footprints', 1, None),
    'lotte-world-magic-island': (.5, 'island-footprint', 1, None),
    'myeongdong-cathedral': (.76, 'complete-plan', .85, None),
    'national-assembly': (.78, 'complete-plan', 1, None),
    'national-museum-korea': ([.36, .5], 'local-building-length-width', 1, None),
    'parc1-ifc': (None, 'spacing-only', 1, .35),
    'samcheonggak': (.4, 'site-spacing', 1, .4),
    'samsung-engineering-gec': (.45, 'building-footprints', 1, None),
    'samsung-town': (None, 'spacing-only', 1, .5),
    'sangbong-emco': (.5, 'building-footprints', 1, None),
    'sebitseom': (None, 'spacing-only', .9, .4),
    'seoul-arts-center': (.55, 'building-footprints', 1, None),
    'seoul-botanic-park': (.78, 'greenhouse-plan; vertical unspecified', None, None),
    'seoul-city-hall': (.4, 'complete-plan', 1, None),
    'seoul-dragon-city': (.6, 'complete-plan', 1, .6),
    'seoul-world-cup-stadium': (.55, 'building-footprints', 1, None),
    'seoultech': (.42, 'complete-plan', 1, None),
    'supreme-court': (.45, 'complete-plan', None, None),
    'technomart': (.6, 'building-footprints', 1, None),
    'tower-palace': (.5, 'building-footprints', 1, .35),
    'walkerhill': (None, 'spacing-only', 1, .45),
    'war-memorial': (.4, 'building-footprints', 1, None),
    'yonsei-underwood': (.7, 'building-footprints', 1, None),
}

PRIORITY_NOTES = {
    'seoul-city-hall': 'Source combines new hall, old library and plaza; split ownership and verify both building footprints. A 2.5x plan correction is only inverse author compression, not proof of correct old/new relative placement.',
    'ddp': 'Source blob includes sunken plaza, bridge, lawn and historic remains. Apply plan correction around source origin, retain baked 22-degree rotation, then fit actual DDP site; do not match to DDP Fashion Mall.',
    'amorepacific-hq': 'One courtyard block, three garden openings and plaza; inverse footprint scale 1/0.55 is usable as an initial silhouette correction. Source 45-degree rotation is already baked.',
    'tower-palace': 'Two different ratios: tower-local geometry 2x, tower centres 1/0.35x. Cannot recover both with one global matrix. Rebuild/tag the seven tower calls before material merge; refit shared podiums and landscape separately.',
    'hyperion': 'Three tower calls plus common department-store podium. Width correction 2x is stated; independent tower-centre spacing is not. Keep source -20-degree rotation baked; verify centres before publishing.',
    'acro-seoul-forest': 'Two source tower centres (-23,-2.5),(23,2.5), source local width28/depth16 vs author approximate real45/25. Overall ~0.6 is approximate and does not establish measured tower spacing. Source +15-degree rotation already baked.',
    'parc1-ifc': 'Combined IFC, Parc1, Fairmont, Conrad and LG Twin Towers. Source says 0.35 spacing only; scaling every vertex 1/0.35 would also enlarge individual towers without evidence. Extract constituent buildings before merging; map them separately to real footprints.',
    'gfc': 'No source compression ratio. Source tower width24/depth46 and height206 are hardcoded design dimensions; fit to confirmed source footprint rather than inferring a scale from height.',
    'samsung-town': 'Three towers; source says 0.5 spacing only. Translate centres 2x only after identifying tower components; individual facade/plan scale remains unresolved. Source material merge destroys component ownership.',
    'seoul-dragon-city': 'Whole-plan ~0.6 and gap24 vs claimed40 are consistent candidate 1/0.6 planar correction. Three hotel towers, shared podium and skybridge must remain connected; source geographic coordinate differs from registry.',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reciprocal(value):
    if isinstance(value, list):
        return [1 / x for x in value]
    return None if value is None else 1 / value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT.parent.parent / '2026-09-05/new-chat/work/repos/seoul-flight-game')
    parser.add_argument('--report', type=Path, default=ROOT / 'data/model-source/flight-current/report.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'data/model-source/flight-current/placement-audit.json')
    args = parser.parse_args()
    report_bytes = args.report.read_bytes()
    report = json.loads(report_bytes)
    rows = []
    for asset in report['assets']:
        source_bytes = subprocess.check_output(['git', '-C', str(args.repo), 'show', report['sourceRevision'] + ':' + asset['sourceFile']])
        if sha(source_bytes) != asset['sourceFileSha256']:
            raise ValueError('Source hash mismatch: ' + asset['id'])
        source = source_bytes.decode()
        lines = source.splitlines()
        # Contiguous opening comment block contains the architectural claims.
        heading = []
        for line in lines:
            if not line.startswith('//'):
                break
            heading.append(line.removeprefix('//').strip())
        text = ' '.join(heading)
        claim = CLAIMS.get(asset['id'])
        planar, scope, vertical, spacing = claim or (None, 'unspecified', None, None)
        compressed = bool(re.search(r'compress|scaled|scale|collider', text, re.I))
        status = 'explicit-author-ratio' if claim else 'compression-mentioned-ratio-unspecified' if compressed else 'no-explicit-scale-evidence'
        a, b = asset['moduleCoordinate'], asset['flightRuntimeCoordinate']
        distance = math.hypot((a['lon'] - b['lon']) * 111320 * math.cos(math.radians(a['lat'])), (a['lat'] - b['lat']) * 111320)
        offset = asset['exportOffsetFromSource']
        rotation_lines = [{'line': i + 1, 'text': line.strip()} for i, line in enumerate(lines)
                          if re.search(r'subgroup\(g.*ry|(?:g|site)\.rotation\.y|const ry =', line)]
        component_lines = [{'line': i + 1, 'text': line.strip()} for i, line in enumerate(lines)
                           if re.search(r'(?:panelTower|bowTower|ovalTower|acroTower|hyperionTower|parc1Tower|ifcTower|hotelTower)\(', line) and not line.lstrip().startswith('function')]
        correction = None
        if planar is not None and not isinstance(planar, list):
            correction = [1 / planar, 1 / vertical if isinstance(vertical, (int, float)) else None, 1 / planar]
        rows.append({
            'id': asset['id'], 'nameKo': asset['nameKo'], 'priority': asset['id'] in PRIORITY,
            'sourceFile': asset['sourceFile'], 'sourceFileSha256': asset['sourceFileSha256'],
            'scaleEvidenceStatus': status, 'evidenceAuthority': 'source author comment; not independently verified',
            'sourceAuthorDescription': [{'line': i + 1, 'text': line} for i, line in enumerate(heading)],
            'sourcePlanarFraction': planar, 'planarClaimScope': scope,
            'sourceVerticalFraction': vertical, 'sourceCentreSpacingFraction': spacing,
            'candidateInversePlanScale': reciprocal(planar), 'candidateInverseHeightScale': reciprocal(vertical),
            'candidateInverseCentreSpacing': reciprocal(spacing),
            'candidateScaleXYZ': correction,
            'globalMatrixSufficientForAuthorClaims': scope == 'complete-plan' and isinstance(vertical, (int, float)),
            'sourceRotationLines': rotation_lines, 'sourceComponentCallLines': component_lines,
            'runtimeAdditionalYawDeg': 0,
            'yawBasis': 'Original rotations already baked into exported vertices; this is not independently verified geographic orientation.',
            'moduleCoordinate': a, 'flightRuntimeCoordinate': b,
            'coordinateDiscrepancyM': round(distance, 2), 'selectedVerifiedCoordinate': None,
            'exportOffsetFromSource': offset, 'nominalSourceGroundInExportM': -offset[1],
            'preserveSourceGroundVerticalAdjustmentM': offset[1],
            'sourceBounds': asset['sourceStats']['bounds'], 'exportedBounds': asset['byteValidation']['bounds'],
            'placementFormula': 'sourceWorld = exportVertex + exportOffsetFromSource; correctedWorld = correction(sourceWorld). Apply before independent georeferencing. Do not scale about exported centre without correcting the anchor.',
            'normalizationWarning': 'Exporter raises minimum vertex to zero. Original nominal ground is not necessarily minimum vertex (sunken courts/site paving). Restoring original grade requires the recorded vertical offset.',
            'review': PRIORITY_NOTES.get(asset['id'], 'Confirm site identity, building-specific footprint fit, ground datum and coordinate before applying source-author scale estimates.'),
            'publishReady': False,
        })
    result = {
        'version': 1, 'sourceRevision': report['sourceRevision'], 'exportReportSha256': sha(report_bytes),
        'notice': 'Read-only source audit. Candidate inverse scales undo stated game compression; they do not establish measured plans or photo-correct facades. No geometry or active manifest changed.',
        'counts': {'assets': len(rows), 'scaleEvidence': dict(Counter(r['scaleEvidenceStatus'] for r in rows)),
                   'coordinateDiscrepancies': sum(r['coordinateDiscrepancyM'] > 0 for r in rows),
                   'coordinateDiscrepanciesOver100M': sum(r['coordinateDiscrepancyM'] > 100 for r in rows)},
        'priorityOrder': PRIORITY, 'assets': rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['counts'], ensure_ascii=False))
    print(args.out)


if __name__ == '__main__':
    main()
