"""Locate possible generated counterparts with paged catalogs and explicit uncertainty."""
import re
from comparator.stage_contracts import BASE, text, references

PROMPT = BASE + """Locate possible generated counterparts of ONE original behavior. The catalog page has
signatures and source identifiers, not proof of equivalence. Choose all plausible member IDs on
this page; the following task will read their full code. Use [] when none are plausible. An absent
candidate on this page does not prove the behavior is missing. Return:
{"candidates":[],"reason":"..."}.
"""


def locate(tasks,evidence,behavior,original,generated):
    """Return candidates without assuming method names or architecture must match."""
    words=set(re.findall(r'[a-z]+',(behavior['description']+' '+evidence.chunks[behavior['source']]['name']).lower()))
    ordered=sorted(generated['ids'],key=lambda i:(-sum(word in evidence.chunks[i]['signature'].lower() for word in words),i))
    page_size=tasks.settings['catalog_page_size']
    for start in range(0,len(ordered),page_size):
        page=ordered[start:start+page_size]
        def validate(value):
            references(value,'candidates',set(page));text(value,'reason')
        value=tasks.call('mapping',PROMPT,dict(behavior=behavior,
            original_evidence=evidence.capsule([behavior['source']],original),
            generated_catalog=evidence.headers(page),catalog_page=start//page_size+1),
            validate,evidence.references(original)|evidence.references(generated))
        if value['candidates']: return value['candidates']
    return []
