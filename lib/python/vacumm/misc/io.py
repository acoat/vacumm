# -*- coding: utf8 -*-
"""In/Output tools"""
# Copyright or © or Copr. Actimar/IFREMER (2010-2016)
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
import copy
import logging.handlers
import os, gc, glob, logging, re, sys
from collections import OrderedDict
from traceback import format_exc
from warnings import warn
import warnings

import numpy as N, MV2, cdms2, cdtime
import pylab as P, operator
from _geoslib import Point, LineString, Polygon
from matplotlib.collections import LineCollection, PolyCollection
from mpl_toolkits.basemap import Basemap

from vacumm import VACUMMError
from .misc import split_selector, kwfilter, squeeze_variable, is_iterable
from .poly import create_polygon, clip_shape
from .atime import (has_time_pattern, time_selector, is_interval, is_time,
    strptime, comptime, are_same_units, ch_units, now, datetime)

from . import axes as vca
from . import color as vcc
#from . import grid as vcg

__all__ = ['list_forecast_files', 'NcIterBestEstimate', 'NcIterBestEstimateError', 'NcFileObj',
    'ncfind_var', 'ncfind_axis', 'ncfind_obj', 'ncget_var', 'ncread_var', 'ncread_files', 'ncread_best_estimate',
    'ncget_grid', 'ncget_time','ncget_lon','ncget_lat','ncget_level', 'ncmatch_obj',
    'ncget_axis', 'netcdf3', 'netcdf4', 'ncread_axis', 'ncread_obj', 'ncget_fgrid',
    'grib_read_files', 'nccache_get_time', 'grib2nc', 'grib_get_names',
    'write_snx', 'ColoredFormatter', 'Logger',
    'TermColors', 'read_shapefile',
    ]

MA = N.ma
MV = MV2


class ColPrinter(object):
    """
    Class to print formatted columns with header and frame

    :Params:

        - **columns**: A list of column descriptions like [['Year',6,'%i'],...]
          where the fist element is the title
          of the column, the second is the width of the
          column, and the last is the format of data.
        - **file**, optional: Output to file instead of stdout.
        - **align**, optional: Text alignment of titles in header, in ('left','right','center').
        - **left,right,top,bottom**, optional: String to draw part of a frame
        - **frame**: Shortcut to left=right='|',  and top=bottom='-'
        - **headsep**, optional: Header separator. If empty or None, not printed.
        - **colsep**, optional: Column separator.
        - **print_header**, optional: Printer once object created.

    .. Note::

        Obviously, you must use monospaced fonts

    :Example:

        >>> p = ColPrinter([['Year',6,'%i'],['Value',7,'%4.1f']], headsep='=',align='center',frame=True)
        ------------------
        |  Year   Value  |
        |================|
        >>> p(2000,25.9)
        | 2000   25.9    |
        >>> p(2001,23.7)
        | 2001   23.7    |
        >>> p.close()
        ------------------
    """
    def __init__(self,columns,headsep=True,align='left',
        left=None,right=None,top=None,bottom=None,frame=None,colsep=' ',
        print_header=True,file=None):
        # Inputs
        if not isinstance(columns,(list,tuple)):
            raise TypeError, 'Input must be a list or tuple of 3-element lists'
        elif len(columns) == 3 and type(columns[0]) is type('s')  and \
            type(columns[1]) is type(1) and type(columns[2]) is type('s'):
            columns = [columns,]
        if align not in ['left','right','center']:
            align = 'left'
        if frame is True:
            left = right = '|'
            top = bottom = '-'
        for bb in 'left','right','top','bottom':
            val = locals()[bb]
            if val is not None:
                setattr(self, '_'+bb, val)
            else:
                setattr(self, '_'+bb, '')
        self._colsep = str(colsep)
        if self._colsep == '':
            self._colsep = ' '
        if self._colsep != ' ':
            self._colsep = ' '+self._colsep+' '
        if headsep in ['',None,False]:
            self._headsep = None
        elif headsep is True:
            self._headsep = '-'
        else:
            self._headsep = str(headsep)

         # Loop on columns
        headers = []
        self._width = []
        self._fmt = []
        self._ncol = len(columns)
        for col in columns:
            if not isinstance(col,(list,tuple)) or \
              len(col) != 3 or type(col[0]) is not type('s') or type(col[1]) != type(1) or \
              type(col[2]) is not type('s') or col[2].find('%') < 0:
                raise TypeError, 'This description of column must contain the column title (string), the column width (int) and the string format for data (string): %s' % col
            width = col[1]
            if width < len(col[0]):
                width = len(col[0])
            self._width.append(width)
            if align == 'left':
                headers.append(col[0].ljust(width))
            elif align == 'right':
                headers.append(col[0].rjust(width))
            else:
                headers.append(col[0].center(width))
            self._fmt.append(col[2])

        # File case
        if file is not None:
            self._fid = open(file,'w')
        else:
            self._fid = None

        # Print header
        self._header = self._colsep.join(headers)
        if print_header:
            self.header()
        self._bottom__printed = False

    def __print(self,line):
        if isinstance(self._fid,file):
            self._fid.write(line+'\n')
        else:
            print line

    def close(self):
        """Print bottom and close the file (if file mode) """
        self.bottom()
        if isinstance(self._fid,file) and not self._fid.closed:
            self._fid.close()

    def __left(self):
        if len(self._left):
            return self._left+' '
        return ''

    def __right(self):
        if len(self._right):
            return ' '+self._right
        return ''

    def top(self):
        """ Print top frame """
        if len(self._top):
            n = len(self._header)+len(self.__left())+len(self.__right())
            self.__print((self._top * n)[:n])

    def header(self):
        """ Print header (stop + header text + header separator) """
        self.top()
        self.__print(self.__left()+self._header+self.__right())
        self.headsep()

    def headsep(self):
        """ Print header separator line """
        if self._headsep is not None:
            n = len(self._header) + \
              len(self.__left()) - len(self._left) + \
              len(self.__right()) - len(self._right)
            self.__print(self._left+(self._headsep * n)[:n]+self._right)

    def bottom(self):
        """ Print bottom frame """
        if self._bottom__printed: return
        if len(self._bottom):
            n = len(self._header)+len(self.__left())+len(self.__right())
            self.__print((self._bottom * n)[:n])
        self._bottom__printed = True


    def __call__(self,*data):
        """Print data in columns

        Arguments refer to the data.
        The number of arguments must be the same as the number of columns.
        """
        if len(data) != self._ncol:
            raise TypeError, 'You must give a number of data equal to the number of columns (%i): %i' \
            % (self._ncol,len(data))

        dds = []
        for i,dd in enumerate(data):
            dds.append((self._fmt[i] % dd).ljust(self._width[i]))
        self.__print(self.__left()+self._colsep.join(dds)+self.__right())

col_printer = ColPrinter # compat



def list_forecast_files(filepattern, time=None, check=True,
    nopat=False, patfreq=None, patfmtfunc=None, patmargin=None, verbose=False, sort=True):
    """Get a list of forecast files according to a file pattern

    :Params:

        - **filepattern**: It can be either:

            - a global matching pattern (``"file??.nc"``),
            - a date pattern (``"file%Y-%m-%d.nc"``),
            - an url (``"http://site.net/file.nc"``),
            - a list of files.

        - **time**: A time selector (``('2000', '2001', 'co')``).

          .. warning::
              This argument is *mandatory* if ``filepattern`` is a date pattern,
              and *not used* if ``filepattern`` is of another type.

        - **check**, optional: Check if local files exist.
        - **nopat**, optional: Never consider that input patterns have date patterns.
        - **patfreq**, optional: Frequency of files to generate file names for each date
           when ``filepattern`` is a date pattern.
        - **patfmtfunc**, optional: Function to use in place of
           :func:`~vacumm.misc.atime.strftime` to generate file names.
           It must take as arguments a date pattern and a CDAT component time.
        - **sort**, optional: If True, files are sorted alphabetically after being listed;
          if a callable function, they are sorted using this function (``files=sort(files)``).

          .. warning:: Files are sorted alphabetically by default!

    :Examples:

        >>> 'Prefered way'
        >>> list_forecast_files('mrsPRVMR_r0_%Y-%m-%d_00.nc', ('2010-08-06', '2010-08-15'))
        >>> list_forecast_files('http://www.ifremer.fr/data/mrsPRVMR_r0_%Y-%m-%d_00.nc', ('2010-08-06', '2010-08-15'))
        >>> list_forecast_files('mrsPRVMR_r0_%Y-%m-%d_*.nc', ('2010-08-06', '2010-08-15'))

        >>> 'Possible way'
        >>> list_forecast_files('mrsPRVMR_r0_2010-05-??_00.nc')
        >>> list_forecast_files(['mrsPRVMR_r0_2010-05-??_00.nc', 'mrsPRVMR_r0_2010-05-??_60.nc'])

        >>> 'Just ot filter in existing files'
        >>> list_forecast_files(['mrsPRVMR_r0_2010-05-06_00.nc', 'mrsPRVMR_r0_2010-05-07_00.nc'])

        >>> 'Simple conversion to list'
        >>> list_forecast_files('http://www.ifremer.fr/data/mrsPRVMR_r0_2010-05-06_00.nc')
    """

    sfp = str(filepattern)
    if len(sfp)>300: sfp = sfp[:300]+'...'
    if verbose:
        print 'Guessing file list using:'
        print '   filepattern: %s'%sfp
        print '   time selector: %s'%(time, )

    # A list of file
    if isinstance(filepattern, list):
        files = []
        for filepat in filepattern:
            files.extend(list_forecast_files(filepat, time=time, check=check,
                patfreq=patfreq, patfmtfunc=patfmtfunc, patmargin=patmargin,
                verbose=False, nopat=nopat))


    # Date pattern
    elif not nopat and has_time_pattern(filepattern):

        from atime import pat2freq,IterDates, strftime, is_interval, pat2glob, time_selector
        if isinstance(time, cdms2.selectors.Selector):
            seltime = time_selector(time, noslice=True)
            if seltime.components():
                _, comps = split_selector(seltime) # FIXME: include positional components
                for i, comp in comps:
                    itv = comp.spec
                    if not is_interval(itv) and is_time(itv):
                        itv = (itv, itv, 'ccb')
                    if i==0:
                        time = itv
                    else:
                        time = itv_union(itv, time)
            else:
                time = None

        if not is_interval(time):
            if is_time(time):
                time = (time, time, 'ccb')
            else:
                raise ValueError('Your file pattern contains date pattern (like "%Y"), '
                    'so you must provide a valid absolute time interval such as (date1,date2,"co")'
                    ' or at least a valid single date')
        time = tuple(time)
        patfmtfunc = patfmtfunc if callable(patfmtfunc) else strftime

        # Guess the minimal frequency
        lmargin = 1
        if patfreq is None:
            patfreq = pat2freq(filepattern)
            if verbose: print 'Detected frequency for looping on possible dates: '+patfreq.upper()
        if not isinstance(patfreq, tuple):

            #  Reform
            patfreq = (1, patfreq)

            # Guess left margin when possible
            gfiles = glob.glob(pat2glob(filepattern))
            gfiles.sort()
            if gfiles<2:
                lmargin = 1
            elif not glob.has_magic(filepattern):
                date0 = date1 = None
                for i in xrange(len(gfiles)-1):
                    try:
                        date0 = strptime(gfiles[i], filepattern)
                        date1 = strptime(gfiles[i+1], filepattern)
                    except:
                        continue
                    if date0>=time[0] or date1<=time[1]: break
                if None not in [date0, date1]:
                    dt = datetime(date1)-datetime(date0)
                    if dt.seconds!=0:
                        lmargin = comptime('2000').add(dt.seconds, cdtime.Seconds).torel(
                            patfreq[1]+' since 2000').value
                    else:
                        lmargin = comptime('2000').add(dt.days, cdtime.Days).torel(
                            patfreq[1]+' since 2000').value
                else:
                    lmargin = 1
             #FIXME: make it work with date+glob patterns
            else:
                lmargin = patfreq[0]


