# -*- coding: utf8 -*-
"""Utilities derived from mpl_toolkits.basemap"""

# Copyright or © or Copr. Actimar (contributor(s) : Stephane Raynaud) (2010)
# 
# raynaud@actimar.fr
# 
# 
# This software is a computer program whose purpose is to provide
# utilities for handling oceanographic and atmospheric data,
# with the ultimate goal of validating the MARS model from IFREMER.
# 
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software.  You can  use, 
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info". 
# 
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability. 
# 
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or 
# data to be ensured and,  more generally, to use and operate it in the 
# same conditions as regards security. 
# 
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.
# 
__all__  = ['gshhs_reslist', 'gshhs_autores', 'cached_map', 'cache_map', 'get_map', 
'GSHHS_BM', 'merc', 'proj', 'clean_cache', 'reset_cache', 'get_map_dir', 'get_proj', 
'create_map']
__all__.sort()

import numpy as N
from mpl_toolkits.basemap import Basemap
from mpl_toolkits.basemap.proj import Proj
from matplotlib import get_configdir
import os, cPickle, stat
from _geoslib import Polygon
#FIXME:imports
from genutil import minmax
from ...misc.io import Shapes
from misc import get_xy
from ...misc.phys.constants import R as rsphere_mean
from ...misc.misc import kwfilter

#: Earth radius of wgs84 ellipsoid
rshpere_wgs84 = (6378137.0,6356752.3141)

#: GSHHS shorelines letters
gshhs_reslist = ['f', 'h', 'i', 'l', 'c']

def gshhs_autores(lon_min, lon_max, lat_min, lat_max):
    """Guess best resolution from lon/lat bounds"""
    testresol=((lon_max-lon_min)+(lat_max-lat_min))/2.0
    ires = N.array([-1.,1. ,5.,15.,50.]).searchsorted(testresol)-1
    return gshhs_reslist[ires]
    
# Cached maps
def cached_map(m=None, mapdir=None, verbose=False, **kwargs):
    """Check if we have a cached map
    
    - *m*: A Basemap instance [Default: None]
    - *mapdir*: Where are stored the cached maps. If ``None``, :func:`matplotlib.get_configdir` is used as a parent directory, which is the matplotlib configuration directory (:file:`~/.matplotlib` undex linux), and :file:`basemap/cached_maps` as the subdirectory.
    
    :Example:
    
    >>> m = cached_map(lon_min=-5, lon_max=6, lat_min=40, lat_max=50, projection='lcc', resolution='f')
    >>> m = cached_map(m) # Does only caching of map
    """
    # We already have one in live memory
    if isinstance(m, Basemap): 
        # Save it
        cache_map(m, mapdir=mapdir)
        # Get it
        return m
    # Guess 
    file = _cached_map_file_(mapdir=mapdir, **kwargs)
    if file is None: return None
    if verbose: print 'Checking', file, os.path.exists(file)
    if not os.path.exists(file): return None
    if verbose: print 'Loadind cached map from '+os.path.basename(file)
    try:
        f = open(file)
        m = cPickle.load(f)
        f.close()
        return m
    except:
        os.remove(file)
        return None

def cache_map(m, mapdir=None):
    """Cache a map if still not cached"""
    if m is None or m.resolution is None: return
    file = _cached_map_file_(m, mapdir=mapdir)
    if file is None: return
    if not os.path.exists(file):
#       print 'Caching map to '+os.path.basename(file)
        f = open(file, 'wb')
        m.ax = None
        cPickle.dump(m, f)
        f.close()
        # Access to all if not in user directory
        if not file.startswith(os.path.expanduser("~")):
            os.chmod(file, stat.S_IROTH+stat.S_IWOTH+stat.S_IWGRP+stat.S_IRGRP+stat.S_IWUSR+stat.S_IRUSR)

