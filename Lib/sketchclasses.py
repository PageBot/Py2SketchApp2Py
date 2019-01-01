#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# -----------------------------------------------------------------------------
#
#  P Y 2 S K E T C H A P P 2 P Y
#
#  Copyright (c) 2016+ Buro Petr van Blokland + Claudia Mens
#  www.pagebot.io
#  Licensed under MIT conditions
#
#  Supporting DrawBot, www.drawbot.com
#  Supporting Flat, xxyxyz.org/flat
#  Supporting Sketch, https://github.com/Zahlii/python_sketch_api
# -----------------------------------------------------------------------------
#
#  classes.py
#
#  Site page opening any sketch file format:
#  https://xaviervia.github.io/sketch2json/
#
#  https://gist.github.com/xaviervia/edbea95d321feacaf0b5d8acd40614b2
#  This description is not complete. 
#  Additions made where found in the Reading specification of this context.
#
#  http://sketchplugins.com/d/87-new-file-format-in-sketch-43
#
#  This source will not import PageBot. But it is written in close
#  conntection to it, so PageBot can read/write Document and Element
#  instances into SketchApp files.
#
#  Webviewer
#  https://github.com/AnimaApp/sketch-web-viewer
#
import os
import zipfile
import json
import re
import io
import weakref

FILETYPE_SKETCH = 'sketch' # SketchApp file extension
UNTITLED_SKETCH = 'untitled.' + FILETYPE_SKETCH # Name for untitled SketchFile.path
IMAGES_PATH = '_images/' # Path extension for image cache directory
DOCUMENT_JSON = 'document.json'
USER_JSON = 'user.json'
META_JSON = 'meta.json'
PAGES_JSON = 'pages/'
IMAGES_JSON = 'images/'
PREVIEWS_JSON = 'previews/' # Internal path for preview images

# Defaults 
BASE_FRAME = dict(x=0, y=0, width=1, height=1)
POINT_ORIGIN = '{0, 0}'
BLACK_COLOR = dict(red=0, green=0, blue=0, alpha=1)
DEFAULT_FONT = 'Verdana'
DEFAULT_FONTSIZE = 12

APP_VERSION = "51.3"
APP_ID = 'com.bohemiancoding.sketch3'

# SketchApp 43 files JSON types

'''
type UUID = string // with UUID v4 format

type SketchPositionString = string // '{0.5, 0.67135115527602085}'



type FilePathString = string

'''

POINT_PATTERN = re.compile('\{([0-9\.\-]*), ([0-9\.\-]*)\}')
  # type SketchPositionString = string // '{0.5, 0.67135115527602085}'


class SketchAppBase:
  """Base class for SketchAppReader and SketchAppWriter"""

  def __init__(self, overwriteImages=False):
    self.overwriteImages = overwriteImages

class SketchBase:

  REPR_ATTRS = ['name'] # Attributes to be show in __repr__

  def __init__(self, d, parent=None):
    if d is None:
      d = {}
    self._class = self.CLASS # Forces values to default, in case it is not None
    self.parent = parent # Save reference to parent layer as weakref.
    # Expect dict of attrNames and (method_Or_SketchBaseClass, default) as value
    for attrName, (m, default) in self.ATTRS.items():
      try:
        setattr(self, attrName, m(d.get(attrName, default), self))
      except TypeError:
        print(m)
  def __getitem__(self, attrName):
    """Allow addressing as dictionary too."""
    return getattr(self, attrName)

  def __repr__(self):
    s = ['<%s' % self._class]
    for attrName in self.REPR_ATTRS:
      if hasattr(self, attrName):
        s.append('%s=%s' % (attrName, getattr(self, attrName)))
    return ' '.join(s) + '>'

  def _get_parent(self):
    if self._parent is not None:
      return self._parent() # Get weakref to parent node
    return None
  def _set_parent(self, parent):
    if parent is not None:
      parent = weakref.ref(parent)
    self._parent = parent
  parent = property(_get_parent, _set_parent)
  
  def _get_root(self):
    """Answer the root (SketchFile instance) of self, searching upwards 
    through chain of parents. Answer None if no root can be found.
    """
    parent = self.parent # Expand weakref
    if parent is not None:
      return self.parent # Still searching in layer.parent sequence
    return None
  root = property(_get_root)

  def asDict(self):
    d = dict(_class=self._class)
    for attrName, (m, default) in self.ATTRS.items():
      d[attrName] = getattr(self, attrName)
    return d

  def find(self, nodeType, found=None):
    if found is None:
      found = []
    if self._class == nodeType:
      found.append(self)
    if hasattr(self, 'layers'):
      for layer in self.layers:
        layer.find(nodeType, found)
    return found

  def asJson(self):
    d = {}
    for attrName in self.ATTRS.keys():
      attr = getattr(self, attrName)
      if isinstance(attr, (list, tuple)):
        l = [] 
        for e in attr:
          if hasattr(e, 'asJson'):
            l.append(e.asJson())
          else:
            l.append(e)
        attr = l
      elif hasattr(attr, 'asJson'):
        attr = attr.asJson()
      if attr is not None:
        assert isinstance(attr, (dict, int, float, list, tuple, str)), attr
        d[attrName] = attr
    if not d:
      return None
    if self.CLASS is not None:
      d['_class'] = self.CLASS
    return d