#        # Add margin to time interval
#        if patmargin is None:
#
#            # Guess margin from a second time pattern (like %Y_%%Y.nc)
#            fp2 = patfmtfunc(filepattern, now())
#            if has_time_pattern(fp2):
#                for fn in glob(pat2glob(fp2):
#
#
#        elif not isinstance(patmargin, tuple):
#            patmargin = (1, patmargin)

        # Make a loop on dates
        itertime = (round_date(time[0], patfreq[1], 'floor'), time[1])
        itertime = add_margin(itertime, (lmargin-1, patfreq[1]), False)
        iterdates = IterDates(itertime, patfreq,
            closed = len(time)==3 and time[2][1]=='c' or True)
        files = []
        for date in iterdates:
            file = patfmtfunc(filepattern, date)
            if '://' in file:
                files.append(file)
            elif check or glob.has_magic(file):
                files.extend(glob.glob(file))
            else:
                files.append(file)

    # Simple remote file or file object
    elif isinstance(filepattern, cdms2.dataset.CdmsFile) or '://' in filepattern:

        files = [filepattern]

    # Glob pattern
    else:
        if check or glob.has_magic(filepattern):
            files = glob.glob(filepattern)
        else:
            files = [filepattern]

    # Unique
    files = list(set(files))

    # Count
    if verbose:
        if not files:
            print 'No file found with this file pattern "%s" and time interval %s'%(filepattern, time)
        else:
            print 'Found %i files'%len(files)

    # Sort files
    if sort is True:
        sort = sorted
    if sort:
        if callable(sort):
            files = sort(files)
        else:
            files.sort()

    return files


def ncfind_var(f, name, ignorecase=True, regexp=False, **kwargs):
    '''
    Find a variable in a netcdf file using :func:`ncfind_obj`

    '''
    nfo = NcFileObj(f)
    f = nfo.f
    res =  ncfind_obj(f, name, ignorecase=ignorecase, regexp=regexp, ids=f.listvariables(), **kwargs)
    del nfo
    return res

def ncfind_axis(f, name, ignorecase=True, regexp=False, **kwargs):
    '''
    Find an axis in a netcdf file using :func:`ncfind_obj`

    '''
    nfo = NcFileObj(f)
    f = nfo.f
    res =  ncfind_obj(f, name, ignorecase=ignorecase, regexp=regexp,
        ids=f.listdimension(), **kwargs)
    del nfo
    return res

def ncfind_obj(f, name, ignorecase=True, regexp=False, ids=None,
        searchmode=None, **kwargs):
    '''
    Find a variable or an axis in netcdf file using a name, list of names
    or matching attributes such as standard_name, long_name and units.

    Objects are checked using :func:`ncmatch_obj`.
    It first checks the standard_name, then the names (ids), the axis, and finally
    the long_names and units.

    :Example:

        >>> f = cdms2.open('temp.nc')
        >>> ncfind_obj(f, 'temp')
        >>> ncfind_obj(f, ['temperature','temp'])
        >>> ncfind_obj(f, ('temperature','TEMP'), ignorecase=False)
        >>> ncfind_obj(f, dict(standard_name="sea_surface_temperature"))
        >>> ncfind_obj(f, 'lon')

    :Params:

        - **f**: A cdms2.dataset.CdmsFile.
        - **name**: A string or list of string to look for,
          or a dictionary with keys "name", "standard_name", "long_name", 'units' and 'axis'.
        - **ignorecase**, optional: Ignore name case when searching variable.
        - **regexp**, optional: Interpret long_names and units as regular expressions
          that must be compiled.
        - **searchmode**, optional: Search order when ``name`` is a dictionary
          and not a OrderedDict. It defaults
          to ``None`` or ``'snlua'`` which means:
          *standard_name -> name -> long_name -> units -> axis* (first letters).
          If ``name`` is an OrderedDict, it simply acts as a filter to restrict search.

    :Return:

        The first matching object name, or None if not found.

    '''
    nfo = NcFileObj(f)
    f = nfo.f

    # Targets
    if ids is None:
        ids = f.listvariables()+f.listdimension()
    elif isinstance(ids, basestring):
        ids = [ids]

    # Searched terms
    withdict = isinstance(name, dict)
    standard_names = long_names = units = axis = None
    if withdict: # Using a dictionary

        # Names and standard_name
        names = name.get("name", name.get('names', None))
        standard_names = name.get("standard_name",  name.get('standard_names', None))

        # Axis
        axis = name.get("axis", None)
        if axis is not None:
            axis = axis.upper()

        # Long_name
        long_names = name.get("long_name", name.get("long_names", None))
        if long_names is not None:
            if not is_iterable(long_names):
                long_names = [long_names]
            if regexp: # Regular expression
                flags = re.I if ignorecase else 0
                long_names = [re.compile(ln, flags).search for ln in long_names]
#            elif ignorecase:
#                long_names = __builtins__['map'](str.lower, long_names)

        # Units
        units = name.get("units", None)
        if units is not None:
            if not is_iterable(units):
                units = [units]
            if regexp: # Regular expression
                flags = re.I if ignorecase else 0
                units = [re.compile(u, flags).search for u in units]
#            elif ignorecase:
#                units = __builtins__['map'](str.lower, units)

    else: # Using a list of names
        names = name if is_iterable(name) else [name]
#    if names is not None:
#        names = __builtins__['map'](str.strip, names)
#        if ignorecase:
#            names = __builtins__['map'](str.lower, names)

    # Search order
    all_keys = ['standard_names', 'names', 'long_names', 'units', 'axis']
    all_keys0 = [key[0] for key in all_keys]
    if searchmode is None:
        searchmode = 'snlua'
    if isinstance(name, OrderedDict):
        keys = [key for key in name.keys() if key in all_keys]
        keys = [key for key in keys if key[0] in searchmode]
    else:
        keys = []
        for key0 in searchmode:
            if key0 in all_keys0:
                keys.append(all_keys[all_keys0.index(key0)])

    # Loop on objects
    for key in keys:
        kwsearch = {key:locals()[key]}
        for name in ids:
            v = f[name]
            if ncmatch_obj(v, name=name, ignorecase=ignorecase, **kwsearch):
                break
        else:
            continue
        break

    else: # Not found
        name = None

    nfo.close()

    return name

def _isinlist_(name, checks, ignorecase):
    """checks is a list of either strings or callables"""
    # Nothing
    if not name or not checks:
        return False
    name = name.strip()
    if ignorecase:
        name = name.lower()

    # Callables
    names = []
    for check in checks:
        if callable(check) and check(name):
            return True
        names.append(check)

    # Strings
    names = map(str.strip, names)
    if ignorecase:
        names = map(str.lower, names)
    return name in names

def ncmatch_obj(obj, name=None, standard_names=None, names=None,
        long_names=None, units=None, axis=None, ignorecase=True, **kwargs):
    """Check if an MV2 object (typicaly from a netcdf file) matches names, standard_names, etc


    It first checks the standard_name, then the names (ids), the axis, and finally
    the long_names and units.

    :Params:

        - **obj**: A MV2 array.
        - **name**, optional: Name (id) of this array, wich defaults to the id attribute.
        - **standard_names**, optional: List of possible standard_names.
        - **names**, optional: List of possible names (ids).
        - **axis**, optional: Axis type, as one of 'x, 'y', 'z', 't'.
        - **long_names**, optional: List of possible long_names or callable expression
          (such as regular expression method).
        - **units**, optional: Same as ``long_names`` but for units.

    :Example:

        >>> ncmatch_obj(sst, standard_names='sea_surface_temperature', names=['sst'])
        >>> import re
        >>> ncmatch_obj(sst, long_names=re.compile('sea surface temp').match)
    """
    # Format
    search = OrderedDict()
    for key in ('standard_names', 'names', 'long_names', 'units', 'axis'):
        val = locals()[key]
        search[key] = val
        if val is None: continue
        if key=='axis':
            search[key] = val if not isinstance(key, list) else val[0]
            continue
        if not is_iterable(val): val = [val]
        search[key] = val

    # Check long_name and units
    for refs, val in [
            (search['standard_names'], getattr(obj, "standard_name", None)),
            (search['names'], name or getattr(obj, 'id', None)),
            (search['axis'], getattr(obj, "axis",  None)),
            (search['long_names'], getattr(obj, "long_name", None)),
            (search['units'], getattr(obj, "units", None))]:
        if refs is not None and val is not None:
            if _isinlist_(val, refs, ignorecase):
                return True

    return False


def ncget_var(f, *args, **kwargs):
    '''
    Get a variable object as returned by :meth:`cdms2.dataset.CdmsFile.getVariable`
    which is equivalent to ``f[varname]``.

    :Return: A cdms2.fvariable.FileVariable or None if not found.

    :See: :func:`ncfind_var()`
    '''
    nfo = NcFileObj(f)
    f = nfo.f
    oldvname = args[0]
    vname = ncfind_var(f, *args, **kwargs)
    if vname is None:
        raise IOError('Variable not found %s in file %s'%(oldvname, f.id))
    var =  f.getVariable(vname)
    del nfo
    return var


