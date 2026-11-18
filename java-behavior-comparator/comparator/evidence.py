"""Source-backed scope and bounded context assembly, without assuming one-to-one method mappings."""
import re
from comparator.models import Incomplete


class Evidence:
    """Resolve source members conservatively and preserve unresolved dependency evidence."""
    def __init__(self, index):
        self.classes=index['classes'];self.chunks=index['chunks'];self.binary=index.get('binary',[])

    def qualify(self, side, name, owner):
        name=re.sub(r'<.*>', '', name).replace('[]','').strip()
        if side+'::'+name in self.classes: return name
        record=self.classes.get(side+'::'+owner,{})
        package=owner.rpartition('.')[0]
        if side+'::'+package+'.'+name in self.classes: return package+'.'+name
        wildcard=[]
        for imported in record.get('imports',[]):
            match=re.search(r'import\s+([\w.]+)(\.\*)?\s*;', imported)
            if match:
                value=match[1]+'.'+name if match[2] else match[1]
                if not match[2] and (value.rsplit('.',1)[-1]==name or value==name): return value
                if match[2] and (side+'::'+value in self.classes or any(
                    binary['side']==side and value in binary['classes'] for binary in self.binary)):
                    wildcard.append(value)
        if len(set(wildcard))==1: return wildcard[0]
        if len(set(wildcard))>1: return '<ambiguous type '+name+'>'
        if name in record.get('jdk_imports',{}): return record['jdk_imports'][name]
        if name.startswith('System.'): return 'java.lang.'+name
        if name in {'String','Object','Class','Boolean','Integer','Long','Exception','RuntimeException'}: return 'java.lang.'+name
        if re.fullmatch(r'[A-Z][\w$]*',name) and package: return package+'.'+name
        return name

    def hierarchy(self, side, name, seen=None):
        seen=set() if seen is None else seen
        if name in seen: return [],[]
        seen.add(name);record=self.classes.get(side+'::'+name)
        if not record:
            return [], [] if name.startswith(('java.','javax.xml.')) else ['Missing source for inherited type '+name]
        result=[record];gaps=[]
        for parent in record['parents']:
            parents, missing=self.hierarchy(side,self.qualify(side,parent,name),seen)
            result.extend(parents);gaps.extend(missing)
        return result,gaps

    def scope(self, side, name, entries=()):
        hierarchy,gaps=self.hierarchy(side,name)
        if not hierarchy: raise ValueError('Target class has no unambiguous source: '+name)
        roots=[];overridden=set()
        for record in hierarchy:
            for identity in record['members']:
                chunk=self.chunks[identity]
                signature=(chunk['name'],tuple(self.qualify(side,value,chunk['owner']) for value in chunk.get('parameter_types',[])))
                if chunk['kind']=='method':
                    if not chunk['public_api'] or signature in overridden or entries and chunk['name'] not in entries: continue
                    overridden.add(signature)
                roots.append(identity)
        selected=set(roots);edges={};pending=list(roots)
        while pending:
            identity=pending.pop();chunk=self.chunks[identity];related=[]
            owner_tree,missing=self.hierarchy(side,chunk['owner']);gaps.extend(missing)
            variables={key:value for record in reversed(owner_tree) for key,value in record['fields'].items()}
            variables.update(chunk['variables'])
            for declared in variables.values():
                receiver=self.qualify(side,declared,chunk['owner'])
                record=self.classes.get(side+'::'+receiver,{})
                related.extend(mid for mid in record.get('members',[]) if self.chunks[mid]['kind'] in {'field','type'})
            for call in chunk['calls']:
                scope=call['scope'];owner=chunk['owner']
                if scope in {'','this'}: receivers=self.hierarchy(side,name)[0] if owner in {r['name'] for r in hierarchy} else owner_tree
                elif scope=='super': receivers=owner_tree[1:]
                else:
                    scope=scope.removeprefix('this.')
                    receiver=self.qualify(side,variables.get(scope,scope),owner)
                    receivers,missing=self.hierarchy(side,receiver)
                    if not receivers and not receiver.startswith(('java.','javax.xml.')) and re.fullmatch(r'[\w$]+(?:\.[\w$]+)+',receiver):
                        gaps.append('Missing source body for '+receiver+'.'+call['name'])
                found=[]
                for record in receivers:
                    matches=[mid for mid in record['members'] if self.chunks[mid]['name']==call['name']
                             and self.chunks[mid]['arity']==call['arity']]
                    if matches:
                        found=matches;break
                if call['name']=='<init>':
                    found.extend(mid for record in receivers for mid in record['members']
                                 if self.chunks[mid]['kind'] in {'field','initializer','type'})
                if not found:
                    found.extend(mid for record in receivers for mid in record['members'] if self.chunks[mid]['kind']=='type')
                if not found and scope in {'','this','super'} and call['name'] not in {'toString','equals','hashCode','getClass','<init>'}:
                    imported_jdk=any('import static java.' in value and ('.'+call['name']+';' in value or '.*;' in value)
                                     for value in self.classes.get(side+'::'+owner,{}).get('imports',[]))
                    if not imported_jdk: gaps.append('Unresolved call dispatch in '+owner+': '+call['name'])
                related.extend(found)
            edges[identity]=sorted(set(related))
            for other in related:
                if other not in selected: selected.add(other);pending.append(other)
        context_ids={mid for identity in selected for mid in self.classes.get(side+'::'+self.chunks[identity]['owner'],{}).get('members',[])
                     if self.chunks[mid]['kind']=='field'}
        return dict(ids=sorted(selected),context_ids=sorted(context_ids),roots=sorted(set(roots)),edges=edges,gaps=sorted(set(gaps)))

    @staticmethod
    def references(scope):
        """Allow citations of supplied enclosing field context as well as primary members."""
        return set(scope['ids'])|set(scope.get('context_ids',[]))

    def capsule(self, identities, scope):
        """Supply whole members and immediate callees; callers never silently truncate code."""
        selected=set(identities)
        for identity in identities: selected.update(scope['edges'].get(identity,[]))
        owners={self.chunks[value]['owner'] for value in selected}
        for owner in owners:
            sides={self.chunks[value]['side'] for value in selected if self.chunks[value]['owner']==owner}
            for side in sides:
                record=self.classes.get(side+'::'+owner,{})
                selected.update(mid for mid in record.get('members',[]) if self.chunks[mid]['kind']=='field')
        return {value:dict(self.chunks[value],owner_context={key:self.classes.get(
            self.chunks[value]['side']+'::'+self.chunks[value]['owner'],{}).get(key) for key in ('imports','parents','fields')})
            for value in sorted(selected)}

    def headers(self, identities):
        """Return source identifiers and signatures for paged counterpart discovery."""
        return [{key:self.chunks[value][key] for key in ('id','owner','name','kind','signature','file','line','end_line')}
                for value in identities]