class Point(SketchBase):
  """Interpret the {x,y} string into a point2D.

  >>> Point('{0, 0}')
  <point x=0.0 y=0.0>
  >>> Point('{0000021, -12345}')
  <point x=21.0 y=-12345.0>
  >>> Point('{10.05, -10.66}')
  <point x=10.05 y=-10.66>
  """
  def __init__(self, sketchPoint, parent=None):
    sx, sy = POINT_PATTERN.findall(sketchPoint)[0]
    self.x = asNumber(sx)
    self.y = asNumber(sy)
    self.parent = parent

  def __repr__(self):
    return '<point x=%s y=%s>' % (self.x, self.y)

  def asJson(self):
    return '{%s, %s}' % (self.x, self.y)

def asRect(sketchNestedPositionString, parent=None):
  """
  type SketchNestedPositionString = string // '{{0, 0}, {75.5, 15}}'
  """
  if sketchNestedPositionString is None:
    return None
  (x, y), (w, h) = POINT_PATTERN.findall(sketchNestedPositionString)
  return x, y, w, h

def asColorNumber(v, parent=None):
  try:
    return min(1, max(0, float(v)))
  except ValueError:
    return 0

def asNumber(v, parent=None):
  try:
    return float(v)
  except ValueError:
    return 0

def asInt(v, parent=None):
  try:
    return int(v)
  except ValueError:
    return 0

def asBool(v, parent=None):
  return bool(v)

def asPoint(p, parent=None):
  return p

def asId(v, parent=None):
  return v

def asString(v, parent=None):
  return str(v)

def asColorList(v, parent=None):
  return []

def asGradientList(v, parent=None):
  return []

def asImageCollection(v, parent=None):
  return []

def asImages(v, parent=None):
  return []

def asDict(v, parent=None):
  return {}

def asList(v, parent=None):
  return list(v)

def FontList(v, parent=None):
  return []

def HistoryList(v, parent=None):
  return ['NONAPPSTORE.57544']

def SketchCurvePointList(curvePointList, parent):
  l = []
  for curvePoint in curvePointList:
    l.append(SketchCurvePoint(curvePoint))
  return l

class SketchCurvePoint(SketchBase):
  """
  type SketchCurvePoint = {
    _class: 'curvePoint',
    do_objectID: UUID,
    cornerRadius: number,
    curveFrom: SketchPositionString, --> Point
    curveMode: number,
    curveTo: SketchPositionString, --> Point
    hasCurveFrom: bool,
    hasCurveTo: bool,
    point: SketchPositionString --> Point
  """
  CLASS = 'curvePoint'
  ATTRS = {
    'do_objectID': (asId, None),
    'cornerRadius': (asNumber, 0),
    'curveFrom': (Point, POINT_ORIGIN),
    'curveMode': (asInt, 1),
    'curveTo': (Point, POINT_ORIGIN),
    'hasCurveFrom': (asBool, False),
    'hasCurveTo': (asBool, False),
    'point': (Point, POINT_ORIGIN),
  }

class SketchLayer(SketchBase):

  def __init__(self, d, parent):
    SketchBase.__init__(self, d, parent)
    self.layers = [] # List of Sketch element instances.
    for layer in d.get('layers', []):
      # Create new layer, set self as its weakref parent and add to self.layers list.
      self.layers.append(SKETCHLAYER_PY[layer['_class']](layer, self))

  def asJson(self):
    d = SketchBase.asJson(self)
    d['layers'] = layers = []
    for layer in self.layers:
      layers.append(layer.asJson())
    return d

class SketchImageCollection(SketchBase):
  """
  _class: 'imageCollection',
  images: Unknown // TODO
  """
  CLASS = 'imageCollection'
  ATTRS = {
    'images': (asDict, {})
  }

class SketchColor(SketchBase):
  """
  _class: 'color',
  do_objectID: UUID,
  alpha: number,
  blue: number,
  green: number,
  red: number

  For more color functions see PageBot/toolbox/color

  >>> test = dict(red=0.5, green=0.1, blue=1)
  >>> color = SketchColor(test, None)
  >>> color.red
  0.5
  >>> sorted(color.asDict())
  ['_class', 'alpha', 'blue', 'do_objectID', 'green', 'red']
  """
  REPR_ATTRS = ['red', 'green', 'blue', 'alpha'] # Attributes to be show in __repr__
  CLASS = 'color'
  ATTRS = {
    'do_objectID': (asId, None),
    'red': (asColorNumber, 0),
    'green': (asColorNumber, 0),
    'blue': (asColorNumber, 0),
    'alpha': (asColorNumber, 0),
  }

class SketchBorder(SketchBase):
  """
  _class: 'border',
  isEnabled: bool,
  color: SketchColor,
  fillType: number,
  position: number,
  thickness: number

  For usage in PageBot, use equivalent PageBot/elements/Element.getBorderDict()

  >>> test = dict(color=dict(red=1))
  >>> border = SketchBorder(test)
  >>> border.color
  <color red=1 green=0 blue=0 alpha=0>
  """
  CLASS = 'border'
  ATTRS = {
    'isEnabled': (asBool, True),
    'color': (SketchColor, None),
    'fillType': (asNumber, 0),
    'position': (asInt, 0),
    'thickness': (asNumber, 1)
  }

