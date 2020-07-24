#!/usr/bin/env python3

# Author: Maciej Dobrzynski, Instutute of Cell Biology, University of Bern, Switzerland
# Date: July 2020
#
# Make a dzi pyramid from images in a specified path:
# - find images in a specified folder, param -indir,
# - combine them into a large montage, where the param -griddim specifies grid dimensions,
# - make a DeepZoom pyramid tiling in a folder, -outdir with dzi file named according to -outfile.
#
# OUTPUT
# A DZI file and the corresponding tiles are saved in a specified output folder
# (-o, -outdir). The core name of the DZI file is based on the input (-f, -outfile).
#
# Script's input params allow to specify the format of the grid,
# e.g. -p 3 4
#
# To view the pyramid use the OpenSeadragon (https://openseadragon.github.io/docs/) viewer.

import os, argparse
from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np


####
## This section contains the code from: https://github.com/openzoom/deepzoom.py
##
## Python Deep Zoom Tools
##
## Copyright (c) 2008-2019, Daniel Gasienica <daniel@gasienica.ch>
## Copyright (c) 2008-2011, OpenZoom <http://openzoom.org/>
## Copyright (c) 2010, Boris Bluntschli <boris@bluntschli.ch>
## Copyright (c) 2008, Kapil Thangavelu <kapil.foss@gmail.com>
## All rights reserved.

import io
import math
import os
import shutil
from urllib.parse import urlparse
import sys
import time
import urllib.request
import warnings
import xml.dom.minidom

from collections import deque


NS_DEEPZOOM = "http://schemas.microsoft.com/deepzoom/2008"

Image.MAX_IMAGE_PIXELS = None
DEFAULT_RESIZE_FILTER = Image.ANTIALIAS
DEFAULT_IMAGE_FORMAT = "png"

RESIZE_FILTERS = {
    "cubic": Image.CUBIC,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
    "nearest": Image.NEAREST,
    "antialias": Image.ANTIALIAS,
}

IMAGE_FORMATS = {
    "jpg": "jpg",
    "png": "png",
}


class DeepZoomImageDescriptor(object):
    def __init__(
        self,
        width=None,
        height=None,
        tile_size=254,
        tile_overlap=1,
        tile_format="png"
    ):
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.tile_overlap = tile_overlap
        self.tile_format = tile_format
        self._num_levels = None



    def save(self, destination):
        """Save descriptor file."""
        file = open(destination, "wb")
        doc = xml.dom.minidom.Document()
        image = doc.createElementNS(NS_DEEPZOOM, "Image")
        image.setAttribute("xmlns", NS_DEEPZOOM)
        image.setAttribute("TileSize", str(self.tile_size))
        image.setAttribute("Overlap", str(self.tile_overlap))
        image.setAttribute("Format", str(self.tile_format))
        size = doc.createElementNS(NS_DEEPZOOM, "Size")
        size.setAttribute("Width", str(self.width))
        size.setAttribute("Height", str(self.height))
        image.appendChild(size)
        doc.appendChild(image)
        descriptor = doc.toxml(encoding="UTF-8")
        file.write(descriptor)
        file.close()

    @classmethod
    def remove(self, filename):
        """Remove descriptor file (DZI) and tiles folder."""
        _remove(filename)

    @property
    def num_levels(self):
        """Number of levels in the pyramid."""
        if self._num_levels is None:
            max_dimension = max(self.width, self.height)
            self._num_levels = int(math.ceil(math.log(max_dimension, 2))) + 1
        return self._num_levels

    def get_scale(self, level):
        """Scale of a pyramid level."""
        assert 0 <= level and level < self.num_levels, "Invalid pyramid level"
        max_level = self.num_levels - 1
        return math.pow(0.5, max_level - level)

    def get_dimensions(self, level):
        """Dimensions of level (width, height)"""
        assert 0 <= level and level < self.num_levels, "Invalid pyramid level"
        scale = self.get_scale(level)
        width = int(math.ceil(self.width * scale))
        height = int(math.ceil(self.height * scale))
        return (width, height)

    def get_num_tiles(self, level):
        """Number of tiles (columns, rows)"""
        assert 0 <= level and level < self.num_levels, "Invalid pyramid level"
        w, h = self.get_dimensions(level)
        return (
            int(math.ceil(float(w) / self.tile_size)),
            int(math.ceil(float(h) / self.tile_size)),
        )

    def get_tile_bounds(self, level, column, row):
        """Bounding box of the tile (x1, y1, x2, y2)"""
        assert 0 <= level and level < self.num_levels, "Invalid pyramid level"
        offset_x = 0 if column == 0 else self.tile_overlap
        offset_y = 0 if row == 0 else self.tile_overlap
        x = (column * self.tile_size) - offset_x
        y = (row * self.tile_size) - offset_y
        level_width, level_height = self.get_dimensions(level)
        w = self.tile_size + (1 if column == 0 else 2) * self.tile_overlap
        h = self.tile_size + (1 if row == 0 else 2) * self.tile_overlap
        w = min(w, level_width - x)
        h = min(h, level_height - y)
        return (x, y, x + w, y + h)

