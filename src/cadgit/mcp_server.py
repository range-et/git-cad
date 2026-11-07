"""Optional MCP facade; the GUI, CLI, and MCP share the same operations."""
from mcp.server.fastmcp import FastMCP
from .usd import assemble,export_stl,stage_info


def run(project):
    mcp=FastMCP('CAD-GIT')
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
    mcp.run(transport='stdio')