class LayoutGrid(SketchBase):
  """
  + isEnabled: bool,
  + columnWidth: number,
  + drawHorizontal: bool,
  + drawHorizontalLines: bool,
  + drawVertical: bool,
  + gutterHeight: number,
  + gutterWidth: number,
  + guttersOutside: bool,
  + horizontalOffset: number,
  + numberOfColumns: number,
  + rowHeightMultiplication: number,
  + totalWidth: number,
  """
  CLASS = 'layoutGrid'
  ATTRS = {
    'isEnabled': (asBool, True),
    'columnWidth': (asNumber, 96),
    'drawHorizontal': (asBool, True),
    'drawHorizontalLines': (asBool, False),
    'drawVertical': (asBool, True),
    'gutterHeight': (asNumber, 24),
    'gutterWidth': (asNumber, 24),
    'guttersOutside': (asBool, False),
    'horizontalOffset': (asNumber, 60),
    'numberOfColumns': (asNumber, 5),
    'rowHeightMultiplication': (asNumber, 3),
    'totalWidth': (asNumber, 576),
  }

class SketchGradientStop(SketchBase):
  """
  _class: 'gradientStop',
  color: SketchColor,
  position: number
  
  >>> test = dict(color=dict(blue=1), position=1) 
  >>> gs = SketchGradientStop(test)
  >>> gs.color, gs.position
  (<color red=0 green=0 blue=1 alpha=0>, 1)
  """
  CLASS = 'gradientStop'
  ATTRS = {
    'color': (SketchColor, None),
    'position': (asPoint, 0), 
  }

def SketchGradientStopList(dd):
  l = []
  for d in dd:
    l.append(SketchGradientStop(d))
  return l

class SketchGradient(SketchBase):
  """
  _class: 'gradient',
  elipseLength: number,
  from: SketchPositionString,
  gradientType: number,
  shouldSmoothenOpacity: bool,
  stops: [SketchGradientStop],
  to: SketchPositionString

  """
  CLASS = 'gradient'
  ATTRS = {
    'elipseLength': (asNumber, 0),
    'from_': (asPoint, None),  # Initilaizes to (0, 0)
    'gradientType': (asInt, 0),
    'shouldSmoothenOpacity': (asBool, True),
    'stops': (SketchGradientStopList, []),
    'to_': (asPoint, None),
  }

class SketchGraphicsContextSettings(SketchBase):
  """
  _class: 'graphicsContextSettings',
  blendMode: number,
  opacity: number
  """
  CLASS = 'graphicsContextSettings'
  ATTRS = {
    'blendMode': (asNumber, 0),
    'opacity': (asNumber, 1),
  }

'''
type SketchInnerShadow = {
  _class: 'innerShadow',
  isEnabled: bool,
  blurRadius: number,
  color: SketchColor,
  contextSettings: SketchGraphicsContextSettings,
  offsetX: 0,
  offsetY: 1,
  spread: 0
}
'''
def SketchFillList(sketchFills, parent):
  l = []
  for fill in sketchFills:
    l.append(SketchFill(fill, parent))
  if l:
    return l
  return None # Ignore in output

class SketchFill(SketchBase):
  """
  _class: 'fill',
  isEnabled: bool,
  color: SketchColor,
  fillType: number,
  gradient: SketchGradient,
  noiseIndex: number,
  noiseIntensity: number,
  patternFillType: number,
  patternTileScale: number
  """
  CLASS = 'fill'
  ATTRS = {
    'isEnabled': (asBool, True),
    'color': (SketchColor, BLACK_COLOR),
    'fillType': (asInt, 0),
    'noiseIndex': (asNumber, 0),
    'noiseIntensity': (asNumber, 0),
    'patternFillType': (asNumber, 1),
    'patternTileScale': (asNumber, 1),
  }

class SketchShadow(SketchBase):
  """
  _class: 'shadow',
  isEnabled: bool,
  blurRadius: number,
  color: SketchColor,
  contextSettings: SketchGraphicsContextSettings,
  offsetX: number,
  offsetY: number,
  spread: number
  """
  CLASS = 'shadow'
  ATTRS = {
    'isEnabled': (asBool, True),
    'blurRadius': (asNumber, 0),
    'color': (SketchColor, BLACK_COLOR),
    'contextSettings': (SketchGraphicsContextSettings, {}),
    'offsetX': (asNumber, 0),
    'offsetY': (asNumber, 0),
    'spread': (asNumber, 0),  
  }

'''
type SketchBlur = {
  _class: 'blur',
  isEnabled: bool,
  center: SketchPositionString,
  motionAngle: number,
  radius: number,
  type: number
}
'''

class SketchEncodedAttributes(SketchBase):
  """
  NSKern: number,
  MSAttributedStringFontAttribute: {
    _archive: Base64String,
  },
  NSParagraphStyle: {
    _archive: Base64String
  },
  NSColor: {
    _archive: Base64String
  }
  """
  CLASS = 'sketchEncodedAttributes'
  ATTRS = {}

class SketchRect:
  """
  _class: 'rect',
  + do_objectID: UUID,
  + constrainProportions: bool,
  + height: number,
  + width: number,
  + x: number,
  + y: number
  """
  def __init__(self, d, parent=None):
    if d is None:
      d = dict(x=0, y=0, w=0, h=0, constrainProportions=True)
    self.do_objectID = d.get('do_objectID')
    self.x = d.get('x', 0)
    self.y = d.get('y', 0)
    self.w = d.get('width', 100)
    self.h = d.get('height', 100)
    self.constrainProportions = d.get('constrainProportions', False)
    self.parent = parent

  def __repr__(self):
    s = '(x=%s y=%d w=%d h=%d' % (self.x, self.y, self.w, self.h)
    if self.constrainProportions:
       s += ' constrain=True'
    return s + ')'

  def asJson(self):
    d = dict(_class='rect', x=self.x, y=self.y, width=self.w, height=self.h, 
        constrainProportions=self.constrainProportions)
    if self.do_objectID is not None:
      d['do_objectID'] = self.do_objectID
    return d

