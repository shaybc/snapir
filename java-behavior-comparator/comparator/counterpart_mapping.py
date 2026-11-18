"""Locate possible generated counterparts with paged catalogs and explicit uncertainty."""
import re
from comparator.stage_contracts import BASE, text, references

PROMPT = BASE + """Locate possible generated counterparts of ONE original behavior. The catalog page has
signatures and source identifiers, not proof of equivalence. Choose all plausible member IDs on
this page; the following task will read their full code. Use [] when none are plausible. An absent
candidate on this page does not prove the behavior is missing. Return:
{"candidates":[],"reason":"..."}.
"""


def locate(tasks,evidence,behavior,original,generated,*,preferred=()):
    """Return candidates without assuming method names or architecture must match."""
    words=set(re.findall(r'[a-z]+',(behavior['description']+' '+evidence.chunks[behavior['source']]['name']).lower()))
    ordered=sorted(generated['ids'],key=lambda i:(-sum(word in evidence.chunks[i]['signature'].lower() for word in words),i))
    page_size=tasks.settings['catalog_page_size']
    def search(page,number,*,cached_only=False):
        def validate(value):
            references(value,'candidates',set(page));text(value,'reason')
        return tasks.call('mapping',PROMPT,dict(behavior=behavior,
            original_evidence=evidence.capsule([behavior['source']],original),
            generated_catalog=evidence.headers(page),catalog_page=number),
            validate,evidence.references(original)|evidence.references(generated),cached_only=cached_only)
    pages=[ordered[start:start+page_size] for start in range(0,len(ordered),page_size)]
    checked=set()
    # Reuse exact existing page payloads before scheduling new hint requests.
    for number,page in enumerate(pages,1):
        value=search(page,number,cached_only=True)
        if value is None: continue
        checked.add(number)
        if value['candidates']: return value['candidates']
    hints=[identity for identity in ordered if identity in set(preferred)]
    for start in range(0,len(hints),page_size):
        page=hints[start:start+page_size]
        tasks.mapping_reuse['preferred_pages']+=1
        # A previous member match is only a hint; the AI must match this behavior explicitly.
        value=search(page,'member-hint-'+str(start//page_size+1))
        if value['candidates']:
            tasks.mapping_reuse['preferred_matches']+=1
            return value['candidates']
    for number,page in enumerate(pages,1):
        if number in checked: continue
        value=search(page,number)
        if value['candidates']: return value['candidates']
    return []