def ncread_obj(f, name, *args, **kwargs):
    """Read an arbitrary netcdf object (axis or variable)"""
    # Inits
    nfo = NcFileObj(f)
    f = nfo.f
    ignorecase = kwargs.get('ignorecase', True)
    ncname = ncfind_obj(f, name, ignorecase=ignorecase)
    if ncname is None:
        del nfo
        raise IOError('Object not found %s in file %s'%(name, f.id))
    if ncname in f.variables:
        obj = ncread_var(f, ncname, *args, **kwargs)
    else:
        obj = ncread_axis(f, ncname, *args, **kwargs)
    del nfo
    return obj

def ncread_axis(f, name, select=None, ignorecase=True, mode='raise'):
    """Read a 1D axis

    .. note:: Please use :func:`ncread_var` to read 2D axes.

    :Params:

        - **mode**, optional: if ``'raise'`` raises an :exc:`IOError`
          if not found, else returns ``None``.
    """
    # Inits
    nfo = NcFileObj(f)
    f = nfo.f
    ncname = ncfind_axis(f, name, ignorecase=ignorecase)
    if ncname is None:
        del nfo
        if mode=='raise':
            raise IOError('Axis not found %s in file %s'%(name, f.id))
        return
    axis = f.getAxis(ncname).clone()
    del nfo
    return axis


def ncread_var(f, vname, *args, **kwargs):
    """Read a variable in a netcdf file and some more

    In addition to a simple ``f(vname, *args, **kwargs)```:

        - ``vname`` can be a list of var names, and it takes the first
          one found, ignoring the case by default.
        - If a variable is on a grid that is stored as curvilinear
          but is rectangular in real, it convert its grid to a rectanguar grid

    If variabe is not found, it raises

    :Params:

        - **f**: File descriptor.
        - **vname**: Variable name(s) (see :func:`ncfind_var`).
        - **ignorecase**, optional: Case insensitive search for the name of variable.
        - Other arguments and keywords are passed to ``f``.
        - **atts**: Dictionary of attributes to apply.

        - **squeeze**, optional: A single argument (or a list of them) interpreted
          as a squeeze specification passed to :func:`~vacumm.misc.misc.squeeze_variable`,
          to squeeze out singleton axes.
        - **torect**, optional: If True, try to convert output grid to rectanguar
          using :func:`~vacumm.misc.grid.misc.curv2rect`.
        - **mode**, optional: if ``'raise'`` raises an :exc:`IOError`
          if not found, else returns ``None``.

    :Example:

        >>> var = ncread_var(f, ['u', 'u2'], lon=(45, 47), atts={'id':'U'})

    """
    # Inits
    nfo = NcFileObj(f)
    f = nfo.f
    ignorecase = kwargs.pop('ignorecase', True)
    torect = kwargs.pop('torect', True)
    grid = kwargs.pop('grid', None)
    kwgrid = kwfilter(kwargs, 'grid')
    samp = kwargs.pop('samp', None)
    atts = kwargs.pop('atts', None)
    mode = kwargs.pop('mode', 'raise')
    searchmode = kwargs.pop('searchmode', None)
    squeeze = kwargs.pop('squeeze', False)
    if not isinstance(squeeze, list):
        squeeze = [squeeze]
    oldvname = vname

    # Find
    vname = ncfind_var(f, vname, ignorecase=ignorecase)
    if vname is None:
        del nfo
        if mode=='raise':
            raise VACUMMError('Variable not found %s in file %s'%(oldvname, f.id))
        return

    # Read
    var = f(vname, *args, **kwargs)

    # Extra stuff
    var = _process_var(var, torect, samp, grid, kwgrid, squeeze, atts)

    del nfo
    return var

def _process_var(var, torect, samp, grid, kwgrid, squeeze, atts):
    '''
    - **samp**, optional: Undersample rate as a list of the same size as
      the rank of the variable. Set values to 0, 1 for no undersampling.
    - **torect**, optional: If True, try to convert output grid to rectanguar
      using :func:`~vacumm.misc.grid.misc.curv2rect`.
    - **grid**, optional: A grid to regrid the variable on.
    - **grid_<keyword>**, optional: ``keyword`` is passed to
      :func:`~vacumm.misc.grid.regridding.regrid`.
    - **squeeze**, optional: Argument passed to :func:`squeeze_variable` to squeeze out singleton axes.
            - Extra kwargs are used to refine the **selector** initialized with ``select``.
    - **atts**: attributes dict (or list of attributes dict for each varname)
    '''
    # To rectangular grid?
    if torect:
        vacumm.misc.grid.curv2rect(var, mode="none")

    # Undersample
    if samp is not None:
        if len(samp)!=var.ndim:
            del nfo
            raise VACUMMError('Sampling keyword ("samp") must have'
                ' a size equal to the rank of the variable (%i)'%var.ndim)
        for i, ss in enumerate(samp):
            if samp==0 or samp==1:
                samp[i] = slice(None)
            elif not isinstance(ss, slice):
                samp[i] = slice(None, None, ss)
        var = var(*samp)

    # Regrid
    if grid is not None:
        from .regridding import regrid2d
        var = regrid2d(var, grid, **kwgrid)

    # Squeeze
    if squeeze:
        for ss in squeeze:
            if ss is False: break
            var = squeeze_variable(var, ss)
            if ss in [True, None]:
                break

    # Attributes
    if atts is not None:
        set_atts(var, atts)

    return var

def ncget_axis(f, checker, ids=None, ro=False, **kwargs):
    """Get an axis in a netcdf file by searching all axes and variables

    If ``checker`` is a list, dict or tuple, :func:`ncfind_axis`
    is called directly to search for the axis within the file.

    :Param:

        - **checker**: Can be either

            - A generic name such as 'x' or 'lon',
            - A function to check that an object is an axis.
              of appropriate type (such as :func:`~vacumm.misc.axes.islon`).
              This function must accept the 'ro' keyword ('readonly').
            - An argument to :func:`ncfind_axis`: list, dict, tuple.

        - **ids**, optional: A list of ids to focus search.

    :Return: The axis or None if not found
    """

    nfo = NcFileObj(f)
    f = nfo.f

    if isinstance(checker, basestring):
        checker = vca.get_checker(checker)
    elif isinstance(checker, (list, tuple, dict)):
        axid = ncfind_obj(f, checker, ids=ids, **kwargs)
        if axid is None: return
        axis = f[axid].clone()
        nfo.close()
        return axis

    # Targets
    dimids = f.listdimension()
    varids = f.listvariables()
    if ids is None:
        ids = varids+dimids
    elif isinstance(ids, basestring):
        ids = [ids]

    # Loop on targets
    axis = None
    for id in ids:
        if checker(f[id], ro=True):
            axis = f[id]
            break
#            if id in varids:
#                return f(id)
#            return f.getAxis(id)
        elif id in varids:
            for i, aid in enumerate(f[id].listdimnames()):
                if checker(f[aid], ro=True):
                    axis = f[id].getAxis(i)
                    break
            else:
                continue
            break
    if axis is None: return
    axis = axis.clone()
    del nfo
    checker(axis, ro=ro)
    return axis


def ncget_lon(f, ids=None, ro=False):
    """Get longitude axis of a netcdf file

    :Params:

        - **f**: Netcdf file name or object.
        - **ids**, optional: List of ids to help searching.
    """
    return ncget_axis(f, vca.islon, ids, ro=ro)

def ncget_lat(f, ids=None, ro=False):
    """Get latitude axis of a netcdf file

    :Params:

        - **f**: Netcdf file name or object.
        - **ids**, optional: List of ids to help searching.
    """
    return ncget_axis(f, vca.islat, ids, ro=ro)

def ncget_time(f, ids=None, ro=False):
    """Get time axis of a netcdf file

    :Params:

        - **f**: Netcdf file name or object.
        - **ids**, optional: List of ids to help searching.
    """
    return ncget_axis(f, vca.istime, ids, ro=ro)

def ncget_level(f, ids=None, ro=False):
    """Get level axis of a netcdf file

    :Params:

        - **f**: Netcdf file name or object.
        - **ids**, optional: List of ids to help searching.
    """
    return ncget_axis(f, vca.islevel, ids, ro=ro)

def ncget_grid(f, ids=None, torect=False):
    """Get a grid of a netcdf file

    :Params:

        - **f**: Netcdf file name or object.
        - **ids**, optional: List of ids to help searching.
    """
    nfo = NcFileObj(f)
    f = nfo.f

    if ids is None:
        ids = f.listvariables()
    elif isinstance(ids, basestring):
        ids = [ids]
    grid = None
    for id in ids:
        grid = f[id].getGrid()
        if grid is not None:
            grid = grid.clone()
            break
    del nfo
    if torect:
        grid = vacumm.misc.grid.curv2rect(grid, mode="none")
    return grid

def ncget_fgrid(f, gg):
    """Get the file grid that matches a transient grid or variable

    Matching is checked using ids of longitudes and latitudes.

    :Params:

        - **f**: file name or object.
        - **gg**: cdms2 grid or variable with a grid.

    :Return: A :class:`FileGrid` instance or ``None``
    """
    if f is None or gg is None: return
    if vacumm.misc.grid.isgrid(f): return f

    # From a variable
    if cdms2.isVariable(gg):
        gg = gg.getGrid()
        if gg is None: return

    # Current grid
    if isinstance(gg, tuple):
        lon, lat = gg
    else:
        lon = gg.getLongitude()
        lat = gg.getLatitude()
    if lon is None or lat is None: return
    lonid = getattr(lon, '_oldid', lon.id)
    latid = getattr(lat, '_oldid', lat.id)

    # Loop on file grids
    from vacumm.misc.io import NcFileObj
    nfo = NcFileObj(f)
    for fgrid in nfo.f.grids.values():
        flon = fgrid.getLongitude()
        flat = fgrid.getLatitude()
        flonid = getattr(flon, '_oldid', flon.id)
        flatid = getattr(flat, '_oldid', flat.id)
        if (lonid, latid)==(flonid, flatid):
            nfo.close()
            return fgrid
    nfo.close()


_nccache_time = {}
def nccache_get_time(f, timeid=None, ro=False):
    """Get a time axis from cache or netcdf file

    A time axis not in cache is read using :func:`ncget_time`,
    them stored in cache.

    :Params:

        - **f**: File object or name.
        - **timeid**, optional: Single or list of time ids for :func:`ncget_time`.

    Example:

        >>> taxis = nccache_get_time('myfile.nc', ['time','time_counter'])
    """
    # Check cache
    # - file name
    fname = f if isinstance(f, basestring) else f.id
    fname = os.path.realpath(fname)
    # - from cache
    if fname in _nccache_time:
        return _nccache_time[fname]

    # Read it
    taxis = ncget_time(f, ids=timeid, ro=ro)
    _nccache_time[fname] = taxis
    return taxis