class SketchTextStyle(SketchBase):
  """
  _class: 'textStyle',
  encodedAttributes: SketchEncodedAttributes
  """
  CLASS = 'textStyle'
  ATTRS = {
    'encodedAttributes': (SketchEncodedAttributes, None),
  }

class SketchBorderOptions(SketchBase):
  """
  _class: 'borderOptions',
  do_objectID: UUID,
  isEnabled: bool,
  dashPattern: [], // TODO,
  lineCapStyle: number,
  lineJoinStyle: number
  """
  CLASS = 'borderOptions'
  ATTRS = {
    'do_objectID': (asId, None),
    'isEnabled': (asBool, True),
    'dashPattern': (asString, ''),
    'lineCapStyle': (asNumber, 0),
    'lineJoinStyle': (asNumber, 0),
  }

class SketchColorControls(SketchBase):
  """
  _class: 'colorControls',
  isEnabled: bool,
  brightness: number,
  contrast: number,
  hue: number,
  saturation: number
  """
  CLASS = 'colorConstrols'
  ATTRS = {
    'isEnabled': (asBool, True),
    'brightness': (asNumber, 1),
    'contrast': (asNumber, 1),
    'hue': (asNumber, 1),
    'saturation': (asNumber, 1),
  }

def SketchBordersList(sketchBorders, parent):
  l = []
  for sketchBorder in sketchBorders:
    l.append(SketchBorder(sketchBorder, parent))
  if l:
    return l
  return None

def SketchShadowsList(sketchShadows, parent):
  l = []
  for sketchShadow in sketchShadows:
    l.append(SketchShadow(sketchShadow, parent))
  if l:
    return l
  return None

class SketchStyle(SketchBase):
  """
  _class: 'style',
  + do_objectID: UUID,
  blur: ?[SketchBlur],
  + borders: ?[SketchBorder],
  borderOptions: ?SketchBorderOptions,
  contextSettings: ?SketchGraphicsContextSettings,
  colorControls: ?SketchColorControls,
  endDecorationType: number,
  + fills: [SketchFill],
  innerShadows: [SketchInnerShadow],
  + miterLimit: number,
  + shadows: ?[SketchShadow],
  sharedObjectID: UUID,
  startDecorationType: number,
  textStyle: ?SketchTextStyle
  + endMarkerType: number,
  + startMarkerType: number,
  + windingRule: number,
  """
  CLASS = 'style'
  ATTRS = {
    'do_objectID': (asId, None),
    'endMarkerType': (asInt, 0),
    'borders': (SketchBordersList, []),
    'fills': (SketchFillList, []),
    'shadows': (SketchShadowsList, []),
    'miterLimit': (asInt, 10),
    'startMarkerType': (asInt, 0),
    'windingRule': (asInt, 1)
  }

class SketchSharedStyle(SketchBase):
  """
  _class: 'sharedStyle',
  do_objectID: UUID,
  name: string,
  value: SketchStyle
  """
  CLASS = 'sharedStyle'
  ATTRS = {
    'do_objectID': (asId, None),
    'name': (asString, 'Untitled'),
    'value': (SketchStyle, None),
  }

def SketchExportFormatList(exporFormats, parent):
  l = []
  for exportFormat in exporFormats:
    l.append(SketchExportFormat(exportFormat, parent))
  return l

class SketchExportFormat(SketchBase):
  """
  _class: 'exportFormat',
  absoluteSize: number,
  fileFormat: string,
  name: string,
  namingScheme: number,
  scale: number,
  visibleScaleType: number
  """
  CLASS = 'exportFormat'
  ATTRS = {
    'absoluteSize': (asNumber, 1),
    'fileFormat': (asString, ''),
    'name': (asString, ''),
    'namingSchema': (asNumber, 0),
    'scale': (asNumber, 1),
    'visibleScaleType': (asNumber, 0),
  }

class SketchExportOptions(SketchBase):
  """
  _class: 'exportOptions',
  + do_objectID: UUID,
  + exportFormats: [SketchExportFormat],
  + includedLayerIds: [], // TODO
  + layerOptions: number,
  + shouldTrim: bool
  """
  CLASS = 'exportOptions'
  ATTRS = {
    'do_objectID': (asId, None),
    'exportFormats': (SketchExportFormatList, []),
    'layerOptions': (asInt, 0),
    'includedLayerIds': (asList, []),
    'shouldTrim': (asBool, False),
  }

class SketchSharedStyleContainer(SketchBase):
  """
  _class: 'sharedStyleContainer',
  objects: [SketchSharedStyle]
  """
  CLASS = 'sharedStyleContainer'
  ATTRS = {
    'objects': (asList, []),
  }

class SketchSymbolContainer(SketchBase):
  """
  _class: 'symbolContainer',
  objects: [] // TODO
  """
  CLASS = 'symbolContainer'
  ATTRS = {
    'objects': (asList, []),
  }

class SketchSharedTextStyleContainer(SketchBase):
  """
  _class: 'sharedTextStyleContainer',
  objects: [SketchSharedStyle]
  """
  CLASS = 'sharedTextStyleContainer'
  ATTRS = {
    'objects': (asList, []),
  }

class SketchAssetsCollection(SketchBase):
  """
  _class: 'assetCollection',
  colors: [], // TODO
  gradients: [], // TODO
  imageCollection: SketchImageCollection,
  images: [] // TODO
  """
  CLASS = 'assetCollection'
  ATTRS = {
    'colors': (asColorList, []),
    'gradients': (asGradientList, []),
    'imageCollection': (SketchImageCollection, []),
    'images': (asImages, []),
  }

