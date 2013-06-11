# -*- coding: utf8 -*-
"""Diagnostic about dynamics"""

import numpy as N, cdms2, MV2
from vacumm import VACUMMError
from vacumm.data.cf import format_var, format_grid
from vacumm.misc.phys.constants import gravity as default_gravity
from vacumm.misc.axes import isaxis
from vacumm.misc.grid.regridding import shiftgrid
from vacumm.misc.grid import set_grid, get_axis_slices, resol
from vacumm.misc.filters import generic2d

def barotropic_geostrophic_velocity(ssh, dxy=None, gravity=default_gravity, cyclic=False, 
    format_axes=True, getu=True, getv=True, filter=None):
    """Get barotropic geostropic velocity from SSH on a C-grid
    
    .. note:: ssh is supposed to be at T points,
        ubt is computed at V points, 
        and vbt is computed at U points.
    
    :Params:
    
        - **ssh**: Sea surface height.
        - **dxy**, optional: Horizontal resolutions (m). 
          Resolution along X and Y are respectively at U and V points.
          Possible forms:
        
            - ``res``: A scalar meaning a constant resolution along X and Y.
            - ``(dx,dy)``: A tuple of resolutions along X and Y.
            - ``None``: Resolution is estimated using
              :func:`~vacumm.misc.grid.misc.resol`.
        
    :Return: ``(ubt,vbt)``
    """
    if not getu and not getv: return
    
    # Init masked
    if getu: ugbt = format_var(ssh*MV2.masked, 'ugbt', format_axes=False)
    if getv: vgbt = format_var(ssh*MV2.masked, 'vgbt', format_axes=False)
    
    # Grid
    tgrid = ssh.getGrid()
    if getu: ugrid = shiftgrid(tgrid, ishift=0.5)
    if getv: vgrid = shiftgrid(tgrid, jshift=0.5)
    if format_axes:
        if getv: format_grid(ugrid, 'u')
        if getu: format_grid(vgrid, 'v')
    if getu: set_grid(ugbt, vgrid)
    if getv: set_grid(vgbt, ugrid)
    
    # Resolutions
    if dxy is None:
        dxt, dyt = resol(ssh, proj=True, mode='local')
        dxu = 0.5*(dxt[:, 1:]+dxt[:, :-1]) ; del dxt
        dyv = 0.5*(dyt[1:, :]+dyt[:-1, :]) ; del dyt
    elif not isinstance(dxy, (list, tuple)):
        dxu = dyv = dxy
    else:
        dxu,  dyv = dxy
    if getv and isinstance(dxu, N.ndarray):
        if cdms2.isVariable(dxu): dxu = dxu.asma()
        if dxu.ndim==1: dxu.shape = 1, -1
        if dxu.shape[1]==ssh.shape[-1]:
            dxu = dxu[:, :-1]
    if getu and isinstance(dyv, N.ndarray):
        if cdms2.isVariable(dyv): dyv = dyv.asma()
        if dyv.ndim==1: dyv.shape = -1, 1
        if dyv.shape[0]==ssh.shape[-2]:
            dyv = dyv[:-1]
            
            
    # Get geostrophic factor
    f0 = coriolis_parameter(ssh, gravity=gravity, fromvar=True).asma()
    bad = f0==0.
    f0[bad] = 1.
    f0[bad] = N.ma.masked ; del bad
    gf = gravity/f0 ; del f0

    # Computes
    sshm = ssh.asma()
    sshm *= gf ; del gf
    if getu: ugbt[..., :-1, :] = -N.ma.diff(sshm, axis=-2)/dyv ; del dyv
    if getv: vgbt[..., :-1] = N.ma.diff(sshm, axis=-1)/dxu ; del dxu
    del sshm
    if getu and cyclic:
        ugbt[..., -1] = ugbt[..., 0]
        
    if not getu: return vgbt
    elif not getv: return ugbt
    return ugbt, vgbt