class NcIterBestEstimate(object):
    """Iterator on netcdf forecast files

    This class is useful for reading the best estimate of netcdf forcast files.

    :Params:

        - **files**: A list of netcdf files.
        - **toffset**, optional: An integer or tuple of (<num>, '<units>')
          to skip the first time steps of each files.
        - **timeid**, optional: Time id. If ``None``, it is guessed
          using :meth:`guess_timeid`.
        - **tslices**, optional: A list of time slices
          (typically taken from a previous loop on file),
          to prevent guessing them.
        - **keepopen**, optional: Keep all file descriptor open,
          else close those who can be closed once no longer used.
        - **autoclose**: Deprecated.

    :Iterator: At each iteration, it returns ``f,tslice``

        - ``f``: the file descriptor (may be closed),
        - ``tslice``: the time slice

            - A :class:`slice` instance.
            - ``None`` if not time is found (thus no slice to perform).
            - ``False``: if nothing to read at all.

    :Example:

    >>> for f, tslice in NcIterBestEstimate(ncfiles, toffset=(1,'day')):
    ...     if tslice is False or time is None: continue
    ...     var = f(time=tslice)
    """
    def __init__(self, files, time=None, toffset=None, timeid=None, tslices=None, keepopen=False, autoclose=True, id=None):
        self.i = 0
        if isinstance(files, basestring): files = [files]
        self.nfiles = len(files)
        self.files = files
        self.nfonext = None
        self.seltime = time #[time] if isinstance(time,list) else time
        self.tslices = [] if tslices is None else tslices
        if toffset is None: toffset = 0
        self.toffset = toffset
        self.timeid = timeid
        self.autoclose = autoclose
        self.keepopen = keepopen
        from atime import add
        self.add = add
        if id is None:
            id = str(self.toffset)+str(self.seltime)+str(files)
            try:
                import md5
                id = md5.md5(self.id).digest()
            except:
                pass
        self.id = id

    def __iter__(self):
        return self

    def next(self, verbose=False):

        # Last iteration
        if self.i == self.nfiles:
            self.close()
            raise StopIteration

        # Check cache of time slices
        if len(self.tslices)>self.i:
            self.nfo = NcFileObj(self.files[self.i])
            f = self.nfo.f
            tslice = self.tslices[self.i]
            self.i += 1
            return f, tslice

        # Open current file
        if self.nfonext is not None: # from next one
            f = self.nfonext.f
            if not self.keepopen: self.nfo.close()
            self.nfo = self.nfonext
            self.nfonext = None
        else: # first time used
            self.nfo = NcFileObj(self.files[self.i])
            f = self.nfo.f

        ## Check file cache
        if not hasattr(f, '_vacumm_nibe_tslices'):
            f._vacumm_nibe_tslices = {}
        #ftslices = f._vacumm_nibe_tslices
        #if self.id in ftslices:
            #print 'gotit from cache'
            #return f, ftslices[self.id]

        # Get time axis
        if hasattr(f, '_vacumm_timeid'):
            self.timeid = f._vacumm_timeid
#        elif self.timeid is None or self.timeid not in f.listdimension():
#            self.timeid = guess_timeid(f)
#        if self.timeid is None:
#            return f, None
#            raise IOError('No valid time axis found in netcdf file')
#        taxis = f.getAxis(self.timeid)
        taxis = nccache_get_time(f, timeid=self.timeid, ro=True)
        if taxis is None:
            return f, None
            raise IOError('No valid time axis found in netcdf file')
        self.timeid = taxis.id
        if verbose:
            print taxis

        # Get base time slice of current file
        ijk = tsel2slice(taxis, self.seltime, asind=True, nonone=True)
        #if isinstance(self.seltime, slice):
            #ij = self.seltime.indices(len(taxis))[:2]
        #else:
            #try: ij = taxis.mapInterval(self.seltime)
            #except:
                #ij = None
        if ijk is False:
            return self.empty() # nothing
        i, j, k = ijk

        # Offset
        ctimes = taxis.asComponentTime()
        if isinstance(self.toffset, tuple):
            subseltime = (self.add(ctimes[0], *self.toffset), ctimes[-1], 'cc')
            subtaxis = taxis.subAxis(*ijk)
            ijo = subtaxis.mapIntervalExt(subseltime)
            if ijo is None or ijo[2]==-1: return self.empty() # nothing
            i += ijo[0]
        else:
            i = max(i, self.toffset)
            if i>=j: return self.empty() # nothing
            subtaxis = None

        # Truncate to next file
        if self.i+1 != self.nfiles:

            # Start of slice
            if subtaxis is None:
                subtaxis = taxis.subAxis(*ijk)
                ct0 = subtaxis.subAxis(0, 1).asComponentTime()[0]
            else:
                ct0 = ctimes[i]

            # End of slice
            self.nfonext = NcFileObj(self.files[self.i+1])
            taxisnext = nccache_get_time(self.nfonext.f, timeid=self.timeid, ro=True)
            if isinstance(self.toffset, tuple):
                ct1 = taxisnext.subAxis(0, 1).asComponentTime()[0]
                ct1 = self.add(ct1, *self.toffset)
                bb = 'co'
            else:
                if self.toffset>=len(taxisnext): # Next file too short for offset
                    ct1 = ctimes[-1]
                    bb ='cc'
                else: # First step starting from offset
                    ct1 = taxisnext.subAxis(self.toffset, self.toffset+1).asComponentTime()[0]
                    bb = 'co'
            subseltime = (ct0, ct1, bb)
            ijo = subtaxis.mapIntervalExt(subseltime)
            if ijo is None or ijo[2]==-1: return self.empty() # nothing
            io, jo, ko = ijo
            j = min(j, i+jo)
        del ctimes

        # Finalize
        self.i += 1
        tslice = slice(i, j)
        self.tslices.append(tslice)
        f._vacumm_nibe_tslices[self.id] = tslice
        return f, tslice

    def empty(self):
        """Nothing to read from this file"""
        self.tslices.append(None)
        self.i += 1
        self.nfo.f._vacumm_nibe_tslices[self.id] = None
        return self.nfo.f, False

    def close(self):
        """Close file descriptors that can be closed"""
        if not self.keepopen:
            if self.nfonext:
                self.nfonext.close()
            if self.nfo:
                self.nfo.close()


class NcIterBestEstimateError(VACUMMError):
    pass


class NcFileObj(object):
    """Simple class to properly manage file object or name

    :Examples:

        >>> nfo = NcFileObj('myfile.nc')
        >>> nfo.f('sst')
        >>> nfo.close() # or del nfo: close file descriptor

        >>> f = cdms2.open(path)
        >>> nfo = NcFileObj(f)
        >>> nfo.f('sst')
        >>> del nfo # or nfo.close(): here has no effect (descriptor still open)
        >>> f.close()
        >>> nfo = NcFileObj(f)
        >>> nfo.close() # close file descriptor

    """
    def __init__(self, ncfile, mode='r'):
        if isinstance(ncfile, NcFileObj):
            self.type = ncfile.type
            self.f = ncfile.f
        elif isinstance(ncfile, basestring):
            self.type = 'path'
            self.f = cdms2.open(ncfile, mode)
        elif hasattr(ncfile, '_status_'):
            self.type = ncfile._status_
            if self.type == 'closed':
                self.f = cdms2.open(ncfile.id, mode)
            else:
                self.f = ncfile
        else:
            raise IOError('Unknown file type %s (not a file name or a netcdf file object)'%ncfile)
    def isclosed(self):
        return self.type == 'closed'
    def ispath(self):
        return self.type == 'path'
    def isopen(self):
        return self.type == 'open'
    def close(self):
        if self.type in ['closed', 'path'] and self.f._status_ == 'open':
            self.f.close()
    __del__ = close

def ncread_best_estimate(filepattern, varname, *args, **kwargs):
    """Read the best estimate of a variable through a set of netcdf forecast files

    .. warning:: This function is deprecated.
        Please use :func:`ncread_files` switching the first
        two argument.

    This is equivalent to::

        ncread_files(varname, filepattern, *args, **kwargs)
    """
    return ncread_files(varname, filepattern, *args, **kwargs)

