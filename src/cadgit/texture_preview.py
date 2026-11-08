"""CPU-side USD preview texture loading; no renderer or source files are modified."""
from __future__ import annotations
import numpy as np
from pxr import Ar, Sdf, Usd, UsdGeom, UsdShade
from PySide6 import QtCore, QtGui


class TexturePreviewError(ValueError):
    pass


def image_pixels(path, cache):
    """Read through Ar so package-relative images work without extracting USDZ."""
    if path in cache:return cache[path]
    asset=Ar.GetResolver().OpenAsset(Ar.ResolvedPath(path))
    if not asset:raise TexturePreviewError('image cannot be opened')
    if asset.GetSize()>64*1024*1024:raise TexturePreviewError('image exceeds the 64 MB preview limit')
    buffer=QtCore.QBuffer();buffer.setData(asset.GetBuffer());buffer.open(QtCore.QIODevice.ReadOnly)
    reader=QtGui.QImageReader(buffer);size=reader.size()
    if size.width()<=0 or size.height()<=0 or size.width()*size.height()>8192**2:
        raise TexturePreviewError('unsupported image or image exceeds the 64 megapixel preview limit')
    # Bound GPU uploads and packing work, including for ordinary 4K/8K assets.
    if max(size.width(),size.height())>2048:
        scaled=size.scaled(QtCore.QSize(2048,2048),QtCore.Qt.KeepAspectRatio)
        reader.setScaledSize(QtCore.QSize(max(1,scaled.width()),max(1,scaled.height())))
    image=reader.read()
    if image.isNull():raise TexturePreviewError('image could not be decoded')
    space=image.colorSpace()
    grayscale=image.format() in (QtGui.QImage.Format_Grayscale8,QtGui.QImage.Format_Grayscale16) or (image.format()==QtGui.QImage.Format_Indexed8 and image.isGrayscale())
    auto_srgb=space.transferFunction()==QtGui.QColorSpace.TransferFunction.SRgb if space.isValid() else image.depth()<=32 and not grayscale
    metadata={axis:image.text('wrap'+axis) for axis in ('S','T')};metadata['srgb']=auto_srgb
    image=image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    pixels=np.frombuffer(image.constBits(),dtype=np.uint8).reshape(image.height(),image.bytesPerLine())[:,:image.width()*4].reshape(image.height(),image.width(),4).copy()
    cache[path]=(pixels,metadata)
    return cache[path]


def box_uv(points,counts,indices):
    """Per-face box projection for inspection when a mesh has no authored UVs."""
    span=np.ptp(points,axis=0);normalized=(points-points.min(axis=0))/np.where(span>0,span,1)
    result=[];offset=0
    for count in counts:
        face=indices[offset:offset+count];offset+=count;p=points[face]
        normal=np.sum(np.cross(p,np.roll(p,-1,axis=0)),axis=0)
        axis=int(np.argmax(np.abs(normal)));axes=[i for i in range(3) if i!=axis]
        result.extend(normalized[face][:,axes])
    return np.asarray(result)


def primvar_uv(mesh,name,counts,indices,corners,time,warnings):
    uv=UsdGeom.PrimvarsAPI(mesh).FindPrimvarWithInheritance(name)
    if not uv or not uv.HasValue():
        warnings.append('No UV coordinates for '+name+'; Rendered preview uses box mapping. Exported geometry is unchanged.')
        return box_uv(np.asarray(mesh.GetPointsAttr().Get(time)),counts,indices)[corners]
    values=np.asarray(uv.ComputeFlattened(time),dtype=float)
    if values.ndim!=2 or values.shape[1]!=2 or not np.isfinite(values).all():
        raise TexturePreviewError('invalid UV coordinates: '+name)
    interpolation=uv.GetInterpolation()
    if interpolation in ('vertex','varying'):
        if len(values)!=len(mesh.GetPointsAttr().Get(time)):raise TexturePreviewError('UV vertex count does not match geometry')
        values=values[indices]
    elif interpolation=='uniform':
        if len(values)!=len(counts):raise TexturePreviewError('UV face count does not match geometry')
        values=np.repeat(values,counts,axis=0)
    elif interpolation=='constant':
        if len(values)!=1:raise TexturePreviewError('invalid constant UV coordinates')
        values=np.repeat(values,len(indices),axis=0)
    elif interpolation!='faceVarying':raise TexturePreviewError('unsupported UV interpolation: '+interpolation)
    if len(values)!=len(indices):raise TexturePreviewError('UV corner count does not match geometry')
    return values[corners]


