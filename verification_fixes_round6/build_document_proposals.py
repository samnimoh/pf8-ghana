from pathlib import Path
import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path('/Users/samnimoh/Desktop/chromo')
MAIN = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def paragraphs(path):
    with zipfile.ZipFile(path) as package:
        tree = ET.fromstring(package.read('word/document.xml'))
    return [''.join(t.text or '' for t in p.findall('.//w:t', NS))
            for p in tree.findall('.//w:body//w:p', NS)]


D = paragraphs(MAIN)
SUP = paragraphs(ROOT / 'article/Additional_file_1.docx')
EDITS = []


def edit(index, substitutions, reason, concept='differentiation interpretation', sev='P2'):
    original = D[index]
    revised = original
    for quote, repl in substitutions:
        assert revised.count(quote) == 1, (index, quote, revised.count(quote))
        revised = revised.replace(quote, repl)
    if len(substitutions) == 1:
        quote, repl = substitutions[0]
        if sum(p.count(quote) for p in D) != 1:
            quote, repl = original, revised
    else:
        quote, repl = original, revised
    assert sum(p.count(quote) for p in D) == 1, (index, quote)
    if concept != 'cross-reference':
        # Moving an existing numeral within a sentence is allowed, adding or deleting it is not.
        number = re.compile(r'\d+(?:[.,]\d+)*')
        assert collections.Counter(number.findall(quote)) == collections.Counter(number.findall(repl)), index
    EDITS.append(dict(quote=quote, repl=repl, concept=concept, sev=sev, expected_count=1,
                      source=str(MAIN), paragraph_index=index, reason=reason,
                      paragraph_text=original,
                      context_before=D[index - 1] if index else '',
                      context_after=D[index + 1] if index + 1 < len(D) else '',
                      supplement_mirror_indices=[i for i, p in enumerate(SUP) if quote in p]))


edit(138, [('To quantify spatial population structure, gene flow and candidate signatures of local selection',
            'To quantify spatial population differentiation, summarise population covariance relationships and examine candidate signatures of local selection')],
     'Separate measured differentiation and fitted relationships from an unestimated contemporary gene-flow rate.')
edit(147, [('near-panmixia, maximum FST of approximately 0.0023', 'very low differentiation at retained common variants, maximum FST of approximately 0.0023'),
           ('Near-panmixia is now supported by FST stability across 0.00204-0.00255 over all six scenarios, which is better evidence than any single run could give',
            'The very low measured differentiation is stable across 0.00204-0.00255 over all six scenarios; this strengthens the threshold-sensitivity result without estimating mating or contemporary exchange')],
     'Two current abstract assertions overinterpret a stable statistic. Retain historical rerun facts and numerical values.')
edit(150, [('If instead the zones exchange parasites freely, an allele arising anywhere will spread everywhere, and the surveillance question becomes one of timing rather than of geography.',
            'Even when differentiation at common variants is very low, marker frequencies can vary geographically; these data do not estimate the routes or rates of contemporary exchange.')],
     'The introduction makes a deterministic connectivity assertion unsupported by the analyses.')
edit(152, [('a resistance allele can have a site-specific frequency even under neutral panmixia',
            'a resistance allele can have a site-specific frequency even when differentiation at common variants is very low')],
     'Preserve the withdrawn surveillance argument; narrow the current explanation outside the quotation.')
edit(155, [('so near-panmixia does not depend on the Fws or MAF cuts',
            'so the magnitude of measured common-variant differentiation is stable across the tested Fws and MAF cuts')],
     'Sensitivity concerns a measured differentiation statistic, not mating or exchange.')
edit(158, [('Objectives 1 and 3 are now answered within the limits the design permits',
            'Objective 1 is answered for differentiation rather than contemporary gene-flow magnitude or direction, and objective 3 is answered within the limits the design permits')],
     'Preserve the original thesis objective verbatim in its table but qualify its answered status.')
edit(164, [('Answered, and robust.', 'Differentiation is quantified and tested; contemporary gene-flow magnitude and direction are not identified.'),
           ('A two-edge graph is the model these data select (edge p = 7.5 x 10 to the -4 and 3.3 x 10 to the -16); a third is not supported (p = 0.33).',
            'A two-edge graph is the selected descriptive covariance model (conditional edge p = 7.5 x 10 to the -4 and 3.3 x 10 to the -16); the third fitted edge is not distinguishable from zero conditional on that graph (p = 0.33).')],
     'The objective-status cell combines valid differentiation with an unanswered gene-flow objective and unqualified graph tests.',
     'graph and differentiation interpretation')
