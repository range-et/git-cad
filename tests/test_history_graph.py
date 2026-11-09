import signal
import pytest
from cadgit.history_graph import build_graph as _build_graph
from cadgit.store import Project,CadgitError,read_json
from cadgit.usd import assemble
from test_history import box


def build_graph(*args, **kwargs):
    # Every fixture here has fewer than 30 nodes. A nonterminating traversal is a
    # failed contract, not a worker timeout that could be mistaken for a kill.
    def exceeded(signum, frame):
        raise AssertionError('Small history graph did not terminate within two seconds')
    previous_handler = signal.signal(signal.SIGALRM, exceeded)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        return _build_graph(*args, **kwargs)
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def test_graph_draws_actual_forks_composition_and_import_lineage(tmp_path):
    p=Project.init(tmp_path/'project');source=box(tmp_path/'part.usda')
    base=p.ingest(source,'rhino','Base');main=p.ingest(source,'rhino','Main edit')
    p.branch('rhino','alternative',base['id'],activate=True)
    fork=p.ingest(source,'rhino','Alternative edit')
    blend=p.ingest(source,'blender','Blender source')
    assembly=assemble(p,[{'snapshot_id':fork['id'],'prim_path':'/World/Part'},{'snapshot_id':blend['id'],'prim_path':'/World/Part'}])
    p.set_main(assembly['id']);p.name_version(base['id'],'Baseline')
    imported=p.ingest(p.stage_path(assembly),'blender','Continue assembly',metadata={'imported_from':assembly['id']})
    graph=build_graph(p.records(),p.records('assemblies'),p.config,assembly['id'])
    edges={(e['child'],e['parent'],e['kind']) for e in graph['edges']}
    assert (main['id'],base['id'],'save') in edges
    assert (fork['id'],base['id'],'save') in edges
    assert (fork['id'],main['id'],'save') not in edges
    assert (assembly['id'],fork['id'],'assembly') in edges
    assert (assembly['id'],blend['id'],'assembly') in edges
    assert (imported['id'],assembly['id'],'import') in edges
    indices={n['id']:i for i,n in enumerate(graph['nodes'])}
    assert all(indices[e['child']]<indices[e['parent']] for e in graph['edges'])
    assert ('rhino','alternative') in graph['lanes']
    assert any(ref['label']=='main' for n in graph['nodes'] if n['id']==assembly['id'] for ref in n['refs'])
    assert any(ref['label']=='Baseline' for n in graph['nodes'] if n['id']==base['id'] for ref in n['refs'])


def test_named_versions_are_immutable_bookmarks_and_empty_branches_are_visible(tmp_path):
    p=Project.init(tmp_path/'project');snap=p.ingest(box(tmp_path/'part.usda'),'rhino')
    before=(p.stage_path(snap).parent/'manifest.json').read_bytes()
    p.name_version(snap['id'],'Print-ready');p.branch('rhino','future',snap['id'],activate=True)
    with pytest.raises(CadgitError,match='already exists'):p.name_version(snap['id'],'Print-ready')
    assert (p.stage_path(snap).parent/'manifest.json').read_bytes()==before
    graph=build_graph(p.records(),[],read_json(p.root/'cadgit.json'))
    assert any(ref.get('branch')=='future' and 'HEAD' in ref['label'] for ref in graph['nodes'][0]['refs'])


def test_graph_retains_missing_ancestry_without_invented_connections():
    record={'id':'snap_a','source':'rhino','parent':'missing','created_at':'2026-11-07','label':'Part'}
    graph=build_graph([record],[],{})
    assert len(graph['nodes'])==1 and not graph['edges']
    assert graph['missing']==[{'child':'snap_a','parent':'missing','kind':'save'}]
    assert graph['warnings']==['1 ancestry references are missing']


def test_unrelated_histories_reuse_a_compact_graph_column():
    records=[{'id':f'snap_{index}','source':f'tool_{index}','created_at':f'2026-11-07T12:{index:02}:00Z','label':'Independent source'} for index in range(12)]
    graph=build_graph(records,[],{})
    assert len(graph['lanes'])==12  # identities/colors remain distinct
    assert graph['column_count']==1
    assert {node['column'] for node in graph['nodes']}=={0}


