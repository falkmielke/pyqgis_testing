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



# https://gis.stackexchange.com/a/346374
# layer = QgsProject.instance().mapLayersByName('monuments')[0]
# ews = layer.editorWidgetSetup(layer.fields().indexFromName("mytext"))
# print("Type:", ews.type())
# print("Config:", ews.config())

widget_library = {}

widget_library["multiline"] = QgsEditorWidgetSetup(
    'TextEdit', {
        'IsMultiline': True,
        'UseHtml': False
    })

widget_library["attachment"] = QgsEditorWidgetSetup(
    'ExternalResource', {
        'FileWidget': True,
        'DocumentViewer': 0,
        'RelativeStorage': 0,
        'StorageMode': 0,
        'DocumentViewerHeight': 0,
        'FileWidgetButton': True,
        'DocumentViewerWidth': 0,
        'FileWidgetFilter': ''
    })

widget_library["checkbox"] = QgsEditorWidgetSetup(
    'CheckBox', {
        'AllowNullState': True,
        # 'CheckedState': '',
        'TextDisplayMethod': 0,
        # 'UncheckedState': ''
    })

widget_library["date"] = QgsEditorWidgetSetup(
    'DateTime', {
        'allow_null': True,
        'calendar_popup': True,
        'display_format': 'd/M/yy',
        'field_format': 'yyyyMMdd',
        'field_format_overwrite': False,
        'field_iso_format': False
    })

widget_library["image"] = QgsEditorWidgetSetup(
    'ExternalResource', {
        'DocumentViewer': 0,
        'DocumentViewerHeight': 0,
        'DocumentViewerWidth': 0,
        'FileWidget': True,
        'FileWidgetButton': True,
        'FileWidgetFilter': '',
        'PropertyCollection': {
            'name': None,
            'properties': {},
            'type': 'collection'
        },
        'RelativeStorage': 1,
        'StorageAuthConfigId': False,
        'StorageMode': 0,
        'StorageType': None
 })


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


def ZoomTo(lyr):
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

    def __init__(self, project, \
                 name: str = "", \
                 provider: str = None, \
                 fields: list = [], \
                 verbose = False
                 ):
        ## data layers
        self.project = project
        self.name = name
        self.provider = provider
        if self.provider is None:
            self.provider = "memory"
        self.layer = QgsVectorLayer("Point", self.name, self.provider)
        self.fields = fields
        self.verbose = verbose

        # make sure elements are linked
        LinkElements(self.fields)

        self.CreateFields()

        self.CreateForm()


    def CreateFields(self):

        # access the real datasource behind your layer (for instance PostGIS)
        self.data_provider = self.layer.dataProvider()
        if (self.fields is None) or (len(self.fields) < 1):
            print("QgisFormLayer `fields` must be a list of form elements" +
                          " to create `QgsField`s.")

        ## (I) Add all fields
        self.data_provider.addAttributes([ \
                QgsField(element["label"], element["dtype"]) \
                for element in self.fields \
                if not element.is_container \
            ])
        self.layer.updateFields()  # update your vector layer from the datasource
        # layer.commitChanges()  # update your vector layer from the datasource

        # find fields back by index
        field_lookup = self.layer.fields()
        self.fldidx = lambda field_name: field_lookup.indexFromName(field_name)

        if self.verbose:
            print(["(" + str(self.fldidx(element["label"])) + ") " \
                       + element["label"] \
                    for element in self.fields \
                    if not element.is_container])




    def CreateForm(self):

        ## (II) form configuration
        self.form_config = self.layer.editFormConfig()
        self.form_config.setLayout(Qgis.AttributeFormLayout(1)) # drag&drop
        self.root_container = self.form_config.invisibleRootContainer()

        # remove all existing items
        self.root_container.clear()



        ## create containers
        self.containers = {}
        for container in [element for element in self.fields if element.is_container]:

            ## a container which contain more fields
            label = container["label"]
            parent = container.parent_link
            if parent is None:
                parent = self.root_container

            self.containers[label] = QgsAttributeEditorContainer(name = label, parent = parent)
            container.link_q = self.containers[label]

            if self.verbose:
                print(f'created container "{label}": ', str(container.link_q))

            # visibility
            condition = container["condition"]
            if condition is not None:
                visexp = QgsExpression(condition)
                self.containers[label].setVisibilityExpression(QgsOptionalExpression(visexp))


        ## https://qgis.org/pyqgis/3.40/core/QgsAttributeEditorElement.html
        ## https://gis.stackexchange.com/q/444315


        ## fill with elements
        for field in [element for element in self.fields if not element.is_container]:
            label = field["label"]
            parent = field.parent_link
            if parent is None:
                parent_q = self.root_container
            else:
                parent_q = parent.link_q

            self.layer.setEditorWidgetSetup(self.fldidx(label), field["widget"])
            self.form_config.setLabelOnTop(self.fldidx(label), True)

            new_field = QgsAttributeEditorField( \
                name = label, \
                idx = self.fldidx(label), \
                parent = parent_q \
            )
            field.link_q = new_field

            if self.verbose:
                print(f'created field "{label}": ', str(field.link_q))

        ## link the children in order of appearance
        for element in self.fields:
            if element.parent_link is None:
                self.root_container.addChildElement(element.link_q)

                if self.verbose:
                    print(f"adding {element['label']} to root.")
            else:
                element.parent_link.link_q.addChildElement(element.link_q)
                if self.verbose:
                    print(f"adding {element['label']} to {element.parent_link['label']}.")


        ## write form
        self.layer.setEditFormConfig(self.form_config)
        self.layer.updateFields()
        self.project.project.addMapLayer(self.layer)

