#!/usr/bin/env python3

import os
import sys
from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.PyQt.QtCore import QMetaType
import pathlib as pl
# from PyQt4.QtCore import *
# from PyQt4.QtGui import QApplication
# from PyQt4.QtXml import *


# https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/intro.html#using-pyqgis-in-standalone-scripts


# Supply path to qgis install location
# QgsApplication.prefixPath()
QgsApplication.setPrefixPath("/usr/bin/qgis", True)


# Create a reference to the QgsApplication.  Setting the
# second argument to False disables the GUI.
qgs = QgsApplication([], False)


# Load providers
qgs.initQgis()


# Write your code here to load some layers, use processing

# algorithms, etc.

### Project
project = QgsProject.instance()
print(project.fileName())

project_crs = QgsCoordinateReferenceSystem.fromEpsgId(31370)
project.setCrs(project_crs)


# Read input parameters from GP dialog
qgis_project_path: pl._local.PosixPath = pl.Path(QgsProject.instance().readPath("./"))
save_filename = qgis_project_path/"test.qgs"
check = project.write(str(save_filename))

layers = {}
# gj = "woods"
for gj in ["multi", "annotations",
    "buildings", "garden", "streets", "trails",
    "water", "wetland", "woods"]:

    layer_path: pl._local.PosixPath = qgis_project_path / f"geodata/plantentuin_{gj}.geojson"

    layer: QgsVectorLayer = QgsVectorLayer(path = str(layer_path), baseName = gj)
    assert layer.isValid(), "Layer is not valid!" # should be a better check/raise in production

    QgsProject.instance().addMapLayer(layer)

    layers[gj] = layer




# set extent and refresh
# https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/composer.html#simple-rendering
settings = QgsMapSettings()
extent: QgsRectangle = layers["garden"].extent()
settings.setExtent(extent)


## data layers
layer = QgsVectorLayer("Point", "testing", "memory")
# layer.addAttribute(QgsField("mytext", QMetaType.Type.QString))
data_provider = layer.dataProvider()  # you access the real datasource behind your layer (for instance PostGIS)
data_provider.addAttributes([QgsField("mytext", QMetaType.Type.QString)])
layer.updateFields()  # update your vector layer from the datasource
# layer.commitChanges()  # update your vector layer from the datasource

QgsProject.instance().addMapLayer(layer)

## the viewport does not zoom to the ROI :(
# canvas = iface.mapCanvas()
# canvas.setExtent(extent)
# QgsMapCanvas.zoomToSelected(layers["garden"])

# ## print layouts
# # https://gis.stackexchange.com/a/428066
# # https://gis.stackexchange.com/a/287125
# plm = project.layoutManager()
# # print(dir(plm))
# print(help(plm.addLayout))
# layout = plm.addLayout()#"default") # your layout name
#
# #get reference map
# refmap = layout.referenceMap()
# refmap.setExtent(extent)



check = project.write()

# Finally, exitQgis() is called to remove the

# provider and layer registries from memory
# TODO atexit?
qgs.exitQgis()




# def add_Layers():
#     QGISAPP = QgsApplication(sys.argv, True)
#     QgsApplication.setPrefixPath(r"C:\OSGeo4W\apps\qgis", True)
#     QgsApplication.initQgis()
#     QgsProject.instance().setFileName(strProjetName)
#     print QgsProject.instance().fileName()
#
#
# for file1 in os.listdir(r"C:\myprojects\world"):
#      if file1.endswith('.shp'):
#          layer = QgsVectorLayer(r"C:\myprojects\world"+r"\\"+file1, file1, "ogr")
#          print file1
#          print layer.isValid()
#          # Add layer to the registry
#          QgsMapLayerRegistry.instance().addMapLayer(layer)
#
#
# QgsProject.instance().write()
# QgsApplication.exitQgis()
#
# add_Layers()