def test_concurrent_fork_tips_occupy_neighboring_columns():
    base={'id':'base','source':'rhino','created_at':'2026-11-07T12:00:00Z','label':'Base'}
    main={**base,'id':'main_edit','parent':'base','created_at':'2026-11-07T12:01:00Z'}
    fork={**base,'id':'fork_edit','branch':'alternative','parent':'base','created_at':'2026-11-07T12:02:00Z'}
    graph=build_graph([base,main,fork],[],{})
    columns={node['id']:node['column'] for node in graph['nodes']}
    assert abs(columns['fork_edit']-columns['main_edit'])==1
    assert graph['column_count']==2


def test_empty_graph_has_no_columns_or_invented_history():
    assert build_graph([], [], {}) == {'nodes': [], 'edges': [], 'lanes': [], 'missing': [], 'cyclic': [], 'warnings': [], 'column_count': 0}


def test_graph_complete_public_topology_and_reference_contract(tmp_path,snapshot):
    import copy
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda')
    base=p.ingest(src,'rhino','Base');main=p.ingest(src,'rhino','Main')
    p.branch('rhino','alternative',base['id'],activate=True);fork=p.ingest(src,'rhino','Fork')
    blend=p.ingest(src,'blender','Blender')
    assembly=assemble(p,[{'snapshot_id':fork['id'],'prim_path':'/World/Part'},{'snapshot_id':blend['id'],'prim_path':'/World/Part'}])
    p.branch('rhino','future',base['id']);p.name_version(base['id'],'Baseline')
    records=p.records()+p.records('assemblies');by_id={r['id']:r for r in records}
    graph=build_graph(p.records(),p.records('assemblies'),p.config,assembly['id'])
    aliases={r['id']:name for r,name in [(base,'base'),(main,'main'),(fork,'fork'),(blend,'blender'),(assembly,'assembly')]}
    topology=copy.deepcopy(graph)
    for node in topology['nodes']:
        assert node.pop('record')==by_id[node['id']]
        node['id']=aliases[node['id']]
    for edge in topology['edges']:
        edge['child']=aliases[edge['child']];edge['parent']=aliases[edge['parent']]
    # Ref ordering follows a set of branches, so compare each node's ref set
    # in label order; no semantic data is omitted from the oracle.
    for node in topology['nodes']:node['refs']=sorted(node['refs'],key=lambda ref:ref['label'])
    assert topology==snapshot


def test_graph_orders_independent_heads_by_commit_sequence_not_id_or_capture_clock(tmp_path,monkeypatch):
    import cadgit.store as store
    project=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda')
    real_uid=store.uid;names=iter(['snap_zzzz_old','snap_aaaa_new'])
    monkeypatch.setattr(store,'uid',lambda prefix:next(names) if prefix=='snap' else real_uid(prefix))
    old=project.ingest(src,'older',metadata={'captured_at':'2026-11-09T12:00:00Z'})
    new=project.ingest(src,'newer',metadata={'captured_at':'2020-01-01T00:00:00Z'})
    graph=build_graph(project.records(),[],{})
    assert [n['id'] for n in graph['nodes']]==[new['id'],old['id']]
    for node in graph['nodes']:
        source=node['record']['source']
        assert node['refs']==[{'label':source+'/main • HEAD','kind':'head','source':source,'branch':'main'}]
        assert graph['lanes'][node['lane']]==(source,'main')


def test_legacy_default_branch_and_ambiguous_heads_do_not_invent_base_head(tmp_path):
    import copy
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda')
    base=p.ingest(src,'rhino');main=p.ingest(src,'rhino')
    p.branch('rhino','fork',base['id']);fork=p.ingest(src,'rhino',branch='fork')
    records=copy.deepcopy(p.records())
    for record in records:
        record.pop('branch')
    graph=build_graph(records,[],{'branches':{'rhino':{'main':{'base':base['id']}}}})
    assert graph['warnings']==['Ambiguous branch rhino/main: multiple heads; preserve history and choose a new branch from an explicit version']
    assert all(not node['refs'] for node in graph['nodes'])
    single=build_graph([records[0]],[],{})
    assert single['nodes'][0]['refs']==[{'label':'rhino/main • HEAD','kind':'head','source':'rhino','branch':'main'}]