def ncread_files(filepattern, varname, time=None, timeid=None, toffset=None, select=None,
    atts=None, samp=None, grid=None, verbose=False, ignorecase=True, torect=True,
    squeeze=False, searchmode=None, nibeid=None, sort=True, nopat=False, patfreq=None,
    patfmtfunc=None, check=True, **kwargs):
    """Read the best estimate of a variable through a set of netcdf files

    .. warning:: Files are listed using function :func:`list_forecast_files`.
        Please read its documentation before using current function.

    :Examples:

        >>> var = ncread_files("r0_2010-%m-%d_00.nc", 'xe',
            ('2010-08-10', '2010-08-15', 'cc'), samp=[2, 1, 3])
        >>> var = ncread_files("http://www.net/r0_2010-%m-%d_00.nc", 'xe',
            ('2010-08-10', '2010-08-15', 'cc'),
            timeid='TIME', toffset=(1, 'day'))
        >>> var = ncread_files("r0_2010-??-??_00.nc", 'xe',
            select=dict(lon=(-10,-5), z=slice(23,24)), grid=smallgrid)
        >>> xe, sst = ncread_files("myfiles*.nc", [('xe', 'sla'),('sst','temp'),'u'])

    :Params:

        - **varname**: Name of the netcdf variable to read.

            - If a simple name, it reads this variable.
            - If a list of names, it reads them all.
            - If a list of list of names, each variable is searched for
              using the sublist of names.

        - **filepattern**: File pattern. See :func:`list_forecast_files`
          for more information.
        - **time**, optional: Time selector. This keyword is *mandatory*
          if ``filepattern`` has date patterns.
        - **toffset**: Skip the first time steps. See :class:`NcIterBestEstimate`
          for more information.
        - **select**, optional: An additional selector for reading
          the variable. It can be a dictionary or a :class:`~cdms2.selectors.Selector`
          instance (see :func:`~vacumm.misc.misc.create_selector`).
        - **atts**: attributes dict (or list of attributes dict for each varname)
          (see :func:`ncread_var`.)
        - **samp**, optional: Undersample rate as a list of the same size as
          the rank of the variable. Set values to 0, 1 for no undersampling.
        - **grid**, optional: A grid to regrid the variable on.
        - **grid_<keyword>**, optional: ``keyword`` is passed to
          :func:`~vacumm.misc.grid.regridding.regrid`.
        - **timeid**, optional: Time id (otherwise it is guessed).
        - **ignorecase**, optional: Ignore variable name case (see :func:`ncfind_var`).
        - **torect**, optional: If True, try to convert output grid to rectanguar
          using :func:`~vacumm.misc.grid.misc.curv2rect` (see :func:`ncread_var`).
        - Extra kwargs are used to refine the **selector** initialized with ``select``.
        - **squeeze**, optional: Argument passed to :func:`ncread_var`
          to squeeze out singleton axes.
        - **searchmode**, optional: Search order (see :func:`ncfind_obj`).
        - **sort/nopat/patfreq/patfmtfunc/check**, optional: These arguments are passed to
          :func:`list_forecast_files`.

    :Raise: :class:`NcIterBestEstimateError` in case of error.
    """
    # Get the list of files
    ncfiles = list_forecast_files(filepattern, time, sort=sort, nopat=nopat,
        patfreq=patfreq, patfmtfunc=patfmtfunc, check=check)
    if len(ncfiles)==0:
        raise NcIterBestEstimateError('No valid file found with pattern: %s'%filepattern)
    single = not isinstance(varname, list)
    varnames = [varname] if single else varname
    if verbose:
        print 'Reading best estimate variable(s): ', ', '.join([str(v) for v in varnames]), '; time:', time
        print 'Using files:'
        print '\n'.join([getattr(fn, 'id', fn) for fn in ncfiles])

    # Some inits
    nvar = len(varnames)
    if isinstance(atts, dict):
        atts = [atts]
    atts = broadcast(atts, nvar)
    allvars = [[] for iv in xrange(nvar)]
    kwgrid = kwfilter(kwargs, 'grid')
    # - base selector
    selects = broadcast(select, nvar)
    selectors = [create_selector(s, **kwargs) for s in selects]
    # - iterator on files
    iterator = NcIterBestEstimate(ncfiles, time, timeid=timeid, toffset=toffset, id=nibeid)
    # - undepsampling
    if samp is not None:
        samp = [0 for s in samp if s==0 or not isinstance(s, int)]
        samp = [slice(None, None, s) for s in samp]
    # - output grid
    if grid is not None:
        from grid.regridding import regrid2d
    # - time
    time_units = None
    newgrid = None
    tvars = [False]*len(varnames) # vars with time?
    itaxes = {}

    # Loop on files
    for ifile, (f, tslice) in enumerate(iterator):

        # Refine selector specs with time slice
        kwseltime = {iterator.timeid:tslice} if iterator.timeid is not None and \
            isinstance(tslice, slice) and not tslice==slice(None) else {}
#        seltime = selector(**kwseltime)
        taxis = None

        # Loop on variables
        for iv, vn in enumerate(varnames):

            # Refine this selector
            seltime = selectors[iv](**kwseltime)

            # Find variable name
            oldvn = vn
            vn = ncfind_var(f, vn, ignorecase=ignorecase)
            if vn is None:
                if verbose: print 'Skipping file %s for %s variable not found'%(f.id, oldvn)
                continue

            # Check time
            if f[vn] is None:
                continue
            withtime = iterator.timeid is not None and iterator.timeid in f[vn].getAxisIds()
            if withtime:
                itaxes[iv] = f[vn].getOrder().find('t')
                tvars[iv] = True
                if not tslice:
                    if verbose: print 'Skipping file %s for %s variable because time slice not compatible'%(f.id, oldvn)
                    continue
                sel = seltime # with time
            else:
                sel = selectors[iv] # no time

            # Infos
            if verbose:
                print 'Processing file no', ifile, ' ', f, ', variable:', vn, ', time slice :', tslice
                if withtime:
                    if taxis is None: taxis = f[vn].getTime()
                    ctimes = taxis.asComponentTime()
                    print '  Available:', ctimes[0], ctimes[-1]
                    del ctimes

            # Read the variable
            if verbose:
                print '  Selecting:', sel
            try:
                var = ncread_var(f, vn, sel, ignorecase=True, torect=torect, squeeze=squeeze,
                                 grid=grid, samp=samp, searchmode=searchmode,
                                 atts=atts[iv] if atts is not None and iv<len(atts) else None)
                if verbose:
                    print '  Loaded:', var.shape
            except Exception, e:
                if verbose: print 'Error when reading. Skipping. Message: \n'+format_exc()#e.message
                continue


            # Fix time units (that may vary between files)
            if iterator.timeid is not None and withtime:
                this_time_units = f[iterator.timeid].units
                if time_units is None:
                    time_units = this_time_units
                elif not are_same_units(this_time_units, time_units):
                    try:
                        ch_units(var, time_units)
                    except:
                        continue

            # Update
            if withtime or ifile==0: # append first time or variables with time
                allvars[iv].append(var)
            if True not in tvars and ifile==1: # no time for all variables
                break

        gc.collect()

        # Read only one file if no variable with time
        if ifile==0 and True not in tvars:
            break

    iterator.close()

    # Concatenate
    from misc import MV2_concatenate
    for iv in xrange(nvar):

        # Check
        if len(allvars[iv])==0:
            raise VACUMMError('No valid data found using varname(s): %s, '
                'filepattern: %s, time: %s'%(varnames[iv], filepattern, time))

        # Reorder and merge
        allvars[iv] = MV2_concatenate(allvars[iv], axis=itaxes.get(iv, 0), copy=False)

    return allvars[0] if single else allvars



def grib_get_names(gribfile):
    '''
    Return a list of a grib file parameter unique names (using grib message's shortName).
    '''
    import pygrib
    names = []
    with pygrib.open(gribfile) as g:
        for i in xrange(g.messages):
            m = g.read(1)[0]
            if m.shortName not in names:
                names.append(m.shortName)
    return names


def grib_read_files(
    filepattern, varname, time=None, select=None,
    torect=None, samp=None, grid=None, squeeze=None, atts=None,
    verbose=False, **kwargs):
    """
    Read cdms2 variables through one or a set of grib files.

    :Examples:

        >>> vardict = grib_read_files("r0_2010-%m-%d_00.grb", 'u',
                ('2010-08-10', '2010-08-15', 'cc'), samp=[2, 1, 3])
        >>> vardict = grib_read_files("r0_2010-??-??_00.grb", dict(shortName:'u'),
                select=dict(lon=(-10.0,-5.0), lat=slice(100,200)), grid=smallgrid)
        >>> vardict = grib_read_files("myfiles*.grb", [dict(shortName=['u', 'u10']), dict(shortName=['v','v10'])])

    :Params:

        - **filepattern**: must be:
            - File pattern. See :func:`list_forecast_files` for more information.
            - One or more string(s) of the files(s) to be processed. string(s) may contain wildcard characters.
        - **varname**: Name of the grib variable(s) to read.
            - If a simple name, it reads this variable **using the grib message's shortName**.
            - If a list of names, it reads them all.
            If a name is a dict, then it is used as grib selector in which case
            the user should not specify selectors which may interfer with the select keyword
            (see :func:`~pygrib.open.select`).
        - **time**, optional: Time selector for files and data. This keyword is *mandatory*
          if ``filepattern`` has date patterns.

        - **select**, optional: An additional selector applied after data have been loaded.
          It can be a dictionary or a :class:`~cdms2.selectors.Selector`
          instance (see :func:`~vacumm.misc.misc.create_selector`).

        - **torect**, optional: If True, try to convert output grid to rectanguar
          using :func:`~vacumm.misc.grid.misc.curv2rect` (see :func:`ncread_var`).
        - **samp**, optional: Undersample rate as a list of the same size as
          the rank of the variable. Set values to 0, 1 for no undersampling.
        - **grid**, optional: A grid to regrid the variable on.
        - **grid_<keyword>**, optional: ``keyword`` is passed to
          :func:`~vacumm.misc.grid.regridding.regrid`.
        - **squeeze**, optional: Argument passed to :func:`ncread_var` to squeeze out singleton axes.
        - **atts**: attributes dict (or list of attributes dict for each varname)

        - *verbose*: function to be called for logging (sys.stderr if True,
            disabled with False)

    :Return:

        If varname is a list of names or dicts:
        - a dict of loaded variables as :class:`cdms2.tvariable.TransientVariable`
          this dict keys are are filled with the corresponding varname value if it is a string, or wiht
          the loaded message's shortName/name/parameterName.
        Else:
        - the loaded variable as :class:`cdms2.tvariable.TransientVariable`

    """
    import datetime, glob, numpy, os, sys, time as _time, traceback
    import cdms2, pygrib
    from axes import create_lat, create_lon
    from atime import create_time, datetime as adatetime
    from grid import create_grid, set_grid
    if not verbose:
        verbose = lambda s:s
    if verbose and not callable(verbose):
        verbose = lambda s: sys.stderr.write(('%s\n')%s)
    # List of variables
    single = not isinstance(varname, (list,tuple))
    varnames = [varname] if single else varname
    verbose(
        'grib_read_files:\n'
        '  filepattern: %s\n'
        '  time: %s\n'
        '  varname: %s'
    %(filepattern, time, '\n- '.join(['%r'%(v) for v in varnames])))
    # List of files
    if isinstance(filepattern, basestring):
        files = list_forecast_files(filepattern, time)
    else:
        if not isinstance(filepattern, (list, tuple)):
            filepattern = (filepattern,)
        files = tuple(f for l in map(lambda p: glob.glob(p), filepattern) for f in l)
    if len(files)==0:
        raise Exception('No valid file found with pattern %r and time %r'%(filepattern, time))
    verbose('number of matching files: %s'%(len(files)))
    #verbose('- %s'%('\n- '.join(files)))
    if time:
        time = map(datetime, time[:2])
    vardict = dict()
    # Load grib data
    for f in files:
        verbose('file: %s'%(f))
        with pygrib.open(f) as g:
            for n in varnames:
                kw = n if isinstance(n, dict) else dict(shortName=n)
                st = _time.time()
                ms = g.select(**kw)
                verbose('  select: %s message%s matching preselection %r (took %s)'%(
                    len(ms), 's' if len(ms)>1 else '', kw, datetime.timedelta(seconds=_time.time()-st)))
                for m in ms:
                    st = _time.time()
                    # use provided special datetime object if present
                    if m.validDate:
                        dt = m.validDate
                    # use validityDate exposed as YYYYMMDD and validityTime exposed as HHMM (or HMM or HH or H)
                    elif m.validityDate != None and m.validityTime != None:
                        dt = '%s%04d00'%(m.validityDate, m.validityTime) # pad validityTime and add 00 seconds
                    # or use dataDate & dataTime & forecastTime ??
                    else:
                        raise Exception('Don\'t know how to handle datetime for message:\n%r'%(m))
                    if isinstance(dt, basestring):
                        dt = datetime.datetime.strptime(dt, '%Y%m%d%H%M%S')
                    if time and (dt < time[0] or dt >= time[1]):
                        continue
                    if m.gridType == 'regular_ll':
                        latitudes,longitudes = m.distinctLatitudes, m.distinctLongitudes
                    else:
                        latitudes,longitudes = m.latlons()
                    kn = n
                    if isinstance(kn, dict):
                        kn = n.get('shortName', n.get('name', n.get('parameterName', None)))
                    if not kn: kn = m.shortName
                    if not kn in vardict: vardict[kn] = []
                    vardict[kn].append(dict(
                        datetime=dt,
                        latitudes=latitudes, longitudes=longitudes,
                        values=m.values
                    ))
                    verbose('    message name: %r, shortName: %r, datetime: %s, gridType: %r, latitude%s, longitude%s (took %s)'%(
                        m.name, m.shortName, dt, m.gridType, latitudes.shape, longitudes.shape, datetime.timedelta(seconds=_time.time()-st)))
                    del m
                del ms
    # Transform loaded data into cdms2 variable
    kwgrid = kwfilter(kwargs, 'grid')
    for n,p in vardict.iteritems():
        if not p:
            vardict[n] = None
            continue
        p = sorted(p, lambda a,b: cmp(a['datetime'], b['datetime']))
        time = create_time([pp['datetime'] for pp in p])
        lat = create_lat(p[0]['latitudes'])
        lon = create_lon(p[0]['longitudes'])
        var = cdms2.createVariable(
            [pp['values'] for pp in p],
            id='_'.join(n.split()), long_name=n,
        )
        var.setAxis(0, time)
        set_grid(var, vacumm.misc.grid.create_grid(lon, lat))
        vatts = atts=atts[iv] if atts is not None and iv<len(atts) else None
        if select:
            var = var(**select)
        var = _process_var(var, torect, samp, grid, kwgrid, squeeze, atts)
        vardict[n] = var
    # Return variable or dict of variables
    return vardict.values()[0] if (single and vardict) else vardict