# Finally, exitQgis() is called to remove the

# provider and layer registries from memory
# TODO atexit?


class FormElement(dict):
    def __init__(self, label, dtype = None, parent = None,
            condition = None, widget = None
        ):
        self["label"] = label
        if dtype is not None:
            self["dtype"] = dtype
        self["parent"] = parent

        # flag containers
        self.is_container = None

        # to be filled in a later step
        self.parent_link = None # link to parent
        self.children = [] # link to children
        self.link_q = None # link to the qgis form object


    def Link(self, structure):
        labels = [element["label"] for element in structure]

        # find the parent by label
        if self["parent"] in labels:
            self.parent_link = structure[labels.index(self["parent"])]

        if self.parent_link is not None:
            # append self to the children of the parent
            self.parent_link.children.append(self)




class FormWidget(FormElement):
    def __init__(self, label, dtype, widget, parent = None):
        super(FormWidget, self).__init__(label = label, dtype = dtype, parent = parent)
        self["widget"] = widget
        self.is_container = False

class FormContainer(FormElement):
    def __init__(self, label, condition = None, parent = None):
        super(FormContainer, self).__init__(label = label, parent = parent)
        self["condition"] = condition
        self.is_container = True

def LinkElements(form):
    # clear links
    for element in form:
        element.children = []
        element.parent_link = None
    # re-link
    for element in form:
        element.Link(form)


if __name__ == "__main__":
    project = QgisProject("test.qgs")
    data_layers = AddDataLayers(project)
    # ZoomTo(data_layers["garden"])

    form_structure = [
        FormWidget("mycategory", dtype = QMetaType.Type.QString, \
                    widget = QgsEditorWidgetSetup('ValueMap', {'map': {'Red': 'R', 'Green': 'G', 'Blue': 'B'}}) \
                    ), \
        \
        FormContainer("Red habitat", condition = "\"mycategory\" = 'R'"), \
        FormWidget("red subtype", dtype = QMetaType.Type.Bool, \
                    widget = widget_library["checkbox"], \
                    parent = "Red habitat"), \
        FormContainer("Red A", condition = "\"red subtype\" = TRUE"), \
        FormWidget("text A", dtype = QMetaType.Type.QString, \
                    widget = widget_library["multiline"], \
                    parent = "Red A"), \
        FormContainer("Red B", condition = "\"red subtype\" = FALSE"), \
        FormWidget("text B", dtype = QMetaType.Type.QString, \
                    widget = widget_library["multiline"], \
                    parent = "Red B"), \
        \
        FormContainer("Green habitat", condition = "\"mycategory\" = 'G'"), \
        FormWidget("time", dtype = QMetaType.Type.Int, \
                    widget = widget_library["date"], \
                    parent = "Green habitat"), \
        \
        FormContainer("Blue habitat", condition = "\"mycategory\" = 'B'"), \
        FormWidget("photo", dtype = QMetaType.Type.QString, \
                    widget = widget_library["image"], \
                    parent = "Blue habitat"), \
        \
        FormWidget("done", dtype = QMetaType.Type.Bool, \
                    widget = widget_library["checkbox"], \
                    ) \
    ]

    # LinkElements(form_structure)
    # print([f"{(frm.parent_link['label']+'/') if frm.parent_link is not None else ""}{frm['label']}"
    #        for frm in form_structure])


    test_form = QgisFormLayer( \
        project, \
        name = "monuments", \
        fields = form_structure, \
        verbose = True \
        )


    check = project.Save()
    project.app.exitQgis()


# TODO
# - zoom to layer
# - shows CRS trafo question on opening?
# - does geometry (coords) come to form layer automatically?
# - more form widget types
# - test on qfield app
# - DateTime of creation
# - layer colors and symbols