edit(194, [(D[194], 'Does adding edges improve fit within the fitted TreeMix covariance model? Operationalised as TreeMix with 0-5 migration edges and jackknife standard errors, with edge p-values conditional on the fitted topology and root. The selected edge count is a descriptive model choice, not a test of contemporary exchange or an identified branching history.')],
     'Frame the operational question around conditional model fit, retaining the explored edge-count range.', 'TreeMix interpretation')

# Current assertions inside historical rerun narratives remain live assertions, not protected withdrawn quotations.
simple = [
    (603, 'it leaves near-panmixia stronger than before', 'it strengthens the evidence that very low measured differentiation is stable across the tested thresholds'),
    (920, 'and near-panmixia continued to hold', 'and very low differentiation at the retained common variants persisted'),
    (1296, 'the near-panmixia result is insensitive to a substantial change in panel size', 'very low measured common-variant differentiation persists after a substantial change in panel size'),
    (1573, 'near-panmixia, maximum pairwise FST of the same order', 'very low common-variant differentiation, maximum pairwise FST of the same order'),
    (1972, 'Near-panmixia is therefore insensitive to both of the thresholds that define the dataset', 'The magnitude of measured common-variant differentiation is therefore stable across both tested thresholds'),
    (3138, 'and near-panmixia across Ghana still holds', 'and differentiation among the sampled zones remains very low at the retained common variants'),
    (3214, 'The substantive readings held — near-panmixia, maximum pairwise FST of about 0.0023, and a near-flat cross-validation curve.', 'The substantive readings held — very low common-variant differentiation, maximum pairwise FST of about 0.0023, and a near-flat cross-validation curve.'),
    (3237, 'The substantive readings held — near-panmixia, maximum pairwise FST of about 0.0023, and a near-flat cross-validation curve.', 'The substantive readings held — very low common-variant differentiation, maximum pairwise FST of about 0.0023, and a near-flat cross-validation curve.'),
    (3239, 'Near-panmixia is insensitive to both:', 'The magnitude of measured common-variant differentiation is stable across both:'),
    (3366, 'Near-panmixia is insensitive:', 'Measured common-variant differentiation is stable across the tested thresholds:'),
    (3423, 'Near-panmixia survives; isolation by distance does not.', 'Very low measured common-variant differentiation is stable across the tested thresholds; isolation by distance is not robust.'),
    (3468, 'the panel size is not propping up the near-panmixia conclusion', 'the very low measured differentiation persists in the larger common-variant panel'),
    (3510, 'Near-panmixia no longer rests on a single pass through a single dataset:', 'The stability of measured common-variant differentiation no longer rests on one threshold setting:'),
    (3527, 'Near-panmixia is strengthened by the same six scenarios.', 'The evidence that measured common-variant differentiation is stable across the tested thresholds is strengthened by the same six scenarios.'),
    (3633, 'near-panmixia is stable, with max FST ranging only 0.00204–0.00255 over six scenarios', 'measured common-variant differentiation is stable, with max FST ranging only 0.00204–0.00255 over six scenarios'),
    (3648, 'the manuscript should carry near-panmixia as its spatial result', 'the manuscript should report very low but detectable common-variant differentiation as its zone-level result'),
    (3651, 'made near-panmixia the best-evidenced conclusion in the manuscript', 'made the stability of measured common-variant differentiation the best-evidenced conclusion in the manuscript'),
    (3882, 'near-panmixia unaffected, isolation by distance not surviving', 'very low measured common-variant differentiation stable, isolation by distance not surviving'),
    (3977, 'made near-panmixia the best-evidenced conclusion in the manuscript', 'made the stability of measured common-variant differentiation the best-evidenced result in the manuscript'),
]
for i, q, r in simple:
    edit(i, [(q, r)], 'A surviving/current sensitivity conclusion describes measured common-variant differentiation, not panmixia. Preserve the audit events, numbers and explicitly withdrawn claims.')

edit(980, [('The published MAF floor is therefore, if anything, mildly anticonservative with respect to the panmixia conclusion, and the conclusion survives the correction.',
            'The measured differentiation remains very low at the lower MAF floor; this is a comparison of panel-specific estimates, not evidence about a mating system or contemporary exchange.')],
     'The direction of a small FST change does not establish conservative/anticonservative bias for panmixia.')