def grib2nc(filepattern, varname):
    '''
    ***Currently for test purpose only***
    '''
    varlist = grib_read_files(filepattern, varname, verbose=True)
    if ncoutfile:
        print>>sys.stderr, 'Writing to netcdf file:', ncoutfile
        netcdf3()
        if os.path.exists(ncoutfile):
            print>>sys.stderr, 'File already exists:', ncoutfile
            sys.exit(1)
        f = cdms2.open(ncoutfile, 'w')
        try:
            for n,v in varlist.iteritems():
                if v is None:
                    print>>sys.stderr, '  %r not found'%(n)
                    continue
                print>>sys.stderr, '  %r (%r)'%(v.id, n)
                f.write(v)
        finally: f.close()

SHAPES_POINTS = SHAPES_POINT = 0
SHAPES_LINES = SHAPES_LINE = 1
SHAPES_POLYGONS = SHAPES_POLYS = SHAPES_POLY = SHAPES_POLYGON = 2
SHAPEFILE_POINTS = 1
SHAPEFILE_MULTIPOINTS = 8
SHAPEFILE_POLYLINES = 3
SHAPEFILE_POLYGONS = 5

def read_shapefile(self, input, proj=False, inverse=False, clip=True,
        shapetype=None, min_area=None, sort=True, reverse=True, samp=1,
        clip_proj=True, m=None, getextended=False):

    # Inits
    from_file = isinstance(input, str)
    if hasattr(m, 'map'): m = m.map
    default_proj = None if m is None else m

    if from_file:

        # From a shapefile
        if shapefile.endswith('.shp') and shapefile.endswith('.dbf'):
            shapefile = shapefile[:-4]
        for ext in ('shp', ):#, 'dbf':
            fname = '%s.%s'%(shapefile, ext)
            assert os.path.exists(fname), fname
        try:
            from mpl_toolkits.basemap.shapefile import Reader
            newreader = True
            shp = Reader(shapefile)
            shapefile_type = shp.shapeType
        except Exception, e:
            print>>sys.stderr, 'Cannot read %s:\n%s\nTrying with shapelib'%(shapefile, e)
            from shapelib import ShapeFile
            newreader = False
            shp = ShapeFile(shapefile)
            shapefile_type = shp.info()[1]
        prefix = shapefile
    #           dbf = dbflib.open(shapefile)
        if default_proj and (1, 1) == default_proj(1, 1):
            default_proj = None
    #    self._info = []

    elif isinstance(shapefile, (list, N.ndarray)): # From coordinates
        in_coords = shapefile
        shapefile_type = 5 if not len(in_coords) or in_coords[0].ndim==2 else 1
        self._info = []

    else:

        # From a Shapes (or super) instance
        in_coords = shapefile.get_data(proj=False)
        self._m = shapefile._m # overwrite m keyword
        default_proj = shapefile._proj
        shapefile_type = [SHAPEFILE_POINTS, SHAPEFILE_POLYLINES,
            SHAPEFILE_POLYGONS][input._type]
        self._info = input._info

    # Get coordinates
    if from_file:
        if newreader:
            nshapes = shp.numRecords
        else:
            nshapes = shp.info()[0]
    else:
        nshapes = 1
    coords = []
    if input_type in [SHAPEFILE_POINTS, SHAPEFILE_MULTIPOINTS]: # A Point or MultiPoint file
        if shapetype is not None and shapetype != SHAPES_POINTS:
            raise TypeError, 'Your shape type is not point'
        stype = SHAPES_POINTS

        # Loop on shape groups
        for iobj in xrange(nshapes):
            if from_file:
                if newreader:
                    all_points = shp.shape(iobj).shape.points
                else:
                    all_points = shp.read_object(iobj).vertices()
            else:
                all_points = in_coords
            coords.extend(all_points)

        # Merge coordinates
        xy = N.asarray(coords)

#               if from_file: self._info.append(dbf.read_record(iobj))

    elif input_type in [SHAPEFILE_POLYLINES, SHAPEFILE_POLYGONS]: # A Polyline or Polygon file

        # Shape type
        if shapetype is not None:
            if shapetype == SHAPES_POINTS:
                raise TypeError, 'Your shape type is point, not polyline or polygon'
            else:
                stype = shapetype
        else:
            if input_type==SHAPEFILE_POLYLINES:
                stype = SHAPES_LINES
            else:
                stype = SHAPES_POLYGONS

        # Loop on shape groups
        for iobj in xrange(nshapes):
            if from_file:
                if newreader:
                    obj = shp.shapeRecord(iobj).shape
                    all_points = obj.points
                    if len(all_points)==0: continue
                    nparts = len(obj.parts)
                    if nparts==1:
                        all_polys = [all_points]
                    else:
                        all_polys = []
                        for ip in xrange(nparts-1):
                            all_polys.append(all_points[obj.parts[ip]:obj.parts[ip+1]])#xxxxxxxx
                else:
                    all_polys = shp.read_object(iobj).vertices()
            else:
                all_polys = in_coords
            coords.extend(all_polys)

        # Merge coordinates
        xy = N.concatenate(coords)

    else:
        raise TypeError, 'Input shapefile must only contains 2D shapes'

    # Bounds
    if xy.shape[0]>0:
        xmin = xy[:, 0].min()
        xmax = xy[:, 0].max()
        ymin = xy[:, 1].min()
        ymax = xy[:, 1].max()
    else:
        xmin = N.inf
        xmax = -N.inf
        ymin = N.inf
        ymax = -N.inf
    del xy
    xpmin = N.inf
    xpmax = -N.inf
    ypmin = N.inf
    ypmax = -N.inf

    # Projection
    # - projection function
    if callable(proj): # direct
        proj = proj
    elif default_proj is not None and (proj is None or proj is True):
        proj = default_proj # from basemap
    elif isinstance(proj, basestring):
        gg = None if xmin>xmax else ([xmin, xmax], N.clip([ymin, ymax], -89.99, 89.99))
        kw = dict(proj=proj) if isinstance(proj, basestring) else {}
        from .basemap import get_proj
        proj = get_proj(gg, **kw)
    else:
        proj = False
    # - synchronisation of map instance
    m_projsync = None
    if callable(m): # same projection as of map?
        if proj is False:
            m_projsync = N.allclose((1, 1), m(1, 1))
        elif proj is m:
            m_projsync = True
        elif callable(proj) and proj is not m:
            m_projsync = N.allclose(proj(1, 1), m(1, 1))


    # Clipping zone with projected coordinates
    clip = create_polygon(clip, proj=clip_proj)

    # Convert to shapes
    shaper = [Point, LineString, Polygon][stype]
    all_shapes = []
    for coord in coords:

        # Numeric array
        coord = N.asarray(coord)

        # Under sampling
        if samp > 1 and coord.shape[0] > (2*samp+1):
            coord = coord[::samp]

        # Projection
        if proj:
            if coord[..., 1].max()<91 and coord[..., 1].min()>-91:
                coord[..., 1] = N.clip(coord[..., 1], -89.99, 89.99)
            coord = N.asarray(proj(coord[..., 0], coord[..., 1])).T

        # Convert to shape instance
        shape = shaper(coord)

        # Clip
        if clip:
            shapes = clip_shape(shape, clip)
        else:
            shapes = [shape]

        # Minimal area
        if min_area is not None and shaper is Polygon and min_area > 0.:
            shapes = filter(lambda sh: sh.area() >= min_area, shapes)

        # Store
        all_shapes.extend(shapes)


    # Final bounds
    if clip is not None or min_area:

        # Normal coordinates
        xy = self.get_xy(proj=False)
        xmin = min(xmin, xy[..., 0].min())
        xmax = max(xmax, xy[..., 0].max())
        ymin = min(ymin, xy[..., 1].min())
        ymax = max(ymax, xy[..., 1].max())
        del xy

    # Projected coordinates
    xyp = self.get_xy(proj=None)
    xpmin = min(xpmin, xyp[..., 0].min())
    xpmax = max(xpmax, xyp[..., 0].max())
    ypmin = min(ypmin, xyp[..., 1].min())
    ypmax = max(ypmax, xyp[..., 1].max())
    del xyp


    # Finalize
#    if from_file
    if not newreader:
        shp.close()