class ImageCreator(object):
    """Creates Deep Zoom images."""

    def __init__(
        self,
        tile_size=254,
        tile_overlap=1,
        tile_format="png",
        image_quality=0.8,
        resize_filter=None,
        copy_metadata=False,
    ):
        self.tile_size = int(tile_size)
        self.tile_format = tile_format
        self.tile_overlap = _clamp(int(tile_overlap), 0, 10)
        self.image_quality = _clamp(image_quality, 0, 1.0)

        if not tile_format in IMAGE_FORMATS:
            self.tile_format = DEFAULT_IMAGE_FORMAT
        self.resize_filter = resize_filter
        self.copy_metadata = copy_metadata

    def get_image(self, level):
        """Returns the bitmap image at the given level."""
        assert (
            0 <= level and level < self.descriptor.num_levels
        ), "Invalid pyramid level"
        width, height = self.descriptor.get_dimensions(level)
        # don't transform to what we already have
        if self.descriptor.width == width and self.descriptor.height == height:
            return self.image
        if (self.resize_filter is None) or (self.resize_filter not in RESIZE_FILTERS):
            return self.image.resize((width, height), Image.ANTIALIAS)
        return self.image.resize((width, height), RESIZE_FILTERS[self.resize_filter])

    def tiles(self, level):
        """Iterator for all tiles in the given level. Returns (column, row) of a tile."""
        columns, rows = self.descriptor.get_num_tiles(level)
        for column in range(columns):
            for row in range(rows):
                yield (column, row)

    def create(self, source, destination):
        """Creates Deep Zoom image from source file and saves it to destination."""

        # Open the source image for DZI tiling from a file
        #self.image = Image.open(safe_open(source))

        # The source image for DZI tiling is a PIL.Image objects
        self.image = source
        width, height = self.image.size

        self.descriptor = DeepZoomImageDescriptor(
            width=width,
            height=height,
            tile_size=self.tile_size,
            tile_overlap=self.tile_overlap,
            tile_format=self.tile_format,
        )

        # Create tiles
        image_files = _get_or_create_path(_get_files_path(destination))

        # Parallelization?
        for level in range(self.descriptor.num_levels):

            if (DEB):
                print("Pyramid level %d" % level)

            level_dir = _get_or_create_path(os.path.join(image_files, str(level)))
            level_image = self.get_image(level)

            for (column, row) in self.tiles(level):

                if (DEB):
                    print("Pyramid col x row: %d %d" % (column, row))

                bounds = self.descriptor.get_tile_bounds(level, column, row)
                tile = level_image.crop(bounds)
                format = self.descriptor.tile_format
                tile_path = os.path.join(level_dir, "%s_%s.%s" % (column, row, format))
                tile_file = open(tile_path, "wb")

                if self.descriptor.tile_format == "jpg":
                    jpeg_quality = int(self.image_quality * 100)
                    tile.save(tile_file, "JPEG", quality=jpeg_quality)
                else:
                    png_compress = round((1 - self.image_quality)*10)
                    tile.save(tile_file, compress_level = png_compress)

        # Create descriptor
        self.descriptor.save(destination)


