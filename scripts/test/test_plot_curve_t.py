"""Test :func:`~vacumm.misc.plot.curve2` with a time axis"""

# Imports
from vcmq import MV2, code_base_name, os, code_base_name, curve2

# Init
var = MV2.arange(5.)
var.units = 'W'
var.long_name = 'Power'
axis = var.getAxis(0)
axis.units = 'months since 2013-01-01'
axis.long_name = 'Time'
axis.axis = 'T'


# Plot
figfile = code_base_name(ext='png')
if os.path.exists(figfile): os.remove(figfile)
curve2(var, savefig=figfile, show=False, close=True)

