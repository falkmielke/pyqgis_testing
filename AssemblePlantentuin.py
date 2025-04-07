#!/usr/bin/env python3

import os
import sys
from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.PyQt.QtCore import QMetaType, QVariant
import pathlib as pl
# from PyQt4.QtCore import *
# from PyQt4.QtGui import QApplication
# from PyQt4.QtXml import *



class QgisProject(object):

    def __init__(self, filename):
        self.filename = filename # "test.qgs"
        self.InitQgisApplication()
        self.CreateQgisProject()
        self.Save()

    def InitQgisApplication(self):
        # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/intro.html#using-pyqgis-in-standalone-scripts

        # Supply path to qgis install location
        # QgsApplication.prefixPath()
        QgsApplication.setPrefixPath("/usr/bin/qgis", True)


        # Create a reference to the QgsApplication.  Setting the
        # second argument to False disables the GUI.
        self.app = QgsApplication([], False)


        # Load providers
        self.app.initQgis()


    def CreateQgisProject(self):
        ### Project
        self.project = QgsProject.instance()
        self.path: pl._local.PosixPath = pl.Path(self.project.readPath("./"))
        # print(project.fileName())

        project_crs = QgsCoordinateReferenceSystem.fromEpsgId(31370)
        self.project.setCrs(project_crs)


    def Save(self):
        # Read input parameters from GP dialog
        self.save_filename = self.path/self.filename
        check = self.project.write(str(self.save_filename))


def AddDataLayers(project):
    layers = {}
    # gj = "woods"
    for gj in ["multi", "annotations",
        "buildings", "garden", "streets", "trails",
        "water", "wetland", "woods"]:

        layer_path: pl._local.PosixPath = project.path / f"geodata/plantentuin_{gj}.geojson"

        layer: QgsVectorLayer = QgsVectorLayer(path = str(layer_path), baseName = gj)
        assert layer.isValid(), "Layer is not valid!" # should be a better check/raise in production

        project.project.addMapLayer(layer)

        layers[gj] = layer

    return layers


def ExtentByLayer(lyr):
    # set extent and refresh
    # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/composer.html#simple-rendering
    settings = QgsMapSettings()
    extent: QgsRectangle = lyr.extent()
    settings.setExtent(extent)

    # canvas = QgsMapCanvas()
    # canvas.show()

    # canvas.setExtent(extent)
    # canvas.refresh()


class QgisFormLayer(object):

    def __init__(self, project):
        ## data layers
        self.project = project
        self.layer = QgsVectorLayer("Point", "testing", "memory")
        self.CreateFields()
        self.CreateForm()


    def CreateFields(self):
        # access the real datasource behind your layer (for instance PostGIS)
        self.data_provider = self.layer.dataProvider()

        ## (I) Add all fields
        self.data_provider.addAttributes([ \
            # QgsField("mycategory", QMetaType.Type.Int), \
            QgsField("mycategory", QMetaType.Type.QString), \
            QgsField("mytext", QMetaType.Type.QString), \
            ])
        self.layer.updateFields()  # update your vector layer from the datasource
        # layer.commitChanges()  # update your vector layer from the datasource

        # find fields back by index
        fields = self.layer.fields()
        self.fldidx = lambda field_name: fields.indexFromName(field_name)


    def CreateForm(self):

        ## (II) form configuration
        self.form_config = self.layer.editFormConfig()
        self.form_config.setLayout(Qgis.AttributeFormLayout(1)) # drag&drop
        self.root_container = self.form_config.invisibleRootContainer()

        # remove all existing items
        self.root_container.clear()


        ## https://qgis.org/pyqgis/3.40/core/QgsAttributeEditorElement.html
        ## https://gis.stackexchange.com/q/444315
        field_name = "mycategory"
        # widget_setup = QgsEditorWidgetSetup('UniqueValues', {'Editable': True})
        category_map = {'Red': 'R', 'Green': 'G', 'Blue': 'B'}
        widget_setup = QgsEditorWidgetSetup('ValueMap', {'map': category_map})

        self.layer.setEditorWidgetSetup(self.fldidx(field_name), widget_setup)
        self.form_config.setLabelOnTop(self.fldidx(field_name), True)

        field1 = QgsAttributeEditorField(name = field_name, idx = self.fldidx(field_name), parent = self.root_container)

        self.root_container.addChildElement(field1)


        ## a container with more fields
        container1 = QgsAttributeEditorContainer(name = "details", parent = self.root_container)

        # visibility
        visexp = QgsExpression("\"mycategory\" = 'R'")
        container1.setVisibilityExpression(QgsOptionalExpression(visexp))


        field_name = "mytext"
        # widget_setup = QgsEditorWidgetSetup('UniqueValues', {'Editable': True})
        widget_setup = QgsEditorWidgetSetup('TextEdit', {'IsMultiline': True, 'UseHtml': False})

        self.layer.setEditorWidgetSetup(self.fldidx(field_name), widget_setup)
        self.form_config.setLabelOnTop(self.fldidx(field_name), True)

        field2 = QgsAttributeEditorField(name = field_name, idx = self.fldidx(field_name), parent = container1)

        container1.addChildElement(field2)


        self.root_container.addChildElement(container1)


        ## write form
        self.layer.setEditFormConfig(self.form_config)
        self.layer.updateFields()
        self.project.project.addMapLayer(self.layer)

# Finally, exitQgis() is called to remove the

# provider and layer registries from memory
# TODO atexit?


if __name__ == "__main__":
    project = QgisProject("test.qgs")
    data_layers = AddDataLayers(project)
    ExtentByLayer(data_layers["garden"])

    form = QgisFormLayer(project)

    check = project.Save()
    project.app.exitQgis()


# TODO
# - application path not initialized
# - zoom to layer
# - shows CRS question on opening
# - does geometry (coords) come to form layer automatically?