edit(981, [('The honest reading is that the panmixia estimate was always well determined and the distance effect never was; what the check did was reveal which of the two the published thresholds had been carrying.',
            'The check shows that the magnitude of measured common-variant differentiation is stable across the tested thresholds, whereas the significance of the distance correlation is not; it does not estimate panmixia.')],
     'Do not relabel a measured differentiation estimate as a mating-system estimate.')
edit(1555, [('gave TreeMix inferential support for the first time', 'gave TreeMix conditional edge-weight tests for the first time'),
            ("and near-panmixia across Ghana's agro-ecological zones still holds", "and differentiation among Ghana's agro-ecological zones remains very low at the retained common variants")],
     'Carry both the statistical-estimate and conditional graph qualifications into this reassurance paragraph.', 'graph and differentiation interpretation')
edit(1844, [('The practical reading is that these zones are not demographically separate populations; they are one population sampled in four places.',
            'The measured differentiation is very low at the retained common variants; it does not establish that the zones form a single demographic population or identify barriers to contemporary exchange.')],
     'A small FST cannot establish one demographic population.')
edit(1845, [('None is practically significant in the sense of implying restricted gene flow. A resistance allele arising in Accra would be expected to reach Bolgatanga; the question these data cannot answer is how quickly.',
            'The estimates describe very low differentiation, but do not quantify barriers to contemporary exchange or predict whether, by which route or how quickly an allele would move between Accra and Bolgatanga.')],
     'Remove the unsupported current connectivity prediction; preserve all reported numbers.')
edit(2046, [('The substantive conclusion the manuscript drew, that this is a population without ancestry structure of any practical consequence, survives; the way it was stated does not.',
            'The measured zone-associated ancestry contrast is small; neither its practical consequences nor the mating system is established by this analysis.')],
     'The qualified correction still asserts absent meaningful ancestry structure without measuring practical consequences.')
edit(3149, [('Zones share essentially all their common genetic variation', 'Among-zone allele-frequency differentiation is very low but statistically detectable at the retained common variants')],
     'Express the measured differentiation rather than an unmeasured shared-variant claim.')
edit(3152, [('Zone labels do not describe the variation — and removing the polyclonal and clonally redundant isolates makes the separation slightly worse, not better',
            'Zones do not separate in these ordinations; removing the polyclonal and clonally redundant isolates does not improve the silhouette coefficient')],
     'Restrict the ordination reading to the measured separation criterion, rather than absence of all zone-associated variation.')
edit(3155, [('Admitting structure barely improves fit; any structure present is of negligible magnitude',
            'Admitting the ancestry component barely improves cross-validation fit in this panel; this does not exclude structure at unexamined variants')],
     'The fitted panel does not measure every possible population structure.')
edit(3157, [('A bifurcating tree alone explains 89.7% of the covariance; two significant migration edges raise this to 99.7%',
            'Within the fitted covariance model, the bifurcating topology explains 89.7% of the covariance; adding two edges raises this to 99.7%, with edge weights distinguishable from zero conditional on that graph')],
     'Carry graph conditioning into the table result cell.', 'TreeMix interpretation')
edit(3158, [('Exchange between groups, not a branching history', 'Improved covariance-model fit conditional on the fitted graph; contemporary exchange and the underlying branching history are not identified')],
     'The table reading asserts exchange and excludes a branching history beyond fitted-model evidence.', 'TreeMix interpretation')
edit(3178, [('Marker frequencies do differ by zone, even though the neutral background does not.', 'Marker frequencies differ by zone alongside very low but detectable differentiation at the retained common variants.')],
     'The table cell currently asserts absent genome-wide differentiation.')
edit(3182, [('Ghanaian P. falciparum behaves as a single, largely panmictic population for common neutral variation, with weak departures detectable in minor-component ancestry and in resistance-marker frequencies.',
            'Ghanaian P. falciparum shows very low but detectable differentiation among the sampled zones at retained common variants, alongside differences in minor-component ancestry and resistance-marker frequencies.'),
           ("This is a substantive answer to the thesis's first objective, and a negative one for the strong form of its hypothesis: the ecological zones are not acting as demographic barriers at a scale these data can detect.",
            "This answers the differentiation part of the thesis's first objective within the sampled panel; the analyses do not directly test demographic barriers or identify contemporary gene-flow magnitude or direction.")],
     'This central conclusion directly asserts panmixia and absent demographic barriers; narrow both to measured differentiation.')
