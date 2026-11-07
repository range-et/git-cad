import pytest
from cadgit.history_graph import build_graph
from cadgit.store import Project,CadgitError,read_json
from cadgit.usd import assemble
from test_history import box


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
