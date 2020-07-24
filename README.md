# Deep Zoom Poster Viewer

An html-based poster gallery using [DeepZoom](https://en.wikipedia.org/wiki/Deep_Zoom) technology.

## Demo

A [demo](http://macdobry.net/pertzlabposters) web-viewer of a montage of posters created from several PDFs.

## Building blocks

* [Python Deep Zoom Tools](https://github.com/openzoom/deepzoom.py) to generate an image montage and the `dzi` pyramid file/folder structure with png image tiles.
* [OpenSeadragon](https://openseadragon.github.io), an open-source, web-based viewer for high-resolution zoomable images, implemented in pure JavaScript, for desktop and mobile.
* [Flat Design Icon](https://github.com/peterthomet/openseadragon-flat-toolbar-icons) set for the viewer.
* [Python Imaging Library](https://en.wikipedia.org/wiki/Python_Imaging_Library) and [imageio](https://pypi.org/project/imageio/) to read/write images.

## Content

* `scripts/makePosterMontage.py`\
A Python script to convert individual `PNG` image files into a `dzi` pyramid.
* `scripts/procImages.sh`\

A shell script that will:

- convert all PDFs in a selected folder to PNGs using a `convert` command from the [ImageMagick](https://imagemagick.org) package,
- run the `makePosterMontage.py` command to create a `dzi` pyramid,
- copy `index.html` to the folder with the pyramid,
- copy the OpenSeadragon library to the folder with the pyramid.

* `HTML-template`\
An HTML template with a basic viewer and the OpenSeadragon library.

## Usage

Suppose PDF files with posters are located in a `~/posters` folder. To make a `dzi` pyramid montage run:

```
./procImages.sh -i ~/posters/pdf -o ~/posters/png -z ~/posters/dzi
```

The command will create the following in the `~/posters` folder:

* a `png` sub-folder with intermediate PNG images converted from PDFs
* a `dzi` sub-folder with the pyramid montage
* an `index.html` file in the `dzi` folder with a sample viewer. This file points to the `openseadragon` library which, in this case, will also be copied from the `HTML-template` folder. Check here](https://openseadragon.github.io/#download) for the latest version.