edit(3187, [('That the headline is a negative is not surprising, and that is a point in its favour.', 'Very low measured differentiation is compatible with several demographic explanations.'),
           ('All four favour genetic homogenisation.', 'These considerations could contribute to weak differentiation, but do not identify the process responsible for the estimates here.')],
     'Retain literature context without turning descriptive low differentiation into an established homogenisation process.')
edit(3212, [('resistance-allele trajectories can remain site-specific even under neutral panmixia', 'resistance-allele trajectories can remain site-specific even when common-variant differentiation is very low')],
     'Preserve the withdrawn surveillance quotation; narrow only the current explanation outside it.')
edit(3213, [('from the same panmictic parasite population', 'despite very low differentiation among the sampled groups at retained common variants'),
           ('neutral structure can be characterised sparsely; marker frequencies cannot.', 'low common-variant differentiation alone does not establish that sparse sampling characterises either population structure or marker frequencies.')],
     'Neither a panmictic population nor sufficient sparse sampling is established by measured low FST.')
edit(3215, [('Because no neutral barrier is detectable at the retained common variants, this analysis supplies no evidence of a barrier for a geographically targeted containment intervention to exploit.',
            'The analyses do not directly test barriers to contemporary exchange, so they do not establish a barrier for a geographically targeted containment intervention to exploit.')],
     'The later caveat is sound; the opening still describes a barrier test that was not performed.')
edit(3216, [('The argument from low FST to free gene flow runs from an absence of detectable structure to an assertion about process.',
            'The argument from low FST to free gene flow runs from very low measured differentiation to an assertion about process.')],
     'Preserve this criticism of the unsupported inference but correct its premise: differentiation was detectable.')
edit(3476, [('so near-panmixia does not depend on this exclusion and in fact strengthens very slightly without it — the polyclonal isolates were not masking differentiation.',
            'so measured differentiation remains very low under these relaxations and rises slightly rather than falling — the excluded polyclonal isolates were not masking differentiation.')],
     'Both panmixia wording and its supposed strengthening overinterpret the small upward change in FST.')
edit(3583, [('A strictly bifurcating population tree is inadequate, and a two-edge graph is the model these data select.',
            'Within the fitted TreeMix covariance model, the bifurcating topology leaves residual covariance that the selected descriptive two-edge graph absorbs.'),
           ('Every edge in the m = 2 graph is significant (p = 7.5 x 10-4 and 3.3 x 10-16); the third edge added at m = 3 is not (weight 0.065, SE 0.147, p = 0.328),',
            'Every edge weight in the m = 2 graph is distinguishable from zero conditional on its fitted topology and root (p = 7.5 x 10-4 and 3.3 x 10-16); the third fitted edge at m = 3 is not distinguishable from zero conditional on that graph (weight 0.065, SE 0.147, p = 0.328),'),
           ('Specific gene-flow corridors remain unidentifiable with four populations.', 'The edge tests do not propagate graph-structure uncertainty or identify contemporary exchange. Specific gene-flow corridors remain unidentifiable with four populations.')],
     'Qualify the conclusion consistently with methods; retain graph-selection disagreement and numerical values.', 'TreeMix interpretation')
edit(3621, [('Is there gene flow beyond a bifurcating tree?', 'Does adding edges improve fit within the fitted TreeMix covariance model?')],
     'The summary question should refer to the fitted quantity rather than an unobserved process.', 'TreeMix interpretation')
edit(3622, [('Partly. m = 2 is the selected descriptive model: its two edges are significant (p = 7.5 x 10-4 and 3.3 x 10-16), a third is not (weight 0.065, SE 0.147, p = 0.33),',
            'Within the fitted covariance model, yes. m = 2 is the selected descriptive model: its two edge weights are distinguishable from zero conditional on its fitted topology and root (p = 7.5 x 10-4 and 3.3 x 10-16), while the third fitted edge is not distinguishable from zero conditional on that graph (weight 0.065, SE 0.147, p = 0.33),'),
           ('Specific corridors remain unidentifiable.', 'Graph-structure uncertainty is not propagated by the edge tests, and contemporary exchange and specific corridors remain unidentifiable.')],
     'Qualify the table answer consistently with its narrowed question and corrected methods.', 'TreeMix interpretation')
edit(3623, [('High that a bifurcating tree is inadequate; m = 2 is a selected descriptive model rather than a settled edge count; corridors not identifiable',
            'Conditional support for improved fit in the selected covariance model; m = 2 is a descriptive model choice rather than a settled edge count; graph structure, contemporary exchange and corridors not identified')],
     'An unconditional rejection of a bifurcating history does not follow from fixed-graph edge tests.', 'TreeMix interpretation')
