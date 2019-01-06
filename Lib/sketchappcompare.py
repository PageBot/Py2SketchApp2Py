#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# -----------------------------------------------------------------------------
#
#  S K E T C H A P P 2 P Y
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
#  sketchcompare.py
#
#  Take two SketchApp files and compare them. 
#  Output an oveview of differences.
#
import os
from sketchclasses import *
from sketchappreader import SketchAppReader
from sketchappwriter import SketchAppWriter

CHECK_ID = False

IGNORE = ['userInfo']
if not CHECK_ID:
    IGNORE.append('do_objectID')

def _compare(d1, d2, result, path=None):
    if path is None:
        path = ''

    if isinstance(d1, SketchBase):
        if not isinstance(d2, SketchBase):
            result.append("%s is not SketchBase instance" % d2)
        else:
            for attrName in d1.ATTRS:
                if attrName in IGNORE:
                    continue
                v1 = getattr(d1, attrName)
                v2 = getattr(d2, attrName)
                _compare(v1, v2, result, path + '/' + attrName)
        if hasattr(d1, 'layers') != hasattr(d2, 'layers'):
            result.append("%s: %s does not have key %s" % (path, d2, dKey1))
        elif hasattr(d1, 'layers'):
            for index, layer1 in enumerate(d1.layers):
                layer2 = d2.layers[index]
                _compare(layer1, layer2, result, path + '/layers[%d]' % index)
    elif isinstance(d1, dict):
        if not isinstance(d2, dict):
            result.append("%s: %s and %s are not both dict" % (path, d1, d2))
        else:
            for dKey1, dd1 in d1.items():
                if not dKey1 in d2:
                    result.append("%s: %s does not have key %s" % (path, d2, dKey1))
                else:
                    dd2 = d2[dKey1]
                    _compare(dd1, dd2, result, path + '/' + dKey1)
    elif isinstance(d1, (list, tuple)):
        if not isinstance(d2,  (list, tuple)):
            result.append("%s: %s is not list/tuple instance" % (path, d2))
        elif (len(d1) != len(d2)):
            result.append("%s: Lists not same length %d - %d" % (path, d1, d2))
        else:
            for index, dd1 in enumerate(d1):
                dd2 = d2[index]
                _compare(dd1, dd2, result, path + '[%d]' % index)
    elif d1 != d2:
        result.append("%s: Value %s different from %s" % (path, d1, d2))


def sketchCompare(sketchFile1, sketchFile2, result=None):
    """
    >>> from sketchappreader import SketchAppReader
    >>> PATH = '../Test/' 
    >>> testFileNames = (
    ...     PATH+'TestImage.sketch',
    ...     PATH+'TestRectangles.sketch',
    ...     PATH+'TestStar.sketch',
    ...     PATH+'TestPolygon.sketch',
    ...     PATH+'TestOval.sketch',
    ...     PATH+'TestABC.sketch',
    ... )
    >>> for readPath in testFileNames:
    ...     reader = SketchAppReader()
    ...     skf1 = reader.read(readPath)
    ...     writePath = readPath.replace('.sketch', 'Write.sketch')
    ...     writer = SketchAppWriter()
    ...     writer.write(writePath, skf1)
    ...     skf2 = reader.read(writePath)
    ...     result = sketchCompare(skf1, skf2) # Should not give any differences
    ...     if result:
    ...         print('--- Difference ---', readPath)
    ...         for error in result:
    ...             if error:
    ...                 print(error)
    >>> sketchCompare('_export/SaveWrite.sketch', '_export/Save.sketch')
    """
    if result is None:
        result = []
    if isinstance(sketchFile1, str):
        reader = SketchAppReader() 
        sketchFIle1 = reader.read(sketchFile1)
    if isinstance(sketchFile2, str):
        reader = SketchAppReader() 
        sketchFIle2 = reader.read(sketchFile1)
    _compare(sketchFile1, sketchFile2, result)

    return result

def prettyPrint(d, name=None, result=None, tab=0):
    """
    >>> from sketchappreader import SketchAppReader
    >>> testFileNames = (
    ...     #'TestImage.sketch',
    ...     'TestRectangles.sketch',
    ...     #'TestStar.sketch',
    ...     #'TestPolygon.sketch',
    ...     #'TestOval.sketch',
    ...     #'TestABC.sketch',
    ... )
    >>> for fileName in testFileNames:
    ...     result = []
    ...     reader = SketchAppReader()
    ...     readPath = '../Test/' + fileName
    ...     skf = reader.read(readPath)
    ...     result = prettyPrint(skf)
    """
    if result is None:
        result = []
    if isinstance(d, SketchBase):
        result.append('\t'*tab + str(d))
        for attrName in sorted(d.ATTRS.keys()):
            if hasattr(d, attrName):
                prettyPrint(getattr(d, attrName), attrName, result, tab+1)
        if hasattr(d, 'layers'):
            for layer in d.layers:
                prettyPrint(layer, 'layers', result, tab+1)
    elif isinstance(d, dict):
        result.append('\t'*tab + name + '{%d}' % len(d))
        for key, value in sorted(d.items()):
            prettyPrint(value, key, result, tab+1)
    elif isinstance(d, (list, tuple)):
        result.append('\t'*tab + '%s[%d]' % (name, len(d)))
        for dd in d:
            prettyPrint(dd, name, result, tab+1)
    else:
        result.append('\t'*tab + name + ': ' + str(d))

    return result

if __name__ == '__main__':
    import doctest
    import sys
    sys.exit(doctest.testmod()[0])