class SketchCreated(SketchBase):
  """
  commit: string,
  appVersion: string,
  build: number,
  app: string,
  version: number,
  variant: string // 'BETA'
  compatibilityVersion': number,
  """
  CLASS = None
  ATTRS = {
    'commit': (asString, ''),
    'appVersion': (asString, APP_VERSION),
    'build': (asNumber, 0),
    'app': (asString, APP_ID),    
    'version': (asInt, 0),
    'variant': (asString, ''),
    'compatibilityVersion': (asInt, 99)
  }

def SketchMSJSONFileReferenceList(refs, parent=None):
  l = []
  for ref in refs:
    l.append(SketchMSJSONFileReference(ref, parent))
  return l

class SketchMSJSONFileReference(SketchBase):
  """
  _class: 'MSJSONFileReference',
  _ref_class: 'MSImmutablePage' | 'MSImageData',
  _ref: FilePathString
  """
  CLASS = 'MSJSONFileReference'
  ATTRS = {
    '_ref_class': (asString, 'MSImageData'),
    '_ref': (asString, ''),
  }

class SketchFontDescriptorAttributes(SketchBase):
  """
  name: string
  size: number
  """
  CLASS = None
  ATTRS = {
    'name': (asString, DEFAULT_FONT),
    'size': (asNumber, DEFAULT_FONTSIZE),
  }

class SketchFontDescriptor(SketchBase):
  """
  _class: 'fontDescriptor',
  attributes: SketchFontDescriptorAttributes
  """
  CLASS = 'fontDescriptor'
  ATTRS = {
    'attributes': (SketchFontDescriptorAttributes, {})
  }

class SketchParagraphStyle(SketchBase):
  """
  _class: 'paragraphStyle',
  alignments: number,
  """
  CLASS = 'paragraphStyle'
  ATTRS = {
    'alignment': (asInt, 2),
  }

class SketchAttributes(SketchBase):
  """
  MSAttributedStringFontAttribute: SketchFontDescriptor
  MSAttributedStringColorAttribute: SketchColor
  textStyleVerticalAlignmentKey: number
  kerning: number, # Wrong name for tracking.
  paragraphStyle: SketchParagraphStyle
  """
  CLASS = None
  ATTRS = {
    'MSAttributedStringFontAttribute': (SketchFontDescriptor, None),
    'MSAttributedStringColorAttribute': (SketchColor, BLACK_COLOR),
    'textStyleVerticalAlignmentKey': (asInt, 0),
    'kerning': (asNumber, 0), # Wrong name for tracking
    'paragraphStyle': (SketchParagraphStyle, None),
  }

class SketchStringAttribute(SketchBase):
  """
  _class: 'stringAttribute';
  length: number,
  attributes: [SketchAttributes]
  """
  CLASS = 'stringAttribute'
  ATTRS = {
    'location': (asInt, 0),
    'length': (asInt, 0),
    'attributes': (SketchAttributes, None),
  }

def SketchStringAttributeList(stringAttributes, parent):
  l = []
  for stringAttribute in stringAttributes:
    l.append(SketchStringAttribute(stringAttribute, parent))
  return l

class SketchAttributedString(SketchBase):
  """
  _class: 'attributedString',
  string: str,
  attributes: [StringAttribute],
  """
  CLASS = 'attributedString'
  ATTRS = {
    'string': (asString, ''),
    'attributes': (SketchStringAttributeList, [])
  }

class SketchRulerData(SketchBase):
  """
  _class: 'rulerData',
  + do_objectID: UUID,
  + base: number,
  + guides: [] // TODO
  """
  CLASS = 'rulerData'
  ATTRS = {
    'do_objectID': (asId, None),
    'base': (asInt, 0),
    'guides': (asList, []),
  }

class SketchText(SketchBase):
  """
  _class: 'text',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedVertical: bool,
  isFlippedHorizontal: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  originalObjectID: UUID,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  style: SketchStyle,
  attributedString: SketchAttributedString,
  automaticallyDrawOnUnderlyingPath: bool,
  dontSynchroniseWithSymbol: bool,
  glyphBounds: SketchNestedPositionString,
  heightIsClipped: bool,
  lineSpacingBehaviour: number,
  textBehaviour: number
  """
  CLASS = 'text'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asInt, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, 'Untitled'),
    'nameIsFixed': (asBool, False),
    'resizingConstraint': (asInt, 47),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'userInfo': (asDict, {}),
    'style': (SketchStyle, {}),
    'attributedString': (SketchAttributedString, None),
    'automaticallyDrawOnUnderlyingPath': (asBool, False),
    'dontSynchroniseWithSymbol': (asBool, False),
    'glyphBounds': (asString, "{{0, 0}, {100, 100}}"),
    'lineSpacingBehaviour': (asInt, 2),
    'textBehaviour': (asInt, 0),
  }

