#!/usr/bin/env python3

import os
import sys
from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.PyQt.QtCore import QMetaType, QVariant

import pathlib as pl
import atexit

# custom
import QGISDecisionTrees as QGT


# TODO visibility by Question ( i.e. hide Question container if different outcome within same tab )

# TODO alternating checkboxes https://stackoverflow.com/questions/36281103/change-checkbox-state-to-not-checked-when-other-checkbox-is-checked-pyqt
# TODO get satellite imagery
# TODO extent Belgium?

# TODO DecisionTree adjustment:
#     There are more steps with no predecessor (76, 37, 24) -> now via clades/tabs



# https://gis.stackexchange.com/a/346374
# layer = QgsProject.instance().mapLayersByName('Heidesleutel')[0]
# ews = layer.editorWidgetSetup(layer.fields().indexFromName("0"))
# print("Type:", ews.type())
# print("Config:", ews.config())

widget_catalogue = {}

widget_catalogue["multiline"] = QgsEditorWidgetSetup(
    'TextEdit', {
        'IsMultiline': True,
        'UseHtml': False
    })

widget_catalogue["attachment"] = QgsEditorWidgetSetup(
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

widget_catalogue["checkbox"] = QgsEditorWidgetSetup(
    'CheckBox', {
        'AllowNullState': True,
        # 'CheckedState': '',
        'TextDisplayMethod': 0,
        # 'UncheckedState': ''
    })

widget_catalogue["date"] = QgsEditorWidgetSetup(
    'DateTime', {
        'allow_null': True,
        'calendar_popup': True,
        'display_format': 'd/M/yy',
        'field_format': 'yyyyMMdd',
        'field_format_overwrite': False,
        'field_iso_format': False
    })

widget_catalogue["image"] = QgsEditorWidgetSetup(
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



def AddInfoText(parent, text, label = ""):
    text_element = QgsAttributeEditorTextElement(name = label, parent = parent)
    text_element.setText(text)
    parent.addChildElement(text_element)

def GetTab(clidx):
    return clidx.split(">>")[0]


class QgisProject(object):

    def __init__(self, filename):
        self.filename = filename # "test.qgs"
        self.InitQgisApplication()
        self.CreateQgisProject()
        self.Save()

        atexit.register(self.Exit)

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

    def Exit(self):
        self.app.exitQgis()



def AddDataLayers(project):
    layers = {}
    # gj = "woods"
    layer_list = QgsLayerDefinition() \
        .loadLayerDefinitionLayers("geodata/gmap_sat_molenheide.qlr")
    project.project.addMapLayers(layer_list)

    layers["gmap"] = layer_list


    if False:
        # alternative to load google maps
        # https://gis.stackexchange.com/a/272728
        import requests
        service_url = "mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        service_uri = "type=xyz&zmin=0&zmax=21&url=https://" + requests.utils.quote(service_url)
        tms_layer = iface.addRasterLayer(service_uri, "Google Sat", "wms")
        #lyrs=y - hybrid
        #lyrs=s - sat
        #lyrs=m - road map



    for gj in ["buildings", "points"]:

        layer_path: pl._local.PosixPath = project.path / f"geodata/molenheide_{gj}.geojson"

        layer: QgsVectorLayer = QgsVectorLayer(path = str(layer_path), baseName = gj)
        assert layer.isValid(), "Layer is not valid!" # should be a better check/raise in production

        project.project.addMapLayer(layer)

        layers[gj] = layer


    return layers



class QgisFormDecisionTree(QGT.DecisionTree):
    # The functional combination of a decision tree and a form.
    # Takes a decision tree, copies its content,
    # but provides extra functionality to create a QGIS form.

    def __init__(self, \
                 tree: QGT.DecisionTree, \
                 project: QgisProject, \
                 name: str = "", \
                 provider: str = None, \
                 verbose: bool = False
                 ):

        # Copy tree attributes
        self.CopyTree(tree)

        ## data layers
        self.project = project
        self.name = name
        self.provider = provider
        if self.provider is None:
            self.provider = "memory"

        # initialize an empty layer
        self.layer = QgsVectorLayer("Point", self.name, self.provider)
        self.data_provider = self.layer.dataProvider()
        self.form_config = self.layer.editFormConfig()
        self.form_config.setLayout(Qgis.AttributeFormLayout(1)) # drag&drop

        self.verbose = verbose

        # (II) create answer fields
        self.AssembleAllFields()

        # (I) create recursive container structure (by clades)
        self.CladeContainers()

        # (III) add all nodes to their respective clade
        self.FormNodeForms()

        # (IV) tip nodes: possible classifications
        # will receive extra containers and text
        # hopefully only visible one at a time

        # (V) define container visibility
        # (add checkbox to hide)
        self.SetDynamicVisibilities()

        # Clean up
        self.FinishFormCreation()


    def CopyTree(self, other_tree):
        # we already inherit all the functions of a tree,
        # yet to become a true tree, one must copy all the branches and leaves.

        ot = other_tree

        # bring in all the data variables
        self.meta = ot.meta
        self.clades = ot.clades
        self.steps = ot.steps
        self.root = ot.root

        # copy nodes
        for idx, node in ot.items():
            self[idx] = node


    def AssembleAllFields(self):
        # traverse the tree and grab all which must be decided
        # currently, for each question, one answer is stored (as String)

        # AssembleField = lambda node: (f"Answer_{node.idx}", QMetaType.Type.QString)
        # all_fields = self.ApplyToNodes(AssembleField)

        if self.verbose:
            print("### Assembling fields for all questions and containers.")

        self.data_provider.addAttributes(
            [QgsField(f"classification", QMetaType.Type.QString)] \
            + [QgsField(f"Answer_{step}", QMetaType.Type.QString) \
               for step in self.steps] \
            )
        self.layer.updateFields()  # feed changes on the vector layer to the datasource

        # convenience function, see below
        self.field_index_lookup = lambda field_label: \
            self.layer.fields().indexFromName(field_label)

        if self.verbose:
            print("\t...done.")


    def CladeContainers(self):
        # assemble clade containers
        # there is a hierarchy in the "T1"/"T2" headers
        # but it is not that strict:
        #    - There are T1 with no T2
        #    - There are T1 with exactly one T2 (possibly extra info)
        #    - There are questions under a T1 but outside any of the T2
        # This function assesses this clade structure (via string structure)
        #     and creates the right containers.

        if self.verbose:
            print("### Creating containers...")
        self.containers = {}
        self.containers["root"] = self.form_config.invisibleRootContainer()
        self.containers["root"].clear()

        AddInfoText(parent = self.containers["root"], text = self.meta["Titel"])

        self.tabs = list(sorted(set([GetTab(k) for k in self.clades.keys()])))
        for nr, tab in enumerate(self.tabs):
            parent = self.containers["root"]

            if self.verbose:
                print("\tcreating container for ", tab, self.clades.get(tab, ""))

            self.containers[tab] = \
                QgsAttributeEditorContainer(name = f"Deel {nr+1}", parent = parent)

            # use tabs
            self.containers[tab].setType(Qgis.AttributeEditorContainerType(1))
            # self.containers[tab].setHorizontalStretch(100)
            # self.containers[tab].setVerticalStretch(100)

        for extra_tab in ["besluit"]:
            self.containers[extra_tab] = \
                QgsAttributeEditorContainer(name = extra_tab, parent = self.containers["root"])

            # use tabs
            self.containers[extra_tab].setType(Qgis.AttributeEditorContainerType(1))


        if self.verbose:
            print("\t...done.")


    def FormConfigPreparation(self):
        # prepare form configuration

        if self.verbose:
            print("### Adjusting form configurator...")


        if self.verbose:
            print("\t...done.")


    def FormNodeForms(self):
        # For each question, assemble a form in a container
        # and append it to the clade container

        if self.verbose:
            print("### Form blocks per question:")

        # store refs to the question elements
        self.question_blocks = {}

        for idx, node in self.GetAllNodes().items():
            # prepare question

            field_idx = self.field_index_lookup(f"Answer_{idx}")
            question = QuestionBlock(
                idx, node, field_idx = field_idx,
                parent = self.containers[GetTab(node.clade)]
            )

            # widget style
            widget = question.ConstructValueMapWidget()
            self.layer.setEditorWidgetSetup(field_idx, widget)
            self.form_config.setLabelOnTop(field_idx, False)

            # assemble the form block
            if self.verbose:
                print(idx, " deploying question ", node["Q"])
            question.DeployQuestionBlock()

            # keep reference
            self.question_blocks[idx] = question

        if self.verbose:
            print("\t...done.")


    def SetDynamicVisibilities(self):
        pass
        # (1) hide CLADES/QUESTIONS if they were not reached yet
        # (2) hide if question in the same tab led to an answer
        # (3) add checkboxes to SHOW COMPLETED clades

        # store the expressions we gather on the way
        tab_expressions = {tab: [] for tab in self.tabs}
        question_expressions = {idx: [] for idx in self.GetAllNodes().keys()}

        possible_solutions = {}

        ## (1) hide CLADES/QUESTIONS if they were not reached yet
        # which node directs where
        # which answers lead to which tab?
        for idx, node in self.GetAllNodes().items():
            # this_tab = GetTab(node.clade)
            for answer_idx, answer in node["A"].items():

                next_key = answer["next_step"]
                if next_key not in self.keys():
                    solution_candidate = QGT.get_classification(answer)
                    if possible_solutions.get(solution_candidate, None) is None:
                        possible_solutions[solution_candidate] = []

                    # store possible determination solutions
                    possible_solutions[solution_candidate] \
                        .append(f"(\"Answer_{idx}\" = {answer_idx})")
                    continue

                # found a link to next tab
                target_tab = GetTab(self[next_key].clade)
                if GetTab(node.clade) >= target_tab:
                    # only influence across different tabs
                    continue

                tab_expressions[target_tab].append(f"(\"Answer_{idx}\" = {answer_idx})")


        # set visibility to be dynamically controlled
        for tab, express in tab_expressions.items():
            if len(express) == 0:
                continue

            visexp = QgsExpression(" OR ".join(tab_expressions[tab]))
            self.containers[tab].setVisibilityExpression(QgsOptionalExpression(visexp))


        ## (2) hide if question in the same tab led to an answer
        # prohibit a different question
        # i.e. a different question in the same tab leads to another tub

        # print([k for k in self.keys()])
        for idx, node in self.GetAllNodes().items():
            this_tab = GetTab(node.clade)
            successor_indices = [] # qn in same tab which list idx as a successor
            null_indices = [] # independent questions leading to different path
            for idx2, node2 in self.GetCladeMembers(this_tab).items():
                if idx2 == idx:
                    continue # skip self


                # hide question if it is the successor of ANY other one
                new_successor = None
                for answer_idx2, answer2 in node2["A"].items():
                    next_key = answer2["next_step"]

                    if (next_key == idx):
                        new_successor = answer_idx2

                # per default, other questions must be null
                if new_successor is not None:
                    successor_indices.append((idx2, new_successor))
                else:
                    null_indices.append(idx2)

            # after all others in the tab were checked
            # (A) no successors? -> display only if other qns are NULL
            if len(successor_indices) == 0:
                question_expressions[idx] \
                    .append(" AND ".join([f"(\"Answer_{idx2}\" IS NULL)" \
                                          for idx2 in null_indices]))
            else:
            # (B) yes this is a successor? -> display only when selected
                question_expressions[idx] \
                    .append(" OR ".join([f"(\"Answer_{idx2}\" = {successor})" \
                                          for idx2, successor in successor_indices]))

        ## hide excluded questions
        for idx in self.GetAllNodes().keys():
            # continue # TODO not working correctly
            visexp = QgsExpression(" AND ".join(question_expressions[idx]) \
                                  )
            self.question_blocks[idx].container.setVisibilityExpression(QgsOptionalExpression(visexp))
            # YOLO.


        ## show classification if reached
        print(possible_solutions)
        for nr, (solution_key, express) in enumerate(possible_solutions.items()):
            solution_container = QgsAttributeEditorContainer( \
                name = f"Classification {nr}",
                parent = self.containers["besluit"]
                )

            AddInfoText(solution_container, solution_key, "classification: ")

            # visible
            visexp = QgsExpression(" OR ".join(express))
            solution_container.setVisibilityExpression(QgsOptionalExpression(visexp))

            # deploy container
            self.containers["besluit"].addChildElement(solution_container)


        visexp = QgsExpression(" OR ".join([" OR ".join(express) \
                              for express in possible_solutions.values()]) \
                              )
        self.containers["besluit"].setVisibilityExpression(QgsOptionalExpression(visexp))

        # TODO dynamically set field `classification`
        # e = QgsExpression( 'Column * 3' )
        # e.prepare( vl.pendingFields() )
        #
        # for f in vl.getFeatures():
        #     f[idx] = e.evaluate( f )
        #     vl.updateFeature( f )
        #
        # vl.commitChanges()



    def FinishFormCreation(self):
        # update and save

        # add all tabs
        for tab in self.tabs:
            self.containers["root"].addChildElement(self.containers[tab])

        self.containers["root"].addChildElement(self.containers["besluit"])

        # connect the form configuration
        self.layer.updateFields()
        self.layer.setEditFormConfig(self.form_config)

        # update/add layer and write form
        self.layer.updateFields()
        self.project.project.addMapLayer(self.layer)
        self.project.Save()



# provider and layer registries from memory
# TODO atexit?


class QuestionBlock(object):
    # a single block for a question
    # (essentially just a wrapper for uniform style)

    def __init__(self, idx, node,
                 field_idx, parent):
        self.idx = idx
        self.node = node
        self.field_idx = field_idx
        self.parent = parent

        self.label = f"Question {idx}"

        self.next_steps = [answer["next_step"] for answer in self.node.GetAnswers()]


    def ConstructValueMapWidget(self):
        # create a value map widget from the possible answers

        # the value map links the display text in the attribute editor
        # to the index of the answer which was chosen (internal data)
        value_map = {"map": \
            {f"[{int(answer_idx): 3.0f}] " + answer["name"][:100]: answer_idx \
             for answer_idx, answer in self.node["A"].items()} \
        }

        return QgsEditorWidgetSetup('ValueMap', value_map)


    def DeployQuestionBlock(self):
        # question container
        self.container = QgsAttributeEditorContainer( \
            name = self.label,
            parent = self.parent
            )

        # question text
        print(self.node["Q"])

        AddInfoText(self.container, self.node["Q"], "Q:   ")


        # print(f"\n___ +{self.idx}+ ________________")
        # answers = node.GetAnswers()
        # print([list(answer.keys()) for answer in answers])
        # ['name', 'next_step', 'classification', 'bwk_code', 'subkey', 'remark']

        # answer text previews
        for answer_idx, answer in self.node["A"].items():
            ans = answer["name"]
            rows = len(ans)//100+1
            for row in range(rows):
                AddInfoText(self.container, \
                            ans[row*100:(row+1)*100], \
                            f"[{int(answer_idx): 3.0f}] " if row == 0 else f"    " \
                            )

        # answer dropdown
        answer_form_element = QgsAttributeEditorField( \
            name = f"Answer_{self.idx}", \
            idx = self.field_idx, \
            parent = self.container \
           )
        self.container.addChildElement(answer_form_element)


        # add info text
        for info in self.node.get("I", []):
            AddInfoText(self.container, info)


        # collapse container
        # visexp = QgsExpression(f"\"Answer_{self.node.idx}\" IS NOT NULL")
        # print(dir(self.container)) # TODO NOT FOUND
        # self.container.setCollapsedExpression(QgsOptionalExpression(visexp))

        # deploy container
        self.parent.addChildElement(self.container)



if __name__ == "__main__":
    project = QgisProject("heide.qgs")
    data_layers = AddDataLayers(project)


    heidesleutel = QGT.DecisionTree.from_csv("./sleutels/Heidesleutel_digitaal_werkversie.csv", sep = ",", header = 4)

    # AddRootButton(project, heidesleutel)


    heidesleutel_form = QgisFormDecisionTree( \
        tree = heidesleutel,
        project = project, \
        name = "heidesleutel", \
        verbose = True \
        )

    # heidesleutel_form.FinishFormCreation()

    # extent = (5.38128, 51.07422 , 5.40922, 51.08951) # EPSG:4326, WGS84?