def clean_cache(mapdir=None, maxsize=10.*1024*1024):
    """Clean cache directory by checking its size
    
    :Params:
    
        - **mapdir**, optional: Directory where maps are cached
        - **maxsize**, optional: Maximal size of directory in bytes
    """
    from ...misc.misc import dirsize
    mapdir = get_map_dir(mapdir)
    if mapdir is None:
        mapdir = os.path.join(get_configdir(), 'basemap', 'cached_maps')
    cache_size = dirsize(mapdir)
    if cache_size>maxsize:
        files = [os.path.join(mapdir, ff) for ff in os.listdir(mapdir)]
        files.sort(cmp=lambda f1, f2: cmp(os.stat(f1)[8], os.stat(f2)[8]))
        for ff in files:
            cache_size -= os.path.getsize(ff)
            os.remove(ff)
            if cache_size<=maxsize: break

def reset_cache(mapdir=None):
    """Remove all cached maps"""
    mapdir = get_map_dir(mapdir)
    for file in [os.path.join(mapdir, ff) for ff in os.listdir(mapdir)]:
        os.remove(file)

def get_map_dir(mapdir=None):
    """Get the directory where cqched maps are stored"""
    if mapdir is None:
        mapdir = os.path.join(get_configdir(), 'basemap', 'cached_maps')
    return mapdir

def _cached_map_file_(m=None, mapdir=None, **kwargs):
    mapdir = get_map_dir(mapdir)
    if not os.path.exists(mapdir):
        os.makedirs(mapdir)
    if m is None:
        if kwargs.has_key('resolution') and kwargs['resolution'] is None:
            return None
        res = kwargs['resolution']
        kwargs['resolution'] = None
        m = Basemap(**kwargs)
    elif m.resolution is None:
        return None
    else:
        res = m.resolution
    srs = m.srs.replace(' ', '')+'+res='+res
    szone = '+%.5f+%.5f+%.5f+%.5f' % (m.llcrnrlon, m.llcrnrlat, m.urcrnrlon, m.urcrnrlat)
    return os.path.join(mapdir, 'basemap.%s.%s.pyk' % (srs, szone))


def create_map(lon_min=-180., lon_max=180., lat_min=-90., lat_max=90., projection='cyl', resolution='auto', 
    lon_center=None, lat_center=None, lat_ts=None, zoom=None, ax=None, 
    overlay=False, fullscreen=False, nocache=False, cache_dir=None, **kwargs):
    """Generic creation of a :class:`Basemap` instance with caching
    
    .. todo:: Merge :func:`get_map` with :func:`create_map`
    """
    kwmap = kwfilter(kwargs, 'basemap', defaults={'area_thresh':0.})
    kwmap.update(kwfilter(kwargs, 'map_'))
    
    # Map arguments
    kwargs.setdefault('area_thresh', 0.) 
    kwargs.setdefault('rsphere', rshpere_wgs84) # WGS-84
    if kwargs['rsphere'] in [None, False, True]: del kwargs['rsphere']
    projection = kwargs.pop('proj', projection)
    if lon_center is None: lon_center = .5*(lon_min+lon_max)
    if lat_center is None: lat_center = .5*(lat_min+lat_max)
    if lat_ts is None: lat_ts = lat_center
    if lon_max-lon_min<1.e-5:
        lon_min = lon_center-1
        lon_max = lon_center+1
    if lat_max-lat_min<1.e-5:
        lat_min = N.clip(lat_center-1, 0, 90)
        lat_max = N.clip(lat_center+1, 0, 90)
    if isinstance(zoom, (int, float)):
        lon_min, lat_min, lon_max, lat_max = zoombox([lon_min, lat_min, lon_max, lat_max], zoom)
    
    # Special overlay case
    if overlay:
        projection = 'merc'
        resolution = None
        lat_center = 0
        lon_center = 0
    elif projection == None:
        projection = 'cyl'
                    
    # Guess resolution
    res = kwargs.pop('res', resolution)
    if res is True:
        res = 'auto'
    elif res is False:
        res = None
    elif isinstance(res, int):
        if res < 0:
            res= 'auto'
        else:
            res = gshhs_reslist[4-res]
    if res == 'auto':
        res = gshhs_autores(lon_min, lon_max, lat_min, lat_max)
    if res in gshhs_reslist:
        kwargs.setdefault('resolution', res)
    else:
        kwargs['resolution'] = None
        
    # Basemap args
    if isinstance(projection, str) and projection.lower() == 'rgf93' :
        # RGF93
        kwargs.update(lon_0=3, lat_0=46.5, lat_1=44, lat_2=49, rsphere=rshpere_wgs84, projection='lcc')
    else:
        # standard
        kwargs.setdefault('lon_0', lon_center)
        kwargs.setdefault('lat_0', N.clip(lat_center, -90, 90))
        kwargs.setdefault('lat_1', kwargs['lat_0'])
        kwargs.setdefault('lat_2', kwargs['lat_1'])
        kwargs.setdefault('lat_ts', N.clip(lat_center, -90, 90))
        kwargs.setdefault('projection', projection)
    kwargs.setdefault('llcrnrlon', lon_min)
    kwargs.setdefault('urcrnrlon', lon_max)
    kwargs.setdefault('llcrnrlat', N.clip(lat_min, -90, 90))
    kwargs.setdefault('urcrnrlat', N.clip(lat_max, -90, 90))
    
    # Check the cache
    kwcache = kwargs.copy()
    if cache_dir is not None:
        kwcache['mapdir'] = cache_dir
    if not nocache:
        mymap = cached_map(**kwcache)
    else:
        mymap = None
        
    # Create the map object
    if mymap is None:
        mymap = Basemap(ax=ax, **kwargs)
        
        # Cache it?
        if int(nocache)<=1: 
            if cache_dir is not None:
                kwcache = {'mapdir':cache_dir}
            else:
                kwcache = {}
            cache_map(mymap, **kwcache)
    elif ax is not None:
        mymap.ax = ax
    mymap.res = res
    return mymap