#           dbf.close()

    # Sort by area or cumulative length?
    if sort:
        sorted = sort_shapes(all_shapes, reverse=reverse)
    else:
        sorted = 0

    if not getextended:
        return all_shapes
    return dict(shapes=all_shapes, shaper=shaper, proj=proj, m=m, xmin=xmin,
        ymin=ymin, xmax=xmax, ymax=ymax, xpmin=xpmin, xpmax=xpmax, ypmin=ypmin,
        ypmax=ypmax, clip=clip, sorted=sorted, m_projsync=m_projsync)

class CachedRecord:
    """Abstract class for managing cached records

    ** It cannot be used by itself **

    The following class variables must be defined:

    - _cache_file: cache file name
    - _time_range: ('2000-12-01 12:00','2005-10-01','co') OR (1, 'day', 'cc')
    - _var_info: (('lon','Longitude', 'degrees east', None),('hs','Wave Height', 'm', (0., 20)),)
    - _station_info: (['Start Bay', '2007-12-25'],['Long Bay', '2004-05-18'])
    - _dt: (1800, cdtime.Seconds)
    - _time_units: 'seconds since 2000-01-01'

    The following methods must be defined:

    - _load_from_source_:
    """
    _verbose_level = 1
    _missing_value = 1.e20

    def __init__(self, time_range, **kwargs):

        for key, val in kwargs.items():
            key = '_'+key
            if hasattr(self, key):
                setattr(self, key, val)

        self._cache_file = self._cache_file %vars()
        self._update_mode = time_range in [None, 'update']
        if self._update_mode:
            time_range = 'all'
        self._time_range = self._get_time_range_(time_range)

        _var_names = [sn for sn, ln, un, vr in _var_info]
        _station_info = [[name, comptime(time_origin)] for name,  time_origin in _buoy_info]

        self._vars = {}
        self.check_cache()


    def _print_(self, text, level=2):
        if self._verbose_level >= level:
            if level == 1:
                text = '!WARNING! '+text
            text = '[%s] %s' %(self.buoy_type, text)
            print text

    def _warn_(self, text):
        self._print_(text, level=1)

    def show_variables(self):
        """Print available variables"""
        print 'Available variables:'.upper()
        for n,v in self._vars.items():
            print '%s: %s [%s]' % (n,v.long_name,v.units)

    def get(self,var_name, time_range=None):
        """Get a variable

        - **var_name**: Name of the variable

        Return: A 1D :mod:`MV2` variable

        See: :meth:`plot()`, :meth:`show_variables()`
        """
        # Time range
        time_range = self._get_time_range_(time_range)
        if time_range != self._time_range:
            self.load(time_range)
        assert var_name.lower() in self._vars.keys(),' Wrong name of variable ("%s"). Please use .show_variables() to list available variables'%var_name.lower()
        if time_range is None:
            args = []
        else:
            args = [time_range]
        return self._vars[var_name](*args)

    def __call__(self,*args,**kwargs):
        """Get a variable

        @see: :meth:`get()`
        """
        return self.get(*args,**kwargs)

    def plot(self,var_name,time_range=None,**kwargs):
        """Plot a variable

        - **var_name**: Name of the variable
        - *time*: Plot only within this time range (like ('2007-01-01','2007-02-01','co')
        - *show*: Show the figure [default: None]
        - All other keywords are passed to :func:`vacumm.misc.plot.curve()`

        Example:

        >>> myvar = mybuoy.plot('baro')

        See: :meth:`get()`, :meth:`show_variables()`
        """
#       # Time range
#       time_range = self._get_time_range_(time_range)
#       if time_range != self._time_range:
#           self.load(time_range)
#
        # Variable
        assert var_name.lower() in self._vars.keys(),' Wrong name of variable. Please use .show_variables() to list available variables'
        var = self._vars[var_name]
        if time_range is not None:
            var = var(time_range)

        # Keywords
        defaults = {
            'linestyle':'-',
            'marker':'.',
            'ms':4.,
            'mfc':'#00ffff',
            'title':'%s at %s buoy %s' % (var.long_name,self.buoy_type,self.buoy_id)
        }
        for att,val in defaults.items():
            kwargs.setdefault(att,val)

        # Plot
        curve(var,**kwargs)

    def save(self, file_name, mode='w', warn=True):

        if len(self._vars) == 0:
            self._warn_('No variables to save')
            return
        if file_name.endswith('.nc'):
            if not os.access(file_name, os.W_OK):
                if warn:
                    self._warn_('No write access to file:'+file_name)
                return
            f = cdms2.open(file_name, mode)
            for var in self._vars.values():
                f.write(var)
            for att in 'type', 'id', 'name':
                att = 'buoy_'+att
                setattr(f, att, getattr(self, att))
            if hasattr(self, '_url'):
                f.url = self._url
            f.close()
            if file_name == self._cache_file:
                self._print_('Cache updated')
            else:
                self._print_('Saved to '+file_name)


    def __init__(self, buoy, time_range, **kwargs):

        # Search for the buoy
        buoy_names = _channelcoast_list_(buoy)
        assert len(buoy_names), 'No buoy matching: '+buoy
        self.buoy_name = buoy_names[0]
        self.buoy_id = buoy_id = self.buoy_name.replace(' ', '')
        for buoy_name, time_origin in self._buoy_info:
            if buoy_name == self.buoy_name:
                self._time_origin = time_origin
                break
        self.buoy_type = self.__class__.__name__

        # Tuning
        for key, val in kwargs.items():
            key = '_'+key
            if hasattr(self, key):
                setattr(self, key, val)

        self._cache_file = self._cache_file %vars()
        self._update_mode = time_range in [None, 'update']
        if self._update_mode:
            time_range = 'all'
        self._time_range = self._get_time_range_(time_range)
        self._vars = {}
        self.check_cache()

    def get(self, var_name, time_range=None):
        time_range = self._get_time_range_(time_range)
        if time_range != self._time_range:
            self.load(time_range)
        return _Buoy_.get(self, var_name, time_range)

    def plot(self, var_name, time_range=None, **kwargs):
        time_range = self._get_time_range_(time_range)
        self.load(time_range)
        return _Buoy_.plot(self, var_name, time_range, **kwargs)

    def _get_time_range_(self, time_range):

        if isinstance(time_range, (list, tuple)): # Directly specified
            time_range = time_selector(*time_range)

        elif time_range in  ('full', 'all', True, False): # Everything possible
            time_range = (self._time_origin, now(True))

        else :#if hasattr(self, '_time_range'): # Default specified time range
            time_range = self._time_range

        if len(time_range) == 2: # Default bound indicators
            time_range += ('co', )

        if time_range[0] < self._time_origin: # Check not too old
            time_range = (self._time_origin, ) + time_range[1:]
        return time_range

    def _check_time_range_(self, time_range, time_axis, getbounds=False):
        """Check if a time_range is included in an time axis"""

        # Format time range
        time_range = self._get_time_range_(time_range)

        # Get right time axis
        if isinstance(time_axis, dict):
            if not len(time_axis):
                res = (False, False)
                if getbounds:
                    res += (None, None)
                return res
            time_axis = time_axis.values()[0]
        if cdms2.isVariable(time_axis):
            time_axis = time_axis.getTime()

        # Get axis range
        nt = len(time_axis)
        t0, t1 = time_axis.subAxis(0, nt, nt-1).asComponentTime()

        # Convert to closed bounds
        time_range = list(time_range)
        for ibound, isign in (0, 1), (1, -1):
            if time_range[2][ibound] == 'o':
                time_range[ibound] = time_range[ibound].add(isign*self._dt[0], self._dt[1])

        # Check bounds
        res = (time_range[0] >= t0 or self._update_mode, time_range[1] <= t1)
        if getbounds:
            res += (t0, t1)
        return res

    def load(self, time_range):
        """Check if time_range is included in in-memory variables, else, check cache and load from it"""
        time_range = self._get_time_range_(time_range)
        if self._vars == {} or \
            self._check_time_range_(time_range, self._vars) != (True, True):
            self.check_cache(time_range)

    def check_cache(self, time_range=None):
        """Update the cache"""

        buoy_id = self.buoy_id

        # Time bounds
        time_range = self._get_time_range_(time_range)
        self._print_('CHECK CACHE TIME RANGE '+str(time_range))
        t0_request, t1_request, bb = time_range

        # Update or create?
        if time_range is None:raise 'a'
        if not os.path.exists(self._cache_file%vars()):  # Create
            self._print_('CREATE')
            time_range = (time_range[0], time_range[1].add(-1, cdtime.Day), 'cc')
            self._vars = self._load_from_source_(time_range[:2]+('cc', ))
            self.save(self._cache_file%vars(), warn=False)

        else: # Update

            # Check cache time range
            f = cdms2.open(self._cache_file)
            cache_time = f.getAxis('time').clone()
            f.close()
            t0_good, t1_good, t0_cache, t1_cache = self._check_time_range_(time_range, cache_time, getbounds=True)

            # Check first date
            vars_new = {}
            if not t0_good:
                # First date of cache is too recent
                vars_before = self._load_from_source_((t0_request, t0_cache, time_range[2][0]+'o'))
                vars_current = self._load_from_cache_('all')
                if len(vars_before):
                    for vn in self._var_names:
                        vars_new[vn] = (vars_before[vn], vars_current[vn])
            # Check last date
            if not t1_good:
                vars_after = self._load_from_source_((t1_cache, t1_request, 'o'+time_range[2][1]))
                if len(vars_after):
                    if not len(vars_new):
                        # We just append to file
                        self._print_('APPEND TO FILE')
                        self._vars = vars_after
                        self.save(self._cache_file%vars(), 'a', warn=False)
                        self._print_(' loading from cache '+str(time_range))
                        self._load_from_cache_(time_range)
                        return
                    else:
                        # We append to var before saving
                        for vn in self._var_names:
                            vars_new[vn] += (vars_after[vn], )

            # Here we completely change the cache
            if len(vars_new):

                # Merge
                self._print_('MERGING')
                for ivar, (sn, ln, un, vr) in enumerate(self._var_info):
                    self._vars[sn] = MV.concatenate(vars_new[sn])
                    self._vars[sn].id = self._vars[sn].name = sn
                    self._vars[sn].long_name = ln
                    self._vars[sn].units = un

                # Save
                self.save(self._cache_file%vars(), warn=False)

            # Update in memory variables
            if self._check_time_range_(time_range, self._vars) != (True, True):
                self._load_from_cache_(time_range)

        gc.collect()

    def _load_from_cache_(self, time_range=None):
        """Load variables from cache"""
        time_range = self._get_time_range_(time_range)
        self._vars = {}
        buoy_id  = self.buoy_id
        f = cdms2.open(self._cache_file%vars())
        for var_name in f.variables.keys():
            self._vars[var_name] = f(var_name, time_range)
        f.close()
        return self._vars