def texture_uv(input,mesh,counts,indices,corners,time,warnings,depth=0):
    if depth>8:raise TexturePreviewError('UV connection chain is too deep')
    connection=input.GetConnectedSource()
    if not connection:
        value=input.Get(time)
        if value is None:value=(0,0)
        return np.tile(np.asarray(value,dtype=float),(len(corners),1))
    node=UsdShade.Shader(connection[0].GetPrim());kind=node.GetIdAttr().Get()
    if kind=='UsdPrimvarReader_float2':
        name=node.GetInput('varname').Get(time)
        if not isinstance(name,str) or not name:raise TexturePreviewError('UV reader has no primvar name')
        return primvar_uv(mesh,name,counts,indices,corners,time,warnings)
    if kind=='UsdTransform2d':
        uv=texture_uv(node.GetInput('in'),mesh,counts,indices,corners,time,warnings,depth+1)
        scale=node.GetInput('scale').Get(time);rotation=node.GetInput('rotation').Get(time);translation=node.GetInput('translation').Get(time)
        angle=np.deg2rad(rotation or 0);matrix=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        return (uv*np.asarray(scale if scale is not None else (1,1)))@matrix.T+np.asarray(translation if translation is not None else (0,0))
    raise TexturePreviewError('unsupported UV node: '+str(kind))


def surface_maps(mesh,shader,counts,indices,corners,time,warnings,cache):
    maps={}
    if shader.GetIdAttr().Get()!='UsdPreviewSurface':return maps
    for role,parameter in [('base_color','diffuseColor'),('roughness','roughness'),('metallic','metallic'),('opacity','opacity')]:
        input=shader.GetInput(parameter)
        if not input or not input.HasConnectedSource():continue
        try:
            connection=input.GetConnectedSource();node=UsdShade.Shader(connection[0].GetPrim())
            if node.GetIdAttr().Get()!='UsdUVTexture':raise TexturePreviewError('unsupported texture node: '+str(node.GetIdAttr().Get()))
            file=node.GetInput('file').Get(time)
            if not isinstance(file,Sdf.AssetPath):raise TexturePreviewError('image file input must be a USD asset path')
            if not file or not file.resolvedPath:raise TexturePreviewError('image path cannot be resolved')
            uv=texture_uv(node.GetInput('st'),mesh,counts,indices,corners,time,warnings)
            if uv.shape!=(len(corners),2) or not np.isfinite(uv).all():raise TexturePreviewError('invalid texture coordinates')
            channel=str(connection[1])
            if channel not in {'rgb','r','g','b','a'}:raise TexturePreviewError('unsupported texture output: '+channel)
            color_space=node.GetInput('sourceColorSpace').Get(time) or 'auto'
            if color_space not in {'auto','sRGB','raw'}:raise TexturePreviewError('unsupported image color space: '+str(color_space))
            pixels,metadata=image_pixels(file.resolvedPath,cache)
            wraps=[node.GetInput('wrap'+axis).Get(time) or 'useMetadata' for axis in ('S','T')]
            wraps=[metadata.get(axis) or 'black' if wrap=='useMetadata' else wrap for axis,wrap in zip(('S','T'),wraps)]
            if any(w not in {'repeat','clamp','black','mirror'} for w in wraps):raise TexturePreviewError('unsupported texture wrap mode: '+str(wraps))
            # VTK uses one wrapping mode and one UV array per surface.
            if wraps[0]!=wraps[1]:raise TexturePreviewError('different S/T wrap modes are not supported')
            scale=node.GetInput('scale').Get(time);bias=node.GetInput('bias').Get(time)
            scale=tuple(scale) if scale is not None else (1,1,1,1);bias=tuple(bias) if bias is not None else (0,0,0,0)
            if len(scale)!=4 or len(bias)!=4 or not np.isfinite([scale,bias]).all():raise TexturePreviewError('invalid texture scale or bias')
            maps[role]={'pixels':pixels,'uv':uv,'channel':channel,'srgb':color_space=='sRGB' or (color_space=='auto' and metadata['srgb']),'wrap':wraps[0],'scale':scale,'bias':bias}
        except (TexturePreviewError,ValueError,TypeError,RuntimeError) as exc:
            warnings.append(role+' texture not displayed: '+str(exc))
    for parameter in ('normal','displacement','occlusion','emissiveColor'):
        input=shader.GetInput(parameter)
        if input and input.HasConnectedSource():warnings.append(parameter+' map is not evaluated by Rendered preview')
    return maps


