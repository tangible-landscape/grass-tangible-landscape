#!/usr/bin/env bash

set -e

LIBFREENECT2_RELEASE=0.2.0
PCL_RELEASE=1.8.0
NCORES=`nproc --all`
CDIR=`pwd`

# package dependencies
sudo apt-get update && sudo apt-get install -y \
   build-essential cmake pkg-config git wget\
   libusb-1.0-0-dev libturbojpeg0-dev libglfw3-dev \
   libboost-all-dev libeigen3-dev libflann-dev libopencv-dev \
   flex make bison gcc libgcc1 g++ ccache \
   python python-dev \
   python-opengl \
   python-wxversion python-wxtools python-wxgtk3.0 \
   python-dateutil libgsl-dev python-numpy python-pil python-matplotlib python-watchdog\
   wx3.0-headers wx-common libwxgtk3.0-dev \
   libwxbase3.0-dev   \
   libncurses5-dev \
   zlib1g-dev gettext \
   libtiff5-dev libpnglite-dev \
   libcairo2 libcairo2-dev \
   sqlite3 libsqlite3-dev \
   libpq-dev \
   libreadline-dev libfreetype6-dev \
   libfftw3-3 libfftw3-dev \
   libboost-thread-dev libboost-program-options-dev liblas-c-dev \
   resolvconf \
   subversion \
   libavutil-dev ffmpeg2theora \
   libffmpegthumbnailer-dev \
   libavcodec-dev \
   libxmu-dev \
   libavformat-dev libswscale-dev \
   checkinstall \
   libglu1-mesa-dev libxmu-dev \
   ghostscript \
   libproj-dev proj-data proj-bin \
   libgeos-dev \
   libgdal-dev python-gdal gdal-bin \
   liblas-bin liblas-dev
   
 
# libfreenect2
wget https://github.com/OpenKinect/libfreenect2/archive/v${LIBFREENECT2_RELEASE}.tar.gz
tar xvf v${LIBFREENECT2_RELEASE}.tar.gz
rm v${LIBFREENECT2_RELEASE}.tar.gz
cd libfreenect2-${LIBFREENECT2_RELEASE}
mkdir build && cd build
cmake ..
make
sudo make install
sudo cp ../platform/linux/udev/90-kinect2.rules /etc/udev/rules.d/
cd ../..

# PCL
wget https://github.com/PointCloudLibrary/pcl/archive/pcl-${PCL_RELEASE}.tar.gz
tar xvf pcl-${PCL_RELEASE}.tar.gz
rm pcl-${PCL_RELEASE}.tar.gz
cd pcl-pcl-${PCL_RELEASE}
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j${NCORES}
sudo make -j2 install
cd ../..

# GRASS GIS
svn checkout https://svn.osgeo.org/grass/grass/branches/releasebranch_7_6 grass76_release
cd grass76_release
CFLAGS="-O2 -Wall" LDFLAGS="-s" ./configure \
  --enable-largefile=yes \
  --with-nls \
  --with-cxx \
  --with-readline \
  --with-pthread \
  --with-proj-share=/usr/share/proj \
  --with-geos=/usr/bin/geos-config \
  --with-wxwidgets \
  --with-cairo \
  --with-opengl-libs=/usr/include/GL \
  --with-freetype=yes --with-freetype-includes="/usr/include/freetype2/" \
  --with-sqlite=yes \
  --with-odbc=no \
  --with-liblas=yes --with-liblas-config=/usr/bin/liblas-config
make -j${NCORES}
sudo make install
cd ..

# r.in.kinect
git clone https://github.com/tangible-landscape/r.in.kinect.git
cd r.in.kinect
make MODULE_TOPDIR=../grass76_release
make install MODULE_TOPDIR=../grass76_release
cd ..

# TL plugin
# could use g.extension instead:
# g.extension g.gui.tangible url=github.com/tangible-landscape/grass-tangible-landscape
# this is for the development of grass-tangible-landscape
git clone https://github.com/tangible-landscape/grass-tangible-landscape.git
cd grass-tangible-landscape
make MODULE_TOPDIR=../grass76_release
make install MODULE_TOPDIR=../grass76_release
cd ..

# set up GRASS GIS icon in dash
cat << EOF > /tmp/grass.desktop
[Desktop Entry]
Version=1.0
Name=GRASS GIS
Comment=Start GRASS GIS
Exec=${CDIR}/grass76_release/bin.x86_64-pc-linux-gnu/grass74
Icon=${CDIR}/grass76_release/dist.x86_64-pc-linux-gnu/share/icons/hicolor/scalable/apps/grass.svg
Terminal=true
Type=Application
Categories=GIS;Application;
EOF
sudo mv /tmp/grass.desktop /usr/share/applications/grass.desktop