class SketchShapeGroup(SketchLayer):
  """
  _class: 'shapeGroup',
  + do_objectID: UUID,
  + booleanOperation: number,
  + exportOptions: SketchExportOptions,
  + frame: SketchRect,
  + isFixedToViewport: bool,
  + isFlippedVertical: bool,
  + isFlippedHorizontal: bool,
  + isLocked: bool,
  + isVisible: bool,
  + layerListExpandedType: number,
  + name: string,
  + nameIsFixed: bool,
  + originalObjectID: UUID,
  + resizingConstraint: number,
  + resizingType: number,
  + rotation: number,
  + shouldBreakMaskChain: bool,
  + userInfo: {}
  + style: SketchStyle,
  + hasClickThrough: bool,
  # layers: [SketchLayer],
  + clippingMaskMode: number,
  + hasClippingMask: bool,
  + windingRule: number
  """
  CLASS = 'shapeGroup'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asNumber, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, ''),
    'nameIsFixed': (asBool, False),
    'originalObjectID': (asId, None),
    'resizingConstraint': (asInt, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'userInfo': (asDict, {}),
    'style': (SketchStyle, None),
    'hasClickThrough': (asBool, False),
    'clippingMaskMode': (asInt, 0),
    'hasClippingMask': (asBool, False),
    'windingRule': (asInt, 1)
  }

class SketchPath(SketchBase):
  """
  _class: 'path',
  isClosed: bool,
  points: [SketchCurvePoint]
  """
  CLASS = 'path'
  ATTRS = {
    'isClosed': (asBool, False),
    'points': (SketchCurvePointList, []),
  }

class SketchShapePath(SketchBase):
  """
  _class: 'shapePath',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedVertical: bool,
  isFlippedHorizontal: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  booleanOperation: number,
  edited: bool,
  path: SketchPath
  """
  CLASS = 'shapePath'
  ATTRS = {
    'do_objectID': (asId, None),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFlippedHorizontal': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, ''),
    'nameIsFixed': (asBool, False),
    'name': (asString, ''),
    'nameIsFixed': (asBool, False),
  }

class SketchArtboard(SketchLayer):
  """
  _class: 'artboard',
  + do_objectID: UUID,
  + booleanOperation: number,
  + exportOptions: SketchExportOptions,
  + frame: SketchRect,
  + isFixedToViewport: bool,
  + isFlippedHorizontal: bool,
  + isFlippedVertical: bool,
  + isLocked: bool,
  + isVisible: bool,
  + layerListExpandedType: number,
  + name: string,
  + nameIsFixed: bool,
  + resizingConstraint: number,
  + resizingType: number,
  + rotation: number,
  + shouldBreakMaskChain: bool,
  + style: SketchStyle,
  + hasClickThrough: bool,
  # layers: [SketchLayer],
  + backgroundColor: SketchColor,
  + hasBackgroundColor: bool,
  + horizontalRulerData: SketchRulerData,
  + verticalRulerData: SketchRulerData,
  + includeBackgroundColorInExport: bool,
  + includeInCloudUpload: bool,
  + isFlowHome: (asBool, False),
  + userInfo: {}
  + layout: LayoutGrid,
  + resizesContent: bool,
  """
  REPR_ATTRS = ['name', 'frame'] # Attributes to be show in __repr__
  CLASS = 'artboard'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asInt, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, 'Artboard'),
    'nameIsFixed': (asBool, False),
    'resizingConstraint': (asNumber, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'style': (SketchStyle, None),
    'hasClickThrough': (asBool, False),
    'backgroundColor': (SketchColor, None),
    'hasBackgroundColor': (asBool, False),
    'horizontalRulerData': (SketchRulerData, None),
    'verticalRulerData': (SketchRulerData, None),
    'isFlowHome': (asBool, False),
    'includeBackgroundColorInExport': (asBool, False),
    'includeInCloudUpload': (asBool, True),
    'layers': (asList, []),
    'userInfo': (asDict, {}),
    'layout': (LayoutGrid, None),
    'resizesContent': (asBool, True),
  }

class SketchBitmap(SketchBase):
  """
  _class: 'bitmap',
  + do_objectID: UUID,
  + booleanOperation: number,
  + exportOptions: SketchExportOptions,
  + frame: SketchRect,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  + isFixedToViewport: bool,
  isLocked: bool,
  isVisible: bool,
  intendedDPI:number, 
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingConstraint: number,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  style: SketchStyle,
  userInfo: {}
  clippingMask: SketchNestedPositionString,
  fillReplacesImage: bool,
  image: SketchMSJSONFileReference,
  nineSliceCenterRect: SketchNestedPositionString,
  nineSliceScale: SketchPositionString
  """
  CLASS = 'bitmap'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asInt, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isFixedToViewport': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'intendedDPI': (asNumber, 72),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, ''),
    'resizingConstraint': (asNumber, 63),
    'nameIsFixed': (asBool, False),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'style': (SketchStyle, None),
    'userInfo': (asDict, {}),
    'clippingMask': (asString, BASE_FRAME),
    'fillReplacesImage': (asBool, False),
    'image': (SketchMSJSONFileReference, None),
    'nineSliceCenterRect': (asRect, None),
    'nineSliceScale': (asRect, None)
  }

class SketchSymbolInstance(SketchBase):
  """
  _class: 'symbolInstance',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  style: SketchStyle,
  horizontalSpacing: number,
  masterInfluenceEdgeMaxXPadding: number,
  masterInfluenceEdgeMaxYPadding: number,
  masterInfluenceEdgeMinXPadding: number,
  masterInfluenceEdgeMinYPadding: number,
  symbolID: number,
  verticalSpacing: number,
  overrides: {
    "0": {} // TODO
  }
  """
  CLASS = 'symbolInstance'
  ATTRS = {

  }

class SketchGroup(SketchLayer):
  """
  _class: 'group',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  originalObjectID: UUID,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  hasClickThrough: bool,
  # layers: [SketchLayer]
  """
  CLASS = 'group'
  ATTRS = {
    'do_objectID': (asId, None),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, 'Group'),
    'nameIsFixed': (asBool, False),
    'originalObjectID': (asId, None),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'hasClickThrough': (asBool, False),
  }

