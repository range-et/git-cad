"""Optional MCP facade; the GUI, CLI, and MCP share the same operations."""
from mcp.server.fastmcp import FastMCP
from .usd import assemble,export_stl,stage_info


def run(project):
    mcp=FastMCP('Git CAD')
    @mcp.tool()
    def project_status()->dict:
        from .service import status
        return {'root':str(project.root),'snapshots':project.records(),'assemblies':project.records('assemblies'),'service':status(project)}
    @mcp.tool()
    def history(source:str='')->list:
        return [r for r in project.records() if not source or r['source']==source]
    @mcp.tool()
    def inspect_snapshot(ref:str)->dict:
        r=project.resolve(ref);return {'manifest':r,'scene':stage_info(project.stage_path(r))}
    @mcp.tool()
    def ingest_usd(path:str,source:str='manual',label:str='')->dict:
        return project.ingest(path,source,label or None)
    @mcp.tool()
    def create_assembly(selections:list[dict],label:str)->dict:
        return assemble(project,selections,label)
    @mcp.tool()
    def select_main(ref:str)->dict:return project.set_main(ref)
    @mcp.tool()
    def export_print(ref:str,output:str,prim_path:str='',allow_base_mesh:bool=False,allow_mesh_issues:bool=False)->dict:
        return export_stl(project,ref,output,prim_path or None,allow_issues=allow_mesh_issues,allow_base_mesh=allow_base_mesh)
    @mcp.tool()
    def list_materials()->list:return project.records('materials')
    @mcp.tool()
    def verify(ref:str)->dict:return project.verify(ref)
    from .library import Library
    library=Library(project)
    @mcp.tool()
    def library_list(kind:str='',query:str='')->list:return library.summaries(kind or None,query)
    @mcp.tool()
    def library_revision(revision:str)->dict:return library.get(revision)
    @mcp.tool()
    def library_history(asset_id:str)->list:return library.history(asset_id)
    @mcp.tool()
    def library_import(path:str,label:str='',kind:str='',asset_id:str='',expected_revision:str='',parents:list[dict]|None=None,provenance:dict|None=None)->dict:
        return library.import_asset(path,label or None,kind or None,asset_id or None,expected_revision or None,parents,provenance)
    @mcp.tool()
    def library_material(label:str,definition:dict,asset_id:str='',expected_revision:str='',provenance:dict|None=None)->dict:
        return library.create_material(label,definition,asset_id or None,expected_revision or None,provenance=provenance)
    @mcp.tool()
    def library_recombine(label:str,physical_from:str,appearance_from:str,note:str='')->dict:return library.recombine(label,physical_from,appearance_from,note)
    @mcp.tool()
    def library_verify(revision:str)->dict:return library.verify(revision)
    @mcp.tool()
    def library_used_by(revision:str)->list:return library.used_by(revision)
    mcp.run(transport='stdio')
