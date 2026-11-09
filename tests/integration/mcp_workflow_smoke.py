"""Real stdio MCP workflow and recovery checks against a disposable project.

Finite scope: the 17 currently exposed tools, a successful geometry/material
journey, stale revisions, invalid references/schema, and overwrite rejection.
This does not certify every argument combination or any live native application.
Requires the optional ``mcp`` dependency; runs without a graphical session.
"""
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cadgit.demo import create


EXPECTED_TOOLS = {
    'project_status', 'history', 'inspect_snapshot', 'ingest_usd',
    'create_assembly', 'select_main', 'export_print', 'list_materials', 'verify',
    'library_list', 'library_revision', 'library_history', 'library_import',
    'library_material', 'library_recombine', 'library_verify', 'library_used_by',
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unpack(result, list_result=False):
    if result.structuredContent is not None:
        value = result.structuredContent
        return value['result'] if set(value) == {'result'} else value
    texts = [item.text for item in result.content if item.type == 'text']
    if list_result:
        return [json.loads(text) for text in texts]
    assert len(texts) == 1, texts
    return json.loads(texts[0])


async def exercise(root):
    project = create(root / 'project')
    originals = {
        path: digest(path)
        for folder in ('history', 'assemblies', 'materials', 'library')
        for path in (project.root / folder).rglob('*') if path.is_file()
    }
    cases = []
    called = set()
    server = StdioServerParameters(
        command=sys.executable,
        env={key:value for key,value in os.environ.items() if key.startswith('COVERAGE_')},
        args=['-m', 'cadgit.cli', '--project', str(project.root), 'mcp'],
    )
    with (root / 'server.log').open('w') as server_log:
        async with stdio_client(server, errlog=server_log) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == 'Git CAD'
                assert initialized.capabilities.tools is not None
                cases.append('MCP-01 initialize')
                discovered = {tool.name for tool in (await session.list_tools()).tools}
                assert EXPECTED_TOOLS <= discovered, EXPECTED_TOOLS - discovered
                cases.append('MCP-02 discover tool contract')

                async def call(name, arguments=None, *, error=False):
                    called.add(name)
                    result = await session.call_tool(name, arguments or {})
                    if error:
                        assert result.isError, (name, result)
                        assert any(item.type == 'text' and item.text for item in result.content)
                        return result
                    assert not result.isError, (name, result)
                    return unpack(result, name in {'history', 'list_materials', 'library_list', 'library_history', 'library_used_by'})

                status = await call('project_status')
                assert Path(status['root']) == project.root
                history = await call('history')
                assert len(history) == 5
                rhino = await call('history', {'source': 'rhino'})
                assert len(rhino) == 3 and all(r['source'] == 'rhino' for r in rhino)
                source = rhino[0]
                cases.append('MCP-03 status and filtered history')
                inspected = await call('inspect_snapshot', {'ref': source['id']})
                assert inspected['manifest']['id'] == source['id']
                assert inspected['scene']['prims']
                cases.append('MCP-04 inspect snapshot')
                await call('inspect_snapshot', {'ref': 'missing-version'}, error=True)
                await call('inspect_snapshot', {'ref': {'invalid': 'type'}}, error=True)
                assert (await call('verify', {'ref': source['id']}))['ok']
                cases.append('MCP-05 invalid reference/schema then recovery')

                assert isinstance(await call('list_materials'), list)
                materials = await call('library_list', {'kind': 'material'})
                assert materials and all(r['kind'] == 'material' for r in materials)
                material = await call('library_revision', {'revision': materials[0]['head']})
                revisions = await call('library_history', {'asset_id': material['asset_id']})
                assert material['id'] in {r['id'] for r in revisions}
                assert (await call('library_verify', {'revision': material['id']}))['ok']
                assert await call('library_list', {'query': 'deliberately-no-matching-label-123456'}) == []
                cases.append('MCP-06 browse material history and empty search')

                note = root / 'spec.txt'
                note.write_text('Synthetic MCP fixture: no engineering properties asserted.\n')
                imported = await call('library_import', {'path': str(note), 'label': 'MCP specification'})
                assert imported['kind'] == 'document'
                assert (await call('library_verify', {'revision': imported['id']}))['ok']
                cases.append('MCP-07 import and verify document asset')
                definition = {'physical': {'properties': {}}, 'appearance': {
                    'preview': {'base_color': [.2, .4, .7], 'roughness': .3, 'metallic': 0.}},
                    'documents': [imported['id']]}
                created = await call('library_material', {'label': 'MCP material', 'definition': definition})
                revised = await call('library_material', {'label': 'MCP material revision',
                    'definition': definition, 'asset_id': created['asset_id'], 'expected_revision': created['id']})
                assert revised['asset_id'] == created['asset_id'] and revised['id'] != created['id']
                before = len(await call('library_history', {'asset_id': created['asset_id']}))
                await call('library_material', {'label': 'Stale revision', 'definition': definition,
                    'asset_id': created['asset_id'], 'expected_revision': created['id']}, error=True)
                assert len(await call('library_history', {'asset_id': created['asset_id']})) == before
                cases.append('MCP-08 material revision and stale-write rejection')
                combined = await call('library_recombine', {'label': 'MCP recombined',
                    'physical_from': material['id'], 'appearance_from': revised['id'], 'note': 'Protocol fixture'})
                assert combined['definition']['appearance'] == revised['definition']['appearance']
                assert combined['definition']['physical'] == material['definition']['physical']
                assert (await call('library_verify', {'revision': combined['id']}))['ok']
                cases.append('MCP-09 recombine pinned material representations')

                ingested = await call('ingest_usd', {'path': str(project.stage_path(source)),
                    'source': 'manual', 'label': 'Protocol imported scene'})
                assert ingested['source'] == 'manual' and ingested['id'] != source['id']
                selection = {'snapshot_id': ingested['id'], 'prim_path': '/Engine/Block',
                    'library_material_revision': combined['id']}
                assembly = await call('create_assembly', {'selections': [selection], 'label': 'MCP assembly'})
                assert assembly['selections'][0]['snapshot_id'] == ingested['id']
                assert assembly['selections'][0]['library_material_revision'] == combined['id']
                assert (await call('verify', {'ref': assembly['id']}))['ok']
                cases.append('MCP-10 ingest then compose with exact lineage')
                await call('select_main', {'ref': assembly['id']})
                assert (await call('inspect_snapshot', {'ref': 'main'}))['manifest']['id'] == assembly['id']
                users = await call('library_used_by', {'revision': combined['id']})
                assert assembly['id'] in json.dumps(users), users
                cases.append('MCP-11 select main and material usage lookup')
                output = root / 'part.stl'
                artifact = await call('export_print', {'ref': 'main', 'output': str(output)})
                assert artifact['source_id'] == assembly['id']
                assert artifact['report']['units'] == 'mm' and artifact['report']['triangles'] > 0
                assert not artifact['report']['printability_certified']
                original_output = digest(output)
                await call('export_print', {'ref': 'main', 'output': str(output)}, error=True)
                assert digest(output) == original_output
                assert (await call('verify', {'ref': artifact['id']}))['ok']
                # Mutate only this disposable newly-created artifact, never
                # source snapshots; prove protocol verification notices damage.
                archived_stl = Path(artifact['_directory']) / artifact['entry_layer']
                payload = archived_stl.read_bytes()
                try:
                    archived_stl.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
                    damaged = await call('verify', {'ref': artifact['id']})
                    assert not damaged['ok'] and any('Hash mismatch' in e for e in damaged['errors'])
                finally:
                    archived_stl.write_bytes(payload)
                assert (await call('verify', {'ref': artifact['id']}))['ok']
                assert (await call('verify', {'ref': assembly['id']}))['ok']
                cases.append('MCP-12 export artifact and reject overwrite without damage')
                cases.append('MCP-13 verify artifact ID detects corruption then recovery')
                await call('create_assembly', {'selections': [{'snapshot_id': 'missing-version',
                    'prim_path': '/Engine/Block'}], 'label': 'Bad assembly'}, error=True)
                assert (await call('inspect_snapshot', {'ref': 'main'}))['manifest']['id'] == assembly['id']
                cases.append('MCP-14 failed assembly leaves main unchanged and session usable')
                assert EXPECTED_TOOLS <= called, EXPECTED_TOOLS - called
    assert all(path.exists() and digest(path) == checksum for path, checksum in originals.items())
    cases.append('MCP-15 original immutable archives unchanged')
    print('MCP_WORKFLOW_VERIFIED: ' + json.dumps({'cases': cases, 'tools_exercised': sorted(called)}))


def main():
    with tempfile.TemporaryDirectory(prefix='cadgit-mcp-smoke-') as temporary:
        asyncio.run(asyncio.wait_for(exercise(Path(temporary)), timeout=120))


if __name__ == '__main__':
    main()