def linear_pixels(texture):
    value=texture['pixels'].astype(np.float32)/255
    if texture['srgb']:
        rgb=value[:,:,:3];value[:,:,:3]=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    value=value*np.asarray(texture['scale'],dtype=np.float32)+np.asarray(texture['bias'],dtype=np.float32)
    channel=texture['channel']
    return np.clip(value[:,:,:3] if channel=='rgb' else value[:,:,'rgba'.index(channel)],0,1)


def resize_pixels(array,width,height):
    """Linear resampling for packing scalar maps into VTK's shared ORM texture."""
    if array.shape[:2]==(height,width):return array
    y=np.linspace(0,array.shape[0]-1,height,dtype=np.float32);x=np.linspace(0,array.shape[1]-1,width,dtype=np.float32)
    y0=y.astype(int);x0=x.astype(int);y1=np.minimum(y0+1,array.shape[0]-1);x1=np.minimum(x0+1,array.shape[1]-1)
    fy=(y-y0)[:,None];fx=(x-x0)[None,:]
    if array.ndim==3:fy=fy[:,:,None];fx=fx[:,:,None]
    return (array[y0[:,None],x0[None,:]]*(1-fx)+array[y0[:,None],x1[None,:]]*fx)*(1-fy)+(array[y1[:,None],x0[None,:]]*(1-fx)+array[y1[:,None],x1[None,:]]*fx)*fy


def render_maps(part):
    """Pack compatible USD maps for VTK PBR, retaining visible fallback warnings."""
    maps=part.get('texture_maps',{})
    if not maps:return None
    first=maps.get('base_color') or next(iter(maps.values()));accepted={}
    for role,texture in maps.items():
        if texture['wrap']!=first['wrap'] or texture['uv'].shape!=first['uv'].shape or not np.allclose(texture['uv'],first['uv']):
            part['warnings'].append(role+' texture not displayed: maps on one surface need matching UVs and wrap modes')
        else:accepted[role]=texture
    result={'uv':first['uv'],'wrap':first['wrap'],'border_opacity':0. if 'opacity' in accepted else part.get('opacity',1.)}
    if 'base_color' in accepted or 'opacity' in accepted:
        dimensions=[texture['pixels'].shape[:2] for role,texture in accepted.items() if role in {'base_color','opacity'}]
        height=max(size[0] for size in dimensions);width=max(size[1] for size in dimensions)
        if 'base_color' in accepted:
            color=linear_pixels(accepted['base_color'])
            if color.ndim==2:color=np.repeat(color[:,:,None],3,axis=2)
            color=resize_pixels(color,width,height)
        else:color=np.broadcast_to(np.asarray(part['color'],dtype=np.float32),(height,width,3))
        srgb=np.where(color<=.0031308,color*12.92,1.055*np.power(color,1/2.4)-.055)
        alpha=np.full((height,width),part.get('opacity',1.),dtype=np.float32)
        if 'opacity' in accepted:
            alpha=linear_pixels(accepted['opacity'])
            if alpha.ndim==3:alpha=alpha[:,:,0]
            alpha=resize_pixels(alpha,width,height)
        result['base_color']=np.round(np.clip(np.dstack([srgb,alpha]),0,1)*255).astype(np.uint8)
    if 'roughness' in accepted or 'metallic' in accepted:
        dimensions=[texture['pixels'].shape[:2] for role,texture in accepted.items() if role in {'roughness','metallic'}]
        height=max(size[0] for size in dimensions);width=max(size[1] for size in dimensions)
        orm=np.ones((height,width,3),dtype=np.float32);orm[:,:,1]=part.get('roughness',.4);orm[:,:,2]=part.get('metallic',0.)
        for role,index in [('roughness',1),('metallic',2)]:
            if role in accepted:
                value=linear_pixels(accepted[role])
                if value.ndim==3:value=value[:,:,0]
                orm[:,:,index]=resize_pixels(value,width,height)
        result['orm']=np.round(np.clip(orm,0,1)*255).astype(np.uint8)
        result['orm_border']=(1.,0. if 'roughness' in accepted else part.get('roughness',.4),0. if 'metallic' in accepted else part.get('metallic',0.),1.)
    return result