def get_map(gg=None, proj=None, res=None, auto=False, **kwargs):
    """Get a suitable map for converting degrees to meters
    
    :Params:
    
        - **gg**: cdms grid or variable, or (xx,yy).
        - *res*: Resolution [default: None]
        - *proj*: Projection [default: None->'merc']
        - *auto*: If True, get geo specs according to grid. If False, whole earth. If None, auto = res is None [default: False]
    
    .. todo:: Merge with :func:`create_map`
    """
    from vacumm.misc.grid import misc
    if proj is None:
        proj = 'merc'
    if auto is None:
        auto = res is not None
    if gg is None: auto = False
    kwmap = dict(resolution=res, projection=proj)
    if auto:
        xx, yy = misc.get_xy(gg, proj=False)
        lat_center = yy.mean()
        lon_center = xx.mean()
        kwmap.update(
            llcrnrlon = xx.min(),
            urcrnrlon = xx.max(),
            llcrnrlat = yy.min(),
            urcrnrlat = yy.max())
    else:
        lat_center = 0.
        lon_center = 0.
    return Basemap(lat_ts=lat_center, lat_0=lat_center, lon_0=lon_center,  **kwmap)
        
class GSHHS_BM(Shapes):
    """Shoreline from USGS using Basemap
    
    Initialized with a valid Basemap instance with resolution not equal to None, or thanks to arguments passed to :func:`vacumm.misc.plot.map()`
        
    - *m*: Basemap instance [default: None]
    
    """
    def __init__(self, input=None, clip=None, sort=True, reverse=True, proj=False, **kwargs):
        # Clipping argument
        if clip is not None:
            clip = polygons([clip])[0]
            
        from_map = not isinstance(input, Shapes)
        if not from_map:
            # Already a Shapes instance
            self._m = input._m
            self._proj = input._proj
            polys = input._shapes
        else:
            # Get the map
            if isinstance(input, Basemap):
                assert input.resolution is not None, 'Your map needs its resolution to be set'
                m = input
            else:
                if isinstance(input, str):
                    kwargs['res'] = input
                elif isinstance(input, dict):
                    kwargs.update(input)
                    
                # Map extension from clip bounds
                if clip is not None:
                    bb = clip.boundary
                    kwargs.setdefault('lon_min', bb[:, 0].min())
                    kwargs.setdefault('lon_max', bb[:, 0].max())
                    kwargs.setdefault('lat_min', bb[:, 1].min())
                    kwargs.setdefault('lat_max', bb[:, 1].max())
                    
                # Default resolution is 'i' if nothing to estimate it
                if not kwargs.has_key('res') and not kwargs.has_key('resolution') and \
                    (   (not kwargs.has_key('lon') and 
                            (not kwargs.has_key('lon_min') or not kwargs.has_key('lon_max'))) or 
                        (not kwargs.has_key('lat') and 
                            (not kwargs.has_key('lat_min') or not kwargs.has_key('lat_max')))):
                    kwargs['res'] = 'i'
                    
                # Check lats
                if kwargs.has_key('lat_min'): kwargs['lat_min'] = max(kwargs['lat_min'], -90)
                if kwargs.has_key('lat_max'): kwargs['lat_max'] = min(kwargs['lat_max'], 90)
                    
                # Build the map
                m = create_map(**kwargs)
            polys = m.coastpolygons
            self._m = m
            self._proj = m.projtran
            
        # Convert to GEOS polygons and clip
        self._shapes = []
        for i, pp in enumerate(polys):

            # Get the polygon
            if not from_map:
                poly = pp
            else:
                if m.coastpolygontypes[i] in [2,4]: continue # Skip lakes
                if callable(self._proj):
                    pp = self._proj(pp[0], pp[1])
                poly = Polygon(N.asarray(pp,'float64').transpose())
            
            # Clip it
            if clip is not None:
                if poly.intersects(clip):
                    self._shapes.extend(poly.intersection(clip))
            else:
                self._shapes.append(poly)
        self._info = []
        self._type = 2
        self._shaper = Polygon
        if self._shapes:
            xy = N.concatenate([s.boundary for s in self._shapes])
            self.xmin = xy[:, 0].min()
            self.xmax = xy[:, 0].max()
            self.ymin = xy[:, 1].min()
            self.ymax = xy[:, 1].max()
            del xy
        else:
            xmin = N.inf
            xmax = -N.inf
            ymin = N.inf
            ymax = -N.inf
        
        # Sort polygons?
        if sort:
            self.sort(reverse=reverse)
            
