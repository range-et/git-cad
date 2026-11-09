"""History graph built from recorded ancestry, never inferred from file names."""
from __future__ import annotations
from collections import defaultdict
from .store import branch_tip,order_key,CadgitError


def build_graph(snapshots, assemblies, config, main_id=None):
    records={r['id']:r for r in [*snapshots,*assemblies]}
    edges=[];missing=[]
    for ref,r in records.items():
        links=[]
        if r.get('parent'):links.append((r['parent'],'save'))
        if r.get('metadata',{}).get('imported_from'):links.append((r['metadata']['imported_from'],'import'))
        links.extend((s['snapshot_id'],'assembly') for s in r.get('selections',[]))
        for parent,kind in dict.fromkeys(links):
            (edges if parent in records else missing).append({'child':ref,'parent':parent,'kind':kind})
    # Descendants appear above their ancestors, including captures imported later
    # with an earlier captured_at timestamp. Stable time ordering breaks ties.
    children=defaultdict(set);parents=defaultdict(set)
    for edge in edges:
        children[edge['parent']].add(edge['child']);parents[edge['child']].add(edge['parent'])
    ready=[ref for ref in records if not children[ref]];order=[]
    while ready:
        ready.sort(key=lambda ref:order_key(records[ref]),reverse=True)
        ref=ready.pop(0);order.append(ref)
        for parent in parents[ref]:
            children[parent].discard(ref)
            if not children[parent]:ready.append(parent)
    # Imported/corrupt legacy manifests can contain cycles. Keep them inspectable.
    cyclic=sorted(set(records)-set(order));order.extend(cyclic)
    lanes=sorted({(r['source'],r.get('branch','main')) for r in snapshots})
    if assemblies:lanes=[('assembly','main'),*lanes]
    heads={};warnings=[]
    for source,branch in {(r['source'],r.get('branch','main')) for r in snapshots}:
        try:
            tip=branch_tip(snapshots,source,branch)
            if tip:heads[(source,branch)]=tip['id']
        except CadgitError as exc:warnings.append(str(exc))
    present_branches={(r['source'],r.get('branch','main')) for r in snapshots}
    for source,branches in config.get('branches',{}).items():
        for branch,info in branches.items():
            if info.get('base') and (source,branch) not in present_branches:heads.setdefault((source,branch),info['base'])
    nodes=[]
    for ref in order:
        r=records[ref];lane=(r.get('source','assembly'),r.get('branch','main'))
        refs=[]
        if ref==main_id:refs.append({'label':'main','kind':'main'})
        for (source,branch),head in heads.items():
            if head==ref:
                active=config.get('active_branches',{}).get(source,'main')==branch
                refs.append({'label':source+'/'+branch+(' • HEAD' if active else ''),'kind':'head','source':source,'branch':branch})
        for name,version in config.get('versions',{}).items():
            if version==ref:refs.append({'label':name,'kind':'version'})
        nodes.append({'id':ref,'record':r,'lane':lanes.index(lane),'refs':refs})
    # Reuse columns once their pending ancestors have been reached, as in a
    # Git log. Software/branch identity still determines labels and colors.
    pending=[];column_count=0
    parent_edges=defaultdict(list)
    for edge in edges:parent_edges[edge['child']].append(edge)
    for node in nodes:
        ref=node['id']
        if ref in pending:column=pending.index(ref)
        else:
            column=next((i for i,value in enumerate(pending) if value is None),len(pending))
            if column==len(pending):pending.append(None)
        node['column']=column;column_count=max(column_count,column+1)
        pending[column]=None
        outgoing=sorted(parent_edges[ref],key=lambda edge:edge['kind']!='save')
        for edge in outgoing:
            parent=edge['parent']
            if parent in pending:continue
            available=[i for i,value in enumerate(pending) if value is None]
            target=min(available,key=lambda i:(abs(i-column),i<column)) if available else len(pending)
            if target==len(pending):pending.append(parent)
            else:pending[target]=parent
            column_count=max(column_count,target+1)
        while pending and pending[-1] is None:pending.pop()
    if missing:warnings.append(str(len(missing))+' ancestry references are missing')
    if cyclic:warnings.append('Cyclic ancestry detected')
    return {'nodes':nodes,'edges':edges,'lanes':lanes,'missing':missing,'cyclic':cyclic,'warnings':warnings,'column_count':column_count}