def write_snx(objects, snxfile, type='auto', mode='w', z=99, xfmt='%g', yfmt='%g', zfmt='%g', close=True):
    """Write points, lines or polygons in a sinusX file"""
    # Check depth
    if isinstance(objects, (LineString, Polygon)):
        objects = [objects]
    elif isinstance(objects[0], Point) or \
        (not isinstance(objects[0], (LineString, Polygon)) and not hasattr(objects[0][0], '__len__')):
        objects = [objects]
        if type =='auto' or isinstance(objects[0][0], Point): type = 'point'

    # File
    splitfile = False
    if isinstance(snxfile, file):
        f = snxfile
    elif '%i' not in snxfile:
        f = open(snxfile, mode)
    else:
        splitfile = True
        snxfile = snxfile.replace('%i', '%%0%ii'%int(N.log10(len(objects))))

    # Loop on objects
    for i, oo in enumerate(objects):

        # Extract object
        if isinstance(oo, LineString):
            oo = oo.get_coords()
            type = 'linestring'
        elif isinstance(oo, Polygon):
            oo = oo.get_coords()
            type = 'polygon'
        elif isinstance(oo[0], tuple):
            type = 'point'
        elif isinstance(oo[0], Point):
            ooo = []
            for o in oo:
                ooo.extend(o.get_coords())
            oo = ooo
            type = 'point'

        # Guess type
        if type == 'auto':
            if isinstance(oo[0], float):
                type = 'point'
            else:
                n = N.asarray(oo)
                d = N.sqrt(N.diff(n[:, 0])**2+N.diff(n[:, 1])**2)
                if d.mean() < 3*N.sqrt((n[0, 0]-n[-1, 0])**2+(n[0, 1]-n[-1, 1])**2):
                    type='polygon'
                else:
                    type = 'linestring'
                del d, n

        # Write
        # - splited file
        if isinstance(snxfile, (str, unicode)) and '%' in snxfile:
            f = open(snxfile%i, mode)
        # - header
        if type.startswith('point'): # Points
            f.write("B S\nCN Semis\nCP 0 0\nCP 0\n")
        elif type.startswith('line'): # LineString
            f.write("B N\nCN Niveau\nCP 0 1\nCP 99\nCP 0\n")
        elif type.startswith('poly'): # Polygon
            f.write("B N\nCN Niveau\nCP 1 1\nCP 99\nCP 0\n")
        for o in oo:
            if len(o) == 2:
                zz = z
            else:
                zz = o[2]
            f.write(('%s %s %s'%(xfmt, yfmt, zfmt)+' A\n')%(o[0], o[1], zz))
        if isinstance(snxfile, (str, unicode)) and '%' in snxfile:
            f.close()
    if not f.closed and close:
        f.close()


class ColoredFormatter(logging.Formatter):
    """Log formatter with colors"""
    def __init__(self, msg, full_line=False):
        logging.Formatter.__init__(self, msg)
        self.full_line = full_line
        self.colorize = TermColors().format

    def format(self, record):
        if self.full_line:
            return self.colorize(logging.Formatter.format(self, record), record.levelname)
        record.levelname = self.colorize(record.levelname, record.levelname)
        return logging.Formatter.format(self, record)

class _Redirector_(object):
    def __init__(self, func, prefix=''):
        self.func = func
        self.prefix = prefix
    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.func(self.prefix+line.rstrip())
    def flush(self):
        pass




class Logger(object):
    """Class for logging facilities when subclassing.
    Logging may be sent to the console and/or a log file

    :Params:

        - **name**: Name of the logger.
        - **logfile**, optional: Log file.
        - **console**, optional: Log to the console.
        - **maxlogsize**, optional: Maximal size of log file before rotating it.
        - **maxbackup**, optional: Maximal number of rotated files.
        - **sfmt**, optional: Format of log messages in log file.
        - **cfmt**, optional: Format of log message in console.
        - **asctime**, optional: Time format.
        - **level**, optional: Initialize logging level (see :meth:`set_loglevel`).
        - **colors**, optional: Use colors when formatting terminal messages?
        - **full_line**, optional: Colorize full line or just level name?
        - **redirect_warnings**, optional: Redirect messages issued by :mod:`warnings.warn`.
        - **redirect_stdout**, optional: Redirect messages issued to sys.stdout.
        - **redirect_stderr**, optional: Redirect messages issued to sys.stderr.

    :See also: :mod:`logging` module
    """
    def __init__(self, name, logfile=None, console=True, maxlogsize=0, maxbackup=0,
            cfmt='%(name)s [%(levelname)-8s] %(message)s',
            ffmt='%(asctime)s: %(name)s [%(levelname)-8s] %(message)s',
            asctime='%Y-%m-%d %H:%M',
            level='debug', colors=True, full_line=False,
            redirect_warnings=False, redirect_stdout=False, redirect_stderr=False):

        # Create or get logger
        self.logger = logger = logging.getLogger(name)

        # Handlers
        handlers = self.logger.handlers
        # - file
        if logfile is not None and logfile != '' and not any(
                [os.path.samefile(logfile,  l.baseFilename) for l in handlers
                    if isinstance(l, logging.handlers.RotatingFileHandler)]):
            checkdir(logfile, asfile=True)
            file =  logging.handlers.RotatingFileHandler(logfile,
                maxBytes=maxlogsize*1000, backupCount=maxbackup)
            file.setFormatter(logging.Formatter(ffmt, asctime))
            logger.addHandler(file)
        # - console
        if console and not any([(isinstance(l, logging.StreamHandler) and
                    not isinstance(l, logging.FileHandler)) for l in handlers]):
            console = logging.StreamHandler()
            if colors:
                console.setFormatter(ColoredFormatter(cfmt, full_line=full_line))
            else:
                console.setFormatter(logging.Formatter(cfmt))
            logger.addHandler(console)
        self.set_loglevel(level)

        # Redirections
        if redirect_warnings:
            warnings.showwarning = self.showwarning
        if redirect_stdout:
            if not isinstance(redirect_stdout, str):
                redirect_stdout = 'debug'
            sys.stdout = _Redirector_(getattr(self, redirect_stdout),
                prefix='STDOUT: ')
        if redirect_stderr:
            if not isinstance(redirect_stderr, str):
                redirect_stderr = 'warning'
            sys.stderr = _Redirector_(getattr(self, redirect_stderr),
                prefix='STDERR: ')


        # Announce
        logger.debug('*** Start log session ***')

    def debug(self, text, *args, **kwargs):
        """Send a debug message"""
        self.logger.debug(text, *args, **kwargs)

    def info(self, text, *args, **kwargs):
        """Send a info message"""
        self.logger.info(text, *args, **kwargs)

    def warning(self, text, *args, **kwargs):
        """Send a warning message"""
        self.logger.warning(text, *args, **kwargs)

    def showwarning(self, message, category, filename, lineno,
            file=None):
        self.warning(
            'REDIRECTED: %s:%s: %s:%s',
            filename, lineno,
            category.__name__, message,
        )


    def _log_and_exit_(self, slevel, text, *args, **kwargs):
        """Log a message and exit"""
        getattr(self.logger, slevel)(text, *args, **kwargs)
        mode = kwargs.pop('mode', None)
        if mode=='exiterr':
            mode = sys.exit
        elif mode=='exit':
            mode = 1
        if isinstance(mode, Exception):
            raise mode(text)
        elif callable(mode):
            mode(text)
        elif isinstance(mode, int):
            sys.exit(mode)


    def error(self, text, *args, **kwargs):
        """Send an error message"""
        self._log_and_exit_('error', text, *args, **kwargs)

    def critical(self, text, *args, **kwargs):
        """Send a critical message"""
        self._log_and_exit_('critical', text, *args, **kwargs)

    def set_loglevel(self, level=None, console=None, file=None):
        """Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        :Example:

            >>> logger.set_loglevel('DEBUG', console='INFO')
        """
        if level is not None:
            self.logger.setLevel(self._get_loglevel_(level))
        for handler in self.logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                if file is not None: handler.setLevel(self._get_loglevel_(file))
            elif console is not None and \
                isinstance(handler, logging.StreamHandler):
                handler.setLevel(self._get_loglevel_(console))

    def get_loglevel(self, asstring=False):
        """Get the log level as an integer or a string"""
        if asstring:
            for label in 'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL':
                if self.logger.level == getattr(logging, label):
                    return label
            return 'NOTSET'
        return self.logger.level

    def _get_loglevel_(self, level):
        if level is None: level = 'debug'
        if isinstance(level, str):
            level = getattr(logging, level.upper(), 'DEBUG')
        return level

class TermColors(object):
    RED = ERROR = FAILURE = CRITICAL = '\033[31m'
    GREEN = INFO = OK = SUCCESS = '\033[32m'
    YELLOW = WARNING = '\033[33m'
    NORMAL = DEBUG = '\033[39m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    RESET = '\033[0m'

    def __init__(self):
        try: import curses
        except ImportError: curses = None
        import sys
        if curses:
            # This is a feature test which may end with an exception (eg. exec through ssh session, unset TERM env var)
            # We don't want to see this kind error (but we are masking other potential errors...)
            try: curses.setupterm()
            except: pass
        if not sys.stdout.isatty() or not curses or (curses.tigetstr('setf') is None and curses.tigetstr('setaf') is None):
            self.disable()

    def disable(self):
        for att in "RED ERROR FAILURE CRITICAL \
        GREEN INFO OK SUCCESS YELLOW WARNING \
        NORMAL DEBUG BLUE MAGENTA CYAN RESET".split():
            setattr(self, att, '')

    def format(self, text, color='NORMAL'):
        """Format a string for its color printing in a terminal

        - **text**: simple string message
        - *color*: color or debug level
        """
        color = color.upper()
        if not hasattr(self, color): return text
        return getattr(self, color)+text+self.RESET

def netcdf3():
    """Turn netcdf4 writing off with :mod:`cdms2`"""
    try:
        netcdf4(0, 0, 0)
    except:
        pass


def netcdf4(level=3, deflate=1, shuffle=1):
    """Turn netcdf4 writing on and suppress compression warning"""
    cdms2.setCompressionWarnings(0)
    cdms2.setNetcdfDeflateFlag(deflate)
    cdms2.setNetcdfShuffleFlag(shuffle)
    cdms2.setNetcdfDeflateLevelFlag(level)


######################################################################
######################################################################