def merc(lon=None, lat=None, **kwargs):
    """Mercator map
    
    - Extra keywords are passed to :class:`mpl_toolkits.basemap.Basemap`
    - *lon*: Longitudes to define ``llcrnrlon`` and ``urcrnrlon``
    - *lat*: Latitudes to define  ``lat_ts``, ``llcrnrlat`` and ``urcrnrlat``
    """
    kwargs.setdefault('resolution', None)
    if lon is not None:
        lon = N.asarray(lon)
        kwargs.setdefault('llcrnrlon', lon.min())
        kwargs.setdefault('urcrnrlon', lon.max())
    if lat is not None:
        lat = N.asarray(lat)
        kwargs.setdefault('llcrnrlat', lat.min())
        kwargs.setdefault('urcrnrlat', lat.max())
        lat_ts = N.median(lat)
    else:
        lat_ts = 0.
    kwargs.setdefault('lat_ts',lat_ts)
    return Basemap(projection='merc', **kwargs)
    
#proj = merc()

def get_proj(gg=None, **kwargs):
    """Setup a default projection using x,y coordinates and 
    :class:`~mpl_toolkits.basemap.proj.Proj`
    
    Projection is set by default to Mercator and cover the coordinates.
    
    :Params:
    
        - **gg**, optional: Grid or coordinates (see :func:`~vacumm.misc.grid.misc.get_xy`).
          If not provided, lon bounds are set to (-180,180) and lat bounds to (-90,90).
        - Other keywords are passed to :class:`~mpl_toolkits.basemap.proj.Proj`
        
    :Examples:
    
        >>> proj = get_proj(sst.getGrid())
        >>> x, y = proj(lon, lat)
        
        >>> proj = get_proj((lon,lat))
        >>> xx, yy = N.meshgrid(lon,lat)
        >>> xx,yy = proj(xx,yy)
    """
    if gg is not None:
        x,y = get_xy(gg, num=True)
        xmin, ymin, xmax, ymax = x.min(), y.min(), x.max(), y.max()
    else:
        xmin, ymin, xmax, ymax = -180, -90, 180, 90 
    projparams = dict(R=rsphere_mean, units='m', proj='merc', lat_ts = N.median(y))
    projparams.update(kwargs)
    return Proj(projparams, xmin, ymin, xmax, ymax)
    

from masking import polygons