def _get_or_create_path(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def _get_files_path(path):
    return os.path.splitext(path)[0] + "_files"

def _clamp(val, min, max):
    if val < min:
        return min
    elif val > max:
        return max
    return val

## end of section from: https://github.com/openzoom/deepzoom.py
####


def parseArguments():
        # Create argument parser
        parser = argparse.ArgumentParser()

        # Positional mandatory arguments
        parser.add_argument(
                'indir',
                help='Input folder with images. Mandatory!',
                type=str)

        # Optional arguments
        parser.add_argument(
                '-v',
                '--verbose',
                help='Verbose, more output.',
                default=False,
                action="store_true")

        parser.add_argument(
                '-f',
                '--outfile',
                help='Name of the output DZI file, default \"dzi\"',
                type=str,
                default='dzi')

        parser.add_argument(
                '-o',
                '--outdir',
                help='Output folder to put DZI tiling, default dzi',
                type=str,
                default='dzi')

        parser.add_argument(
                '-g',
                '--griddim',
                help='Grid dimensions. Provide two integers separated by a white space; default 3x3',
                nargs=2,
                type=int,
                default=(3, 3))

        parser.add_argument(
                '-m',
                '--imdim',
                help='Image dimensions. Provide two integers separated by a white space; default 1024x1024',
                nargs=2,
                type=int,
                default=(1024, 1024))

        parser.add_argument(
                '-x',
                '--imext',
                help='File extension of the image to process, default png',
                type=str,
                default='png')

        parser.add_argument(
                '-r',
                '--cores',
                help='Number of cores for multiprocessing, default 4 (NOT USED)',
                type=int,
                default=4)

        parser.add_argument(
                '-t',
                '--tilesz',
                help='Size of DeepZoom tiles, default 254',
                type=int,
                default=254)

        parser.add_argument(
                '-q',
                '--imquality',
                help='Image quality (0.1 - 1) for JPG or compression level for PNG, default 0.8.',
                type=float,
                default=0.8)

        # Parse arguments
        args = parser.parse_args()
        args.griddim = tuple(args.griddim)
        args.imdim = tuple(args.imdim)

        return args


if __name__ == "__main__":

    args = parseArguments()

    # Global constants
    if args.verbose:
        DEB=1
    else:
        DEB=0

    # Dimensions of an image matrix
    gridWidth, gridHeight = args.griddim

    # dimensions of the poster image
    imWidth, imHeight = args.imdim

    # file extension of the input image file
    imExt = args.imext

    # directory with input image files
    imDir = args.indir

    # Raw print arguments
    if (DEB):
        print("You are running the script with arguments: ")
        for a in args.__dict__:
            print(str(a) + ': ' + str(args.__dict__[a]))

        print('')

    padding = 10 #pixels; padding between images

    # Parameters of the input image
    imDepthIn  = 2**8-1

    # Parameters of the output image
    imDepthOut = 2**8-1
    imMode = 'RGB' # 3x8-bit pixels (https://pillow.readthedocs.io/en/stable/handbook/concepts.html#concept-modes)


    # Initialisation

    gridCol = range(0, gridWidth)
    gridRow = range(0, gridHeight)

    imGridWidth  = int(imWidth*gridWidth  + padding*(gridWidth-1))
    imGridHeight = int(imHeight*gridHeight + padding*(gridHeight-1))

    labelWellPosX = round(imWidth * 0.46)
    labelWellPosY = 20

    labelFOVcol = 10
    labelWellCol=250
    bgEmptyWell = imDepthOut # color of empty canvas for well montage
    bgEmptyGrid = 10 # color of empty canvas for grid montage

    # font for annotations (UNUSED)
    #myFont = ImageFont.truetype(font='fonts/arial.ttf', size=300)


    # Work

    # create canvas for montage of the entire grid
    imGrid = Image.new(imMode, (imGridWidth, imGridHeight), bgEmptyGrid)

    if (DEB):
        print("Making the montage:")
        print(imGridWidth, "x", imGridHeight, "pixels")

    # all image files for processing
    files = [f for f in os.listdir(imDir) if os.path.isfile(os.path.join(imDir, f)) and f.endswith(imExt)]
    files.sort()

    if (DEB):
        print("\n", len(files), "file(s) found in the input directory")

    # check whether the grid with specified dimensions will contain all input images
    if (len(files) > gridWidth * gridHeight):
        print("\nWarning:\nspecified grid dimensions smaller than the number of images in the input folder.")

    # Iterator over all image files
    iiIm = 0

    for iRow in gridRow:
        for iCol in gridCol:

            if (iiIm < len(files)):
                locImPath = os.path.join(imDir, files[iiIm])

                if (DEB):
                    print('\nTrying file:')
                    print(locImPath)

                # Handle errors if the image file is inaccessible/corrupt
                flagFileExists = os.path.isfile(locImPath) and os.access(locImPath, os.R_OK)
                flagFileOK = True

                try:
                    locIm = Image.open(locImPath)
                except (IOError, SyntaxError, IndexError, ValueError) as e:
                    print('Corrupted file:', locImPath)
                    flagFileOK = False

                # Add image to montage canvas

                gridPosW = iCol * (imWidth + padding)
                gridPosE = gridPosW + imWidth
                gridPosN = iRow * (imHeight + padding)
                gridPosS = gridPosN + imHeight
                bbox = (gridPosW, gridPosN, gridPosE, gridPosS)

                if (DEB):
                    print('\nBounding box for inserting the image into grid canvas:')
                    print(bbox)


                imGrid.paste(locIm, bbox)

            iiIm += 1


    imPathDir = '%s/%s.dzi' % (args.outdir, args.outfile)
    if (DEB):
        print("\nMaking DeepZoom tiling in:\n" + imPathDir)


    creator = ImageCreator(
        tile_size = args.tilesz,
        tile_format = 'png',
        image_quality = args.imquality,
        resize_filter = 'antialias',
    )

    creator.create(imGrid, imPathDir)

    if(DEB):
        print("\nAnalysis finished!\n")