edit(731, [(', Table 6.8 and Section 10.1 use this wording', ' and Section 10.1 use this wording')],
     'Neither Table 6.8 caption describes this cascade. Remove its unsupported pointer rather than guess a replacement that again maps incorrectly in the supplement.', 'cross-reference')
for index in (1775, 1969):
    edit(index, [(' This table is new in this revision and is.', '')],
         'Remove the whole unfinished caption sentence left by numbering cleanup.', 'caption cleanup', 'P3')

MD = ROOT / 'article/article.md'
md = MD.read_text()
md_edits = [
    ('The estimate generalises only if parasites are exchanged freely enough between zones that allele frequencies are effectively shared.',
     'Whether a local estimate represents the country depends on the geographic distribution of the marker and the sampling design; low common-variant differentiation alone does not establish that representativeness.',
     'Free exchange is not a necessary condition for representativeness and is unmeasured; state the representativeness limit directly.'),
    ('### Resistance markers vary geographically where neutral structure does not',
     '### Resistance markers vary geographically alongside very low common-variant differentiation',
     'The heading implies absent genome-wide structure despite detectable differentiation.'),
    ('Genome-wide F~ST~ averages drift and gene flow over thousands of retained variants; selection acts on single loci,',
     'Genome-wide F~ST~ summarises among-group allele-frequency differences across the retained variants rather than separately estimating drift or gene flow; selection can affect individual loci,',
     'FST does not separately estimate drift or migration rates.'),
    ('Ordination recovered no zone structure, every silhouette coefficient being negative (Fig. 2).',
     'Zones did not separate in the ordinations, every silhouette coefficient being negative (Fig. 2).',
     'Keep lack of ordination separation distinct from absent zone-associated differentiation.'),
]
for q, r, reason in md_edits:
    assert md.count(q) == 1, q
    assert re.findall(r'\d+(?:[.,]\d+)*', q) == re.findall(r'\d+(?:[.,]\d+)*', r)
    EDITS.append(dict(quote=q, repl=r, concept='differentiation interpretation', sev='P2', expected_count=1,
                      source=str(MD), paragraph_index=None, reason=reason))

proposed = D.copy()
for e in EDITS:
    if e['source'] == str(MAIN):
        proposed[e['paragraph_index']] = proposed[e['paragraph_index']].replace(e['quote'], e['repl'])
remaining = [{'paragraph_index': i, 'text': t,
              'classification': 'Inference limit, preserved history or original thesis objective; final adversarial review required'}
             for i, t in enumerate(proposed)
             if re.search(r'panmix|panmict|random mat|bifurcat|free gene flow|ongoing exchange|contemporary exchange', t, re.I)]
paths = [MAIN, ROOT / 'article/Additional_file_1.docx', ROOT / 'article/Pf8_Ghana_article.docx', MD,
         ROOT / 'article/CANONICAL_FACTS_FOR_ARTICLE.md']
result = {
    'scope': 'Read-only conceptual sweep. One asserted edit per affected manuscript paragraph. Regenerate the supplement from the working record and rebuild article DOCX from Markdown.',
    'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    'counts': {'manuscript_edits': sum(e['source'] == str(MAIN) for e in EDITS),
               'article_markdown_edits': sum(e['source'] == str(MD) for e in EDITS), 'total': len(EDITS)},
    'edits': sorted(EDITS, key=lambda e: (e['source'], e['paragraph_index'] or 0)),
    'remaining_keyword_occurrences_after_proposals': remaining,
    'notes': [
        'Original thesis objective about gene-flow magnitude/direction remains verbatim; its answered status is qualified.',
        'Paragraph 3607 explicitly describes the previous version\'s near-panmixia grading and is intentionally preserved.',
        'Explicit inference limits concerning mating and contemporary exchange are preserved.',
        'No scientific pipeline was executed or biological method changed. Proposed interpretation replacements preserve numerical tokens.',
        'Cross-reference correction removes the unsupported Table 6.8 pointer without guessing a new target.',
        'Table cells and article headings are included as expressions of the same absent-structure inference problem.',
    ],
}
output = ROOT / 'verification_fixes_round6/document_proposals.json'
output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'output': str(output), 'counts': result['counts'],
                  'remaining_keyword_indices': [p['paragraph_index'] for p in remaining]}, indent=2))