class SketchRectangle(SketchBase):
  """
  _class: 'rectangle',
  do_objectID: UUID,
  booleanOperation: number,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFixedToViewport': bool,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  resizingConstraint: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  edited: bool,
  isClosed: bool,
  points: CurvePointList,
  path: SketchPath,
  fixedRadius: number,
  hasConvertedToNewRoundCorners: bool
  """
  CLASS = 'rectangle'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asInt, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedHorizontal': (asBool, bool),
    'isFlippedVertical': (asBool, bool),
    'isLocked': (asBool, bool),
    'isVisible': (asBool, bool),
    'layerListExpandedType': (asNumber, 0),
    'name': (asString, 'Rectangle'),
    'nameIsFixed': (asBool, bool),
    'resizingConstraint': (asNumber, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'edited': (asBool, False),
    'isClosed': (asBool, True),
    'path': (SketchPath, None),
    'points': (SketchCurvePointList, []),
    'fixedRadius': (asNumber, 0),
    'hasConvertedToNewRoundCorners': (asBool, True)
  }

class SketchOval(SketchBase):
  """
  _class: 'oval',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  booleanOperation: number,
  edited: bool,
  path: SketchPath  
  """
  CLASS = 'oval'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asBool, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, CLASS),
    'nameIsFixed': (asBool, False),
    'resizingConstraint': (asInt, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'edited': (asBool, False),
    'isClosed': (asBool, True),
    'pointRadiusBehaviour': (asInt, 1),
    'points': (SketchCurvePointList, []),
  }


class SketchStar(SketchBase):
  """
  _class: 'star',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  booleanOperation: number,
  edited: bool,
  path: SketchPath  
  """
  CLASS = 'star'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asBool, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, CLASS),
    'nameIsFixed': (asBool, False),
    'resizingConstraint': (asInt, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'edited': (asBool, False),
    'isClosed': (asBool, True),
    'pointRadiusBehaviour': (asInt, 1),
    'points': (SketchCurvePointList, []),
  }

class SketchPolygon(SketchBase):
  """
  _class: 'polygon',
  do_objectID: UUID,
  exportOptions: SketchExportOptions,
  frame: SketchRect,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  booleanOperation: number,
  edited: bool,
  path: SketchPath  
  """
  CLASS = 'polygon'
  ATTRS = {
    'do_objectID': (asId, None),
    'booleanOperation': (asBool, -1),
    'exportOptions': (SketchExportOptions, {}),
    'frame': (SketchRect, BASE_FRAME),
    'isFixedToViewport': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, CLASS),
    'nameIsFixed': (asBool, False),
    'resizingConstraint': (asInt, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'edited': (asBool, False),
    'isClosed': (asBool, True),
    'pointRadiusBehaviour': (asInt, 1),
    'points': (SketchCurvePointList, []),
  }

# Conversion of Sketch layer class name to Python class.
SKETCHLAYER_PY = {
  'text': SketchText,
  'shapeGroup': SketchShapeGroup,
  'shapePath': SketchShapePath,
  'bitmap': SketchBitmap,
  'artboard': SketchArtboard,
  'symbolInstance': SketchSymbolInstance,
  'group': SketchGroup,
  'rectangle': SketchRectangle,
  'oval': SketchOval,
  'star': SketchStar,
  'polygon': SketchPolygon,
}

'''
type SketchSymbolMaster = {
  backgroundColor: SketchColor,
  _class: 'symbolMaster',
  do_objectID: UUID,
  exportOptions: [SketchExportOptions],
  frame: SketchRect,
  hasBackgroundColor: bool,
  hasClickThrough: bool,
  horizontalRulerData: SketchRulerData,
  includeBackgroundColorInExport: bool,
  includeBackgroundColorInInstance: bool,
  includeInCloudUpload: bool,
  isFlippedHorizontal: bool,
  isFlippedVertical: bool,
  isLocked: bool,
  isVisible: bool,
  layerListExpandedType: number,
  layers: SketchLayerList,
  name: string,
  nameIsFixed: bool,
  resizingType: number,
  rotation: number,
  shouldBreakMaskChain: bool,
  style: SketchStyle,
  symbolID: UUID,
  verticalRulerData: SketchRulerData
}
'''
# document.json
class SketchDocument(SketchBase):
  """
  _class: 'document',
  + do_objectID: UUID,
  + assets: SketchAssetsCollection,
  + colorSpace: number,
  + currentPageIndex: number,
  ? enableLayerInteraction: bool,
  ? enableSliceInteraction: bool,
  + foreignSymbols: [], // TODO
  + layerStyles: SketchSharedStyleContainer,
  + layerSymbols: SketchSymbolContainer,
  + layerTextStyles: SketchSharedTextStyleContainer,
  + pages: SketchMSJSONFileReferenceList,
  """
  CLASS = 'document'
  ATTRS = {
    'do_objectID': (asId, None),
    'assets': (SketchAssetsCollection, []),
    'colorSpace': (asInt, 0),
    'currentPageIndex': (asInt, 0),
    #'enableLayerInteraction': (asBool, False),
    #'enableSliceInteraction': (asBool, False),
    'foreignLayerStyles': (asList, []),
    'foreignSymbols': (asList, []),
    'foreignTextStyles': (asList, []),
    'layerStyles': (SketchSharedStyleContainer, {}),
    'layerSymbols': (SketchSymbolContainer, {}),
    'layerTextStyles': (SketchSharedTextStyleContainer, {}),
    'pages': (SketchMSJSONFileReferenceList, []),
  }