def coriolis_parameter(lat, gravity=default_gravity, fromvar=False, format_axes=False):
    """Get the coriolis parameters computed at each latitude
    
    :Params:
    
        - **lat**: Latitude or a variable with latitude coordinates.
        - **gravity**, optional: Gravity.
        - **fromvar**, optional: If True, lat is supposed to be a MV2
          array with latitude coordinates.
    """
    
    # Latitude
    if fromvar: 
        if not cdms2.isVariable(lat):
            raise VACUMMError('lat must a MV2 array because fromvar is True')
        latv = lat*0
        lat = lat.getLatitude()
        if lat is None:
            raise VACUMMError('lat must a MV2 array with a latitude axis because fromvar is True')
        if cdms2.isVariable(lat): lat=lat.asma() # 2D axes
        if lat.shape!=latv.shape:
            if len(lat.shape)==2:
                latv[:] = N.ma.resize(lat, latv.shape)
            else:
                yaxis = latv.getOrder().index('y')
                new_shape = len(latv.shape)*[1]
                new_shape[yaxis] = latv.shape[yaxis]
                tile_shape = list(latv.shape)
                tile_shape[yaxis] = 1
                latv[:] = N.tile(lat.getValue().reshape(new_shape), tile_shape)
    else:
        latv = lat.getValue() if isaxis(lat) else lat
    
    # Compute
    f0 = 2*N.sin(N.pi*latv/180.)
    f0 *= 2*N.pi/(24.*3600.)
    
    
    # Format
    if not hasattr(f0, '__len__'): return f0
    f0 = MV2.asarray(f0)
    if not fromvar and isaxis(lat) and f0.ndim==1:
        f0.setAxis(0, lat)
    return format_var(f0, 'f0', format_axes=format_axes)
   

def eddy_kinetic_energy(sshuv, gravity=default_gravity, format_axes=None, dxy=None):
    """Compute EKE either from SSH or velocity on  C-grid
    
    :Params:
    
        - **sshuv**: SSH or (U,V).
        
            - If SSH, velocity are computed at U and V points
              using :func:`barotropic_geostrophic_velocity`.
            - If (U,V), velocities are supposed to be at V and U points.
            
        - **dxy**, optional: Horizontal resolutions (see :func:`barotropic_geostrophic_velocity`).
            
    :Return: EKE at T points.
    """
    
    # Init and get velocities
    if cdms2.isVariable(sshuv): # from SSH
        eke = sshuv*MV2.masked
        u, v = barotropic_geostrophic_velocity(ssh, dxy=dxy, gravity=gravity, format_axes=format_axes)
        if format_axes is None: format_axes = False
    else: # from (U,V)
        u, v = sshuv
        eke = u*MV2.masked
        if format_axes is None: format_axes = True
        gridt = shiftgrid(u.getGrid(), jshift=1)
        set_grid(eke, gridt)
    
    # Sum contributions
    uf = u.filled(0.)
    vf = v.filled(0.)
    eke[..., 1:, :] =  uf[..., 1:,  :]**2
    eke[..., 1:, :] += uf[..., :-1, :]**2
    eke[..., 1:]    += vf[..., :-1]**2
    eke[..., 1:]    += vf[..., :-1]**2
    
    # Weight and mask
    count = N.zeros(eke.shape, 'i')
    gu = 1-N.ma.getmaskarray(u).astype('i')
    gv = 1-N.ma.getmaskarray(v).astype('i')
    count[1:] = gu[:-1]
    count[1:] += gu[1:]
    count[:, 1:] += gv[:, :-1]
    count[:, 1:] += gv[:, 1:]
    del gu, gv
    mask = count==0
    count[mask] = 1
    eke[:] /= count
    eke[:] = MV2.masked_where(mask, eke, copy=0)
    del mask, count
    
    # Format
    if format_axes:
        format_grid(gridt, 't')
    return format_var(eke, "eke", format_axes=False)
    
        