def test_ambiguous_nondefault_branch_does_not_display_config_base_as_head(tmp_path):
    import copy
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda')
    base=p.ingest(src,'rhino')
    p.branch('rhino','fork',base['id']);p.ingest(src,'rhino',branch='fork')
    p.branch('rhino','other',base['id']);p.ingest(src,'rhino',branch='other')
    records=copy.deepcopy(p.records())
    for record in records:
        if record['branch']=='other':record['branch']='fork'
    graph=build_graph(records,[],p.config)
    assert graph['warnings']==['Ambiguous branch rhino/fork: multiple heads; preserve history and choose a new branch from an explicit version']
    assert not any(ref.get('branch')=='fork' for node in graph['nodes'] for ref in node['refs'])


def test_crossing_save_import_and_assembly_edges_keep_stable_columns(tmp_path,snapshot):
    project=Project.init(tmp_path/'project');source=box(tmp_path/'part.usda')
    originals={name:project.ingest(source,name,name+'0') for name in ['a','b','c','d']}
    edits={}
    for name,donor in [('a','c'),('b','d'),('c','a'),('d','b')]:
        edits[name]=project.ingest(source,name,name+'1',metadata={'imported_from':originals[donor]['id']})
    a2=project.ingest(source,'a','a2',metadata={'imported_from':edits['d']['id']})
    b2=project.ingest(source,'b','b2',metadata={'imported_from':edits['a']['id']})
    assembly=assemble(project,[{'snapshot_id':r['id'],'prim_path':'/World/Part'} for r in [a2,b2,edits['c'],edits['d']]],'combined')
    project.ingest(source,'c','c2',metadata={'imported_from':assembly['id']})
    project.ingest(source,'d','d2',metadata={'imported_from':a2['id']})
    graph=build_graph(project.records(),project.records('assemblies'),project.config)
    assert not graph['missing'] and not graph['cyclic']
    assert {'columns':[(node['record']['label'],node['column']) for node in graph['nodes']],
            'width':graph['column_count']}==snapshot


def test_shared_pending_parent_does_not_hide_remaining_edges_or_pull_them_left(tmp_path):
    project=Project.init(tmp_path/'project');source=box(tmp_path/'part.usda');records=[]
    for index,(app,imported) in enumerate([('d',None),('d',0),('d',None),('d',0),('c',0),('c',None),('b',5)]):
        records.append(project.ingest(source,app,str(index),metadata={'imported_from':records[imported]['id']} if imported is not None else {}))
    assemble(project,[{'snapshot_id':records[index]['id'],'prim_path':'/World/Part'} for index in [2,3,4,0]],'combined')
    graph=build_graph(project.records(),project.records('assemblies'),project.config)
    assert [(node['record']['label'],node['column']) for node in graph['nodes']]==[
        ('6',0),('5',0),('combined',1),('4',0),('3',2),('2',1),('1',1),('0',3)]
    assert graph['column_count']==4
    assert not graph['missing'] and not graph['cyclic']


def test_corrupt_cycle_keeps_space_for_all_pending_connections(tmp_path,monkeypatch):
    import copy
    import cadgit.store as store
    project=Project.init(tmp_path/'project');source=box(tmp_path/'part.usda')
    original_uid=store.uid;ids=iter(['snap_2','snap_0','snap_3','snap_4','snap_1'])
    monkeypatch.setattr(store,'uid',lambda prefix:next(ids) if prefix=='snap' else original_uid(prefix))
    for index in range(5):project.ingest(source,'a',str(index))
    records=copy.deepcopy(sorted(project.records(),key=lambda r:r['id']))
    for index,target in enumerate([1,2,2]):records[index]['parent']=records[target]['id']
    for index,record in enumerate(records):record['metadata']['imported_from']=records[(index+2)%5]['id']
    # Corrupt only the in-memory graph input; all committed records remain valid.
    graph=build_graph(records,[],{})
    assert graph['cyclic']==['snap_0','snap_1','snap_2','snap_3','snap_4']
    assert [(node['record']['label'],node['column']) for node in graph['nodes']]==[('1',0),('4',0),('0',1),('2',0),('3',2)]
    assert graph['column_count']==4
    assert all(project.verify(record['id'])['ok'] for record in project.records())