# pages/*.json
class SketchPage(SketchLayer):
  """
  _class: 'page',
  do_objectID: UUID,
  + booleanOperation: number, 
  + exportOptions: SketchExportOptions,
  + frame: SketchRect,
  + hasClickThrough: bool,
  + horizontalRulerData: SketchRulerData,
  + includeInCloudUpload: bool,
  + isFlippedHorizontal: bool,
  + isFlippedVertical: bool,
  + isLocked: bool,
  + isVisible: bool,
  + layerListExpandedType: number,
  # layers: [SketchSymbolMaster],
  + name: string,
  + nameIsFixed: bool,
  + resizingConstraint: number,
  + resizingType: number,
  + rotation: number,
  + shouldBreakMaskChain: bool,
  + style: SketchStyle,
  + verticalRulerData: SketchRulerData
  + userInfo: {}
}
  """
  CLASS = 'page'
  ATTRS = {
    'do_objectID': (asId, None),    
    'booleanOperation': (asInt, -1),
    'frame': (SketchRect, BASE_FRAME),
    'exportOptions': (SketchExportOptions, {}),
    'hasClickThrough': (asBool, True),
    'includeInCloudUpload': (asBool, False),
    'isFlippedHorizontal': (asBool, False),
    'isFlippedVertical': (asBool, False),
    'isLocked': (asBool, False),
    'isVisible': (asBool, True),
    'layerListExpandedType': (asInt, 0),
    'name': (asString, 'Untitled'),
    'nameIsFixed': (asBool, False),
    'resizingConstraint': (asNumber, 63),
    'resizingType': (asInt, 0),
    'rotation': (asNumber, 0),
    'shouldBreakMaskChain': (asBool, False),
    'style': (SketchStyle, None),
    'verticalRulerData': (SketchRulerData, None),
    'horizontalRulerData': (SketchRulerData, None),
    'userInfo': (asDict, {}),
  }

class SketchFile:
  """Holds entire data file. Top of layer.parent-->layer.parent-->sketchFile chain.
  """
  def __init__(self, path=None):
    self.path = path or UNTITLED_SKETCH
    self.pages = {}
    self.document = None
    self.user = None 
    self.meta = None

  def __repr__(self):
    return '<sketchFile>'   

  def find(self, findType):
    found = []
    for pageId, page in self.pages.items():
      page.find(findType, found)
    return found

  def _get_imagesPath(self):
    """Answer the _images/ path, related to self.path
    
    >>> SketchFile('/a/b/c/d.sketch').imagesPath
    '/a/b/c/d_images/'
    >>> SketchFile('d.sketch').imagesPath
    'd_images/'
    >>> SketchFile('a/b/c').imagesPath
    'a/b/c/_images/'
    >>> SketchFile().imagesPath
    'untitled_images/'
    """
    path = self.path
    if path.endswith('.' + FILETYPE_SKETCH):
      parts = path.split('/')
      if len(parts) > 1:
        imagesPath = '/'.join(parts[:-1]) + '/'
      else:
        imagesPath = ''
      imagesPath += (parts[-1].replace('.'+FILETYPE_SKETCH, '')) + IMAGES_PATH
    else:
      if not path.endswith('/'):
        path += '/'
      imagesPath = path + IMAGES_PATH
    return imagesPath
  imagesPath = property(_get_imagesPath) # Read only


# meta.json
class SketchMeta(SketchBase):
  """
  commit: string,
  appVersion: string,
  build: number,
  app: string,
  pagesAndArtboards: {
    [key: UUID]: { name: string }
  },
  fonts: [string], // Font names
  version: number,
  saveHistory: [ string ], // 'BETA.38916'
  autosaved: number,
  variant: string // 'BETA'
  compatibilityVersion': number,
  """
  CLASS = None
  ATTRS = {
    'commit': (asString, ''),
    'appVersion': (asString, APP_VERSION),
    'build': (asNumber, 0),
    'app': (asString, APP_ID),
    'pagesAndArtboards': (asList, []), # To be filled by self.__init__
    'fonts': (FontList, []), # Font names
    'version': (asInt, 0),
    'saveHistory': (HistoryList, []), # 'BETA.38916'
    'autosaved': (asInt, 0),
    'variant': (asString, ''),
    'created': (SketchCreated, {}),
    'compatibilityVersion': (asInt, 99),
  }

  def __init__(self, d, parent):
    SketchBase.__init__(self, d, parent)
    self.pagesAndArtboards = {} # Dictionary of Sketch element instances.
    for pageId, page in self.root.pages.items():
      # Create page or artboard reference
      artboards = {}
      self.pagesAndArtboards[page.do_objectID] = dict(name=page.name, artboards=artboards)
      for layer in page.layers:
        if layer._class == 'artboard':
          artboards[layer.do_objectID] = dict(name=layer.name)

# user.json
class SketchUser(SketchBase):
  """
  [key: SketchPageId]: {
    scrollOrigin: SketchPositionString,
    zoomValue: number
  },
  [key: SketchDocumentId]: {
    pageListHeight: number,
    cloudShare: Unknown // TODO
  }
  """
  CLASS = 'user'
  ATTRS = {
  }
  def __init__(self, d, parent):
    SketchBase.__init__(self, d, parent)
    self.document = dict(pageListHeight=118)

  def asJson(self):
    return dict(document=dict(pageListHeight=self.document['pageListHeight']))

if __name__ == '__main__':
  import doctest
  import sys
  sys.exit(doctest.testmod()[0])