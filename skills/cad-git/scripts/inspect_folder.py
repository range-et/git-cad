#!/usr/bin/env python3
"""Read-only onboarding inventory. No CAD-GIT installation or native app required."""
import argparse
import json
import os
from pathlib import Path

RESERVED=('history','assemblies','materials','artifacts','main','.cadgit','mcp.example.json')
SKIP={'.git','.venv','venv','node_modules','__pycache__','.cadgit','.bridge','.pytest_cache'}
GROUPS={
    'rhino':{'.3dm'},
    'blender':{'.blend'},
    'usd':{'.usd','.usda','.usdc','.usdz'},
    'backups':{'.blend1','.blend2','.3dmbak'},
    'other_exchange':{'.step','.stp','.iges','.igs','.obj','.stl','.fbx','.3mf','.fcstd','.sldprt','.sldasm'},
    'materials_and_images':{'.mtlx','.sbsar','.png','.jpg','.jpeg','.tif','.tiff','.exr','.hdr','.webp'},
}


def inspect_folder(folder,limit=200):
    root=Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('Input must be an existing directory')
    config_path=root/'cadgit.json';config={'present':config_path.exists() or config_path.is_symlink()}
    warnings=[]
    if config['present']:
        try:
            data=json.loads(config_path.read_text(encoding='utf-8'))
            config.update(readable=True,is_object=isinstance(data,dict))
            if isinstance(data,dict):config['schema_version']=data.get('schema_version')
        except (OSError,ValueError) as exc:
            config.update(readable=False);warnings.append('Existing cadgit.json needs inspection: '+str(exc))
    conflicts=[name for name in RESERVED if (root/name).exists() or (root/name).is_symlink()] if not config['present'] else []
    if not config['present'] and ((root/'source').exists() or (root/'source').is_symlink()) and not (root/'source').is_dir():conflicts.append('source (not a directory)')
    suggested=root
    if conflicts:
        suggested=root/'cad-project';number=2
        while suggested.exists() or suggested.is_symlink():
            suggested=root/('cad-project-'+str(number));number+=1
    groups={name:{'count':0,'files':[]} for name in GROUPS};symlinks=[];symlink_count=0;nested=[]
    def walk_error(error):warnings.append('Unreadable path: '+str(error))
    for directory,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
        here=Path(directory);kept=[]
        marker=here/'cadgit.json'
        if here!=root and (marker.exists() or marker.is_symlink()):nested.append(str(here.relative_to(root)))
        looks_initialized=False
        if marker.is_file():
            try:
                value=json.loads(marker.read_text(encoding='utf-8'))
                looks_initialized=isinstance(value,dict) and isinstance(value.get('id'),str) and isinstance(value.get('name'),str)
            except (OSError,ValueError):pass
        for name in sorted(dirs):
            child=here/name
            if child.is_symlink():
                symlink_count+=1
                if len(symlinks)<limit:symlinks.append(str(child.relative_to(root)))
                continue
            if name in SKIP or name.startswith('.cadgit-init-'):continue
            if looks_initialized and name in {'history','assemblies','materials','artifacts','main'}:continue
            kept.append(name)
        dirs[:]=kept
        for name in sorted(files):
            child=here/name
            if child.is_symlink():
                symlink_count+=1
                if len(symlinks)<limit:symlinks.append(str(child.relative_to(root)))
                continue
            suffix=child.suffix.lower();group=next((key for key,extensions in GROUPS.items() if suffix in extensions),None)
            if group is None:continue
            groups[group]['count']+=1
            if len(groups[group]['files'])>=limit:continue
            try:groups[group]['files'].append({'path':str(child.relative_to(root)),'bytes':child.stat().st_size})
            except OSError as exc:warnings.append('Unreadable file metadata: '+str(exc))
    if not config['present'] and len(nested)==1:suggested=root/nested[0]
    for group in groups.values():group['omitted']=group['count']-len(group['files'])
    return {
        'root':str(root),'config':config,
        'initialization':{'mode':'existing_config_needs_tool_validation' if config['present'] else 'existing_nested_config_needs_tool_validation' if len(nested)==1 else 'new_child_recommended' if conflicts else 'in_place_candidate','reserved_conflicts':conflicts,'suggested_project_root':str(suggested)},
        'nested_project_configs':nested,
        'candidates':groups,'symlinks_not_followed':{'count':symlink_count,'paths':symlinks},
        'warnings':warnings,'path_limit_per_group':limit,
        'note':'Read-only inventory; CAD-GIT status/init and actual exports provide validation. Native files and dependencies were not opened or modified.',
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path);parser.add_argument('--limit',type=int,default=200,help='Maximum listed paths per group; counts remain complete')
    args=parser.parse_args()
    if args.limit<0:parser.error('--limit must be nonnegative')
    try:result=inspect_folder(args.folder,args.limit)
    except (OSError,ValueError) as exc:parser.error(str(exc))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
