# -*- coding: utf-8 -*-
from __future__ import print_function
import MV2, numpy as N
from vcmq import create_time, regrid1d, bar2

# Creation d'un jeu de precipitations horaires
hours = create_time((12*60, 25.*60,  60), 'minutes since 2000')
precip = MV2.sin(N.arange(len(hours))*.2)*10
precip.setAxis(0, hours)
precip.units = 'mm'
precip.long_name = 'Original'

# Nouvel echantillonnage / 2h
hours2 = create_time((10, 30., 2), 'hours since 2000')

# Regrillage 1D conservatif
precip2 = regrid1d(precip, hours2, 'conservative')
precip2.long_name = 'Regridded'

# Verifications
print('Total precip.:')
print('- original =', precip.sum())
print('- remapped =', precip2.sum())
# > Total precip.:
# > - original = 89.957242832779755
# > - remapped = 89.957237


# Plots
kwplot = dict(color='#00ffff',edgecolor='#55aaaa',
    width=.9, date_fmt='%Hh', show=False)
b = bar2(precip, figsize=(5.5, 6), xhide=True,
    subplot=211, top=.9, **kwplot)
b.figtext('Precipitations', style='italic')
bar2(precip2, subplot=212, **kwplot)

