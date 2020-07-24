#!/usr/bin/env bash

usage="Convert pdf files to png and create a DZI pyramid.
Usage:
$(basename "$0") [-h] [-r char] [-c int] [-m int]
where:
        -h | --help             Show this Help text.
        -i | --dirin            Path to input folder with PDF files (default .).
        -o | --diroutpng        Path to output folder with PNG files (default png).
        -z | --diroutdzi        Path to output folder with DZI files (default dzi).
        -w | --imwidth          With of the output image in pixels (default 1000).
        -e | --imheight         Height of the output image in pixels (default 1000).
        -d | --imdens           DPI density to rneder PDF into PNG (default 300).
        -b | --imdepth          Bit depth of the output image (default 8).
        -c | --ncores           Number of cores for PDF>PNG conversion (default 2; UNUSED).
        -t | --test             Test mode."

E_BADARGS=85

if [ ! -n "$1" ]
then
  echo "$usage"
  exit $E_BADARGS
fi

# default path to root directory
DIRIN=.

DIROUTPNG=png
DIROUTDZI=dzi

# width and height of the output image
IMW=1000
IMH=1000

IMDENS=300
IMDEPTH=8

# Number of cores for PDF>PNG conversion
NC=2

# Flag for test mode
TST=0

# read arguments
TEMP=`getopt -o thi:o:z:w:e:d:b:c: --long test,help,dirin:,dirout:,diroutdzi:,imheight:,imwidth:,imdens:,imdepth:,ncores: -n 'procImages.sh' -- "$@"`
eval set -- "$TEMP"


# extract options and their arguments into variables.
# Tutorial at:
# http://www.bahmanm.com/blogs/command-line-options-how-to-parse-in-bash-using-getopt

while true ; do
    case "$1" in
        -t|--test) TST=1 ; shift ;;
        -h|--help) echo "$usage"; exit ;;
        -i|--dirin)
            case "$2" in
                "") shift 2 ;;
                *) DIRIN=$2 ; shift 2 ;;
            esac ;;
        -o|--diroutpng)
            case "$2" in
                "") shift 2 ;;
                *) DIROUTPNG=$2 ; shift 2 ;;
            esac ;;
        -z|--diroutdzi)
            case "$2" in
                "") shift 2 ;;
                *) DIROUTDZI=$2 ; shift 2 ;;
            esac ;;
        -w|--imwidth)
            case "$2" in
                "") shift 2 ;;
                *) IMW=$2 ; shift 2 ;;
            esac ;;
        -e|--imheight)
            case "$2" in
                "") shift 2 ;;
                *) IMH=$2 ; shift 2 ;;
            esac ;;
        -d|--imdens)
            case "$2" in
                "") shift 2 ;;
                *) IMDENS=$2 ; shift 2 ;;
            esac ;;
        -b|--imdepth)
            case "$2" in
                "") shift 2 ;;
                *) IMDEPTH=$2 ; shift 2 ;;
            esac ;;
        -c|--ncores)
            case "$2" in
                "") shift 2 ;;
                *) NC=$2 ; shift 2 ;;
            esac ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done


if [ $TST -eq 1 ]; then
  echo "Test mode ON, images will NOT be processed!"

  for ii in ${DIRIN}/*.pdf; do
    fout=`echo ${ii} | sed -e "s|.*/||"`
    fout=${DIROUTPNG}/${fout%.*}.png

    echo ""
    echo "Converting ${ii}"
    echo "to ${fout}"
  done
else
  echo "Test mode OFF, processing images in $DIRIN"
  echo "Step 1: converting PDFs to PNGs"
  echo ""

  mkdir -p ${DIROUTPNG}

  if [ $? -ne 0 ] ; then
      echo "Error: could not create ${DIROUTPNG} fodler for intermediate PNGs"
      exit 2
  else
      echo "Created ${DIROUTPNG} folder for intermediate PNGs"
  fi

(
  for ii in ${DIRIN}/*.pdf; do
    # for parallel version of this loop
    #((k=k%NC)); ((k++==0)) && wait

    fout=`echo ${ii} | sed -e "s|.*/||"`
    fout=${DIROUTPNG}/${fout%.*}.png

    echo ""
    echo "Converting ${ii}"
    echo "to ${fout}"

    convert \
    -resize ${IMW}x${IMH} \
    -background white \
    -gravity center \
    -extent ${IMW}x${IMH} \
    -density ${IMDENS} \
    -depth ${IMDEPTH} "${ii}" "${fout}"
  done
)

  echo ""
  echo "Step 2: creating DZI in ${DIROUTDZI} from files in ${DIROUTPNG}"
  echo ""

  ./makePosterMontage.py -v -g 3 3 -m ${IMW} ${IMH} -o ${DIROUTDZI} ${DIROUTPNG}

  echo ""
  echo "Step 3: creating index.html in ${DIROUTDZI} from template"

  cp ../HTML-template/index.html ${DIROUTDZI}/.

  if [ $? -ne 0 ] ; then
      echo "Could not copy index.html to ${DIROUTDZI}"
      exit 2
  else
      echo "Created index.html in ${DIROUTDZI}"
  fi

  echo ""
  echo "Step 4: copying OpenSeadragon to ${DIROUTDZI}"

  cp -R ../HTML-template/openseadragon ${DIROUTDZI}/.

  if [ $? -ne 0 ] ; then
      echo "Could not copy OpenSeadragon to ${DIROUTDZI}"
      exit 2
  else
      echo "Copied OpenSeadragon to ${DIROUTDZI}"
  fi

fi
