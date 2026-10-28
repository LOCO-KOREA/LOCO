"""Report facade: shared overview, plain-language sheets (also used for the preview) and XLSX rendering."""
from .common import currentness, flatten
from .overview import overview
from .renderer import render
from .plain import plain_sheets
