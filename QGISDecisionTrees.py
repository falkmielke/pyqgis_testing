#!/usr/bin/env python3

__author__ = "Falk Mielke (falk.mielke@inbo.be)"
__date__ = 20250408


"""
I feel like my Bachelor's years have returned :)
Thank you for the programming task.
"""

#_______________________________________________________________________________
#                 TODO
#_______________________________________________________________________________
# Work never ends.
"""
- Other constructor functions (e.g. "DecisionTree.read_googledocs(google_fileid)")
- DO NOT use merged cells, please!
- Qn 4 has only one answer (and it is a loop)
- valid filename in PrintGraph()
- print_answer() hardening
- XML (nested) file format: save and restore

"""

#_______________________________________________________________________________
#                 Libraries
#_______________________________________________________________________________
# We build on the concepts of others.

from collections.abc import Callable # for typestrings
import re as RE # regular expressions
import numpy as NP
import pandas as PD
from difflib import SequenceMatcher # substring matching

"""
## Reference Collection:
(i.e. things I googled on the way, to refresh or investigate)
- class functions for alternative constructors https://stackoverflow.com/a/141777
- dropna for certain columns https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dropna.html
- common substrings of descriptions: https://stackoverflow.com/questions/58585052/find-most-common-substring-in-a-list-of-strings
- sorting dict by values: https://stackoverflow.com/a/613218
- graphviz and pydot: https://medium.com/data-science/graph-visualisation-basics-with-python-part-iii-directed-graphs-with-graphviz-50116fb0d670
- typestrings: https://docs.python.org/3/library/typing.html
"""


#_______________________________________________________________________________
#                 Little Helpers
#_______________________________________________________________________________
# some general functions to make our lives easier

# get a subset of rows by type
RowsByType = lambda df, typ, typcol = "type": df.loc[df[typcol].values == typ, :]

def CutString(string, length):
    if len(string) <= length-5:
        return string
    else:
        return(string[:length-5] + "[...]")

def ExtractClades(data):
    # data contains "chapters", clades, subgroups.
    # These should better be added as a category.
    # Storing in a dict <- {"clade_idx": "label"}

    # assemble clades as a dictionary
    clades = {}
    data["clade"] = NP.nan
    data["clade"] = data["clade"].astype(str)

    current = str(0)
    current_t1 = None

    clades[current] = ""


    for idx, row in data.iterrows():
        # print(idx, current, clades[current])
        if row["type"] == "T1":
            # add a new entry to clade
            current = current_t1 = str(row["step"])
            clades[current] = row["name"].strip()
            # print("T1", current, clades[current])
            continue

        if row["type"] == "T2":
            # add extra clade description
            current = current_t1 + ">>"+ str(row["step"])

            clades[current] = clades[current_t1] + " // " + CutString(row["name"], 60).strip()
            # print("    T2", current, current_t1, clades[current])
            continue

        # link the row to a clade
        data.loc[idx, "clade"] = current

    return data, clades



#_______________________________________________________________________________
#                 The Tree
#_______________________________________________________________________________
# This dict-derived object will carry the structure of all the decision nodes.

class DecisionTree(dict):

    @classmethod
    def from_csv(cls, csv_path: str, *args, **kwargs):
        # load a decision tree from a csv
        # passes arguments through to pandas.read_csv

        # read meta info
        meta = None
        header = kwargs.get("header", 0)
        if header > 0:
            meta = PD.read_csv(csv_path, index_col = 0, nrows = header, header = None)
            meta = meta.iloc[:, :1].reset_index(drop = False, inplace = False)
            meta = {r[0]: r[1] for _, r in meta.iterrows()}

        # read data
        data = PD.read_csv(csv_path, *args, **kwargs)

        # lower all column names
        data.rename(columns = {col: col.lower() for col in data.columns}, inplace = True)

        # group into clades
        data, clades = ExtractClades(data)

        # instantiate a DecisionTree and return it.
        return cls(data, meta = meta, clades = clades)


    def __init__(self, data: PD.DataFrame, meta: dict = None, clades: dict = None):
        # builds a tree from a data frame
        # which should have columns:
        #     step, type, name, next_step, classification, bwk_code, subkey, remark

        # store meta info
        self.meta = meta

        # store clades
        self.clades = clades

        # lower all column names
        data.rename(columns = {col: col.lower() for col in data.columns}, inplace = True)

        # remove spacing rows
        data.dropna(subset = ["step", "type"], inplace = True)

        # data["step"] = data["step"].astype(int) # does not work: things like "12A"
        for col in ["step", "next_step"]:
            # ensure that these are the same data type
            data[col] = [str(val).strip().upper() for val in data[col].values]
        # print(data.sample(3).T)

        # check if all steps have a predecessor
        next_steps = set(data["next_step"].values)
        no_predecessor = set([step for step in data["step"].values \
                          if step not in next_steps \
                          ])
        no_predecessor.remove(data["step"].values[0])

        # adjust some, print warning
        if len(no_predecessor) > 0:
            # remove extra letter
            adjusted_predecessor = []
            for npred in no_predecessor:
                letterless_index = RE.sub(r"\D", "", npred)
                if npred == letterless_index: continue
                missing_links = data["next_step"].values == letterless_index
                data.loc[missing_links, "next_step"] = npred
                adjusted_predecessor.append(f"{letterless_index} -> {npred}")

            print("Found the following loose branches: ", no_predecessor, \
                  ", but adjusted ", adjusted_predecessor)
            # raise IOError("Found the following loose branches: ", no_predecessor)

        # list steps for later reference
        self.steps = list(map(str, NP.unique(sorted(data["step"].values))))

        # create TreeNode's
        for step in self.steps:
            self[step] = TreeNode(self, data.loc[data["step"].values == step])

        # the root node
        self.root = self[min(self.steps)]


    def Print(self):
        # print the whole tree
        for step in self.steps:
            print(f"\n________ {step} ________")
            print(str(self[step]))


    def ApplyToNodes(self, apply_function: Callable[[object], None]):
        # recursively apply a function to all nodes
        results = {}

        def RecursiveApply(tree_node):

            results[tree_node.idx] = apply_function(tree_node)

            for term, child in tree_node.Traverse():
                if not term:
                    # proceed to non-terminal nodes
                    RecursiveApply(child)

        RecursiveApply(self.root)

        return(results)


    def PrintGraph(self, filename):
        # TODO check valid filename

        import pydot as DOT

        graph = DOT.Dot(graph_type = "digraph")
        q_nodes = []
        t_nodes = []
        edges = []


        def AppendGraph(tree_node):
            # recursively build the graph

            dot_node = DOT.Node(str(tree_node.idx))
            graph.add_node(dot_node)

            children = tree_node.Traverse()
            for term, child in children:
                # print(term, child)
                if not term:
                    child_node = AppendGraph(child)
                    q_nodes.append(child_node)
                    edges.append(DOT.Edge(dot_node, child_node))

                else:
                    term_node = DOT.Node(get_classification(child),
                                         style = "filled",
                                         fillcolor = "lightgreen")
                    t_nodes.append(term_node)
                    edges.append(DOT.Edge(dot_node, term_node))

            return dot_node


        # start at the root
        AppendGraph(self.root)

        for node in set(q_nodes):
            graph.add_node(node)

        for node in set(t_nodes):
            graph.add_node(node)

        for edge in set(edges):
            graph.add_edge(edge)

        graph.write_svg(filename)


    def GetAllNodes(self):
        # return all nodes
        return {tnidx: self[tnidx] \
                for tnidx in self.steps \
                }


    def GetCladeMembers(self, clade_idx):
        # return all nodes by clade
        assert clade_idx in self.clades.keys()
        return {tnidx: node \
                for tnidx, node in self.GetAllNodes().items() \
                if node.clade == clade_idx \
                }

    def GetAllClades(self):
        # return all nodes, organized in clades
        return {self.GetCladeMembers(clade_idx) \
                for clade_idx in self.clades.keys() \
                }


    def __get__(self, key):

        # see if the key is in the steps
        if key not in self.steps:
            raise IOError(f"The node {str(key)} is not found in the list of tree nodes.\n (Might be data type related; try `tree[str(key)])`")

        return super(DecisionTree, self).__get__(key)



#_______________________________________________________________________________
#                 The Node
#_______________________________________________________________________________
# The nodes are what makes a tree, not the branches (Confucius).

class TreeNode(dict):

    def __init__(self, tree, rows):
        # print(rows)
        # rows contain the following types:
        #     "T1", "T2": new clade/subgroup/category; to be removed
        #     "Q": that is the question
        #     "A": answers (usually more than one)
        #     "I": extra info

        # reference to the tree
        self.tree = tree

        # skip clade-defining category rows
        non_T = lambda tp: tp[0] != "T"
        rows = rows.loc[list(map(non_T, rows["type"].values)), :]

        # the index ("step")
        self.idx = rows.iloc[0, :]["step"]
        self.types = NP.unique(rows["type"].values).astype(str)
        self.clade = rows.iloc[0, :]["clade"]

        ### [T]: type/topic/theme (can be T1, T2, ...)
        ### and [I]: extra information
        for typ in self.types:
            if typ in ["A", "Q"]:
                # answers and questions are special
                continue

            # this is about "T"/headers and "I"/info
            self[str(typ)] = \
                    [", ".join(map(str, RowsByType(rows, t_type)["name"].values)) \
                         for t_type in self.types \
                         if t_type[0] == typ ] \
            # print(self[str(typ)])

        # print(self.get("I", None))
        # add remarks on the question line
        remarks = [rem.strip() for rem in RowsByType(rows, "Q")["remark"] \
                   if str(rem).lower() != "nan"]
        if len(remarks) > 0:
            self["I"] = [info for info in [*self.get("I", []), *list(remarks)] \
                         if info != ""]

        ### [A]: Possible Answers
        self["A"] = {i: row.astype(str).to_dict() \
                     for i, row in RowsByType(rows, "A").iterrows()}
        # ['name', 'next_step', 'classification', 'bwk_code', 'subkey', 'remark']


        for answer in self.GetAnswers():
            answer["node_link"] = self

        # print([(is_terminal(ans), is_subkey(ans)) for ans in self["A"].values()])
        # print(self.idx, CommonString(self["A"]))

        ### [Q]: What is the question?
        if all(RowsByType(rows, "Q")["name"].isna()):
            self["Q"] = CommonString(self["A"])
        else:
            self["Q"] = "/".join(RowsByType(rows, "Q")["name"].values)

    def GetCladeLabel(self):
        # get the clade for this node
        clade = self.tree.clades.get(self.clade, None)
        return clade

    def GetAnswers(self):
        # get all the answers... at least for this node.

        if len(self["A"]) > 0:
            return [v for v in self["A"].values()]
        else:
            return "42"


    def Traverse(self):
        # facilitate moving along the tree
        # returns a tuple with (is_terminal, node|classification)

        children = []
        for answer in self.GetAnswers():
            if is_terminal(answer):
                # either append
                children.append((True, answer))
            else:
                children.append((False, self.tree[answer["next_step"]]))

        return children


    def ExtraInfo(self):
        # print extra info
        return self.get("I", None)


    def __str__(self, print_remark = False):
        # create a meaningful text for this node

        if "T" in self.keys():
            out.append(", ".join(self["I"]))
        out = ["Q: " + self["Q"]]
        if "I" in self.keys():
            out.append("\t"+", ".join(self["I"]))
        for answer in self["A"].values():
            proceed = answer["next_step"]

            if proceed not in self.tree.keys():
                # some more extensive tests (e.g. "19")
                proceed = "*" + proceed

            if is_subkey(answer):
                proceed = "*" + answer["subkey"]
            elif is_terminal(answer):
                proceed = "*" + get_classification(answer)

            if print_remark and (not isna(answer, "remark")):
                remark = "(" + answer["remark"] + ")"
            else:
                remark = ""

            # concatenate output
            out.append(f"""\t{proceed}\t <---\t{answer['name']}{remark}""")

        return ("\n".join(out))



#_______________________________________________________________________________
#                 The Answers
#_______________________________________________________________________________
# There will always be more than one correct answer.
# Here some functions to handle them.

def print_answer(answer):
    # TODO must be an answer! (otherwise, `step` will not be found)

    out = f"[{answer['step']}] {answer['name']} --> "

    if is_terminal(answer):
        out += get_classification(answer)
    else:
        out += answer['next_step']

    return out

def get_remark(answer):
    print(answer["remark"])
    return answer["remark"]

def isna(answer, key):
    return str(answer[key]) == "nan"

def is_terminal(answer):
    # note that this does not flag the "SLEUTEL" divergences
    # print(answer["next_step"], type(answer["next_step"]))
    if isna(answer, "next_step"):
        return True
    return str(answer["next_step"]) not in answer["node_link"].tree.keys()

def is_subkey(answer):
    return not isna(answer, "subkey")

def get_classification(answer):
    return (" / ".join([label for label in [
        answer["next_step"],
        answer["subkey"],
        answer["classification"],
        answer["bwk_code"]
    ] if label.lower() != 'nan']))

def CommonString(answers):
    # get the common part of a set of answer descriptions ("name")

    names = [ans["name"].lower() for ans in answers.values()]
    substring_counts={}

    # https://stackoverflow.com/questions/58585052/find-most-common-substring-in-a-list-of-strings
    for i in range(0, len(names)):
        for j in range(i+1,len(names)):
            string1 = names[i].strip()
            string2 = names[j].strip()
            match = SequenceMatcher(None, string1, string2).find_longest_match(0, len(string1), 0, len(string2))
            matching_substring=string1[match.a:match.a+match.size]
            if(matching_substring not in substring_counts):
                substring_counts[matching_substring]=1
            else:
                substring_counts[matching_substring]+=1

    # print(substring_counts)

    # scoring:
    scores = {key: NP.sqrt(len(key))*len(key.split(" ")) * value / len(answers) \
              for key, value in substring_counts.items() \
              if (value > 1) \
              # and (len(key.split(" ")) > 1) \
              and (len(key) >= 8) \
              }
    sorted_scores = sorted(scores.items(), key=lambda item: item[1])
    # print(sorted_scores)

    if len(scores) > 0:
        candidate = sorted_scores[-1][0]
        return(candidate.strip())

    # good chance that the first word is instructive...
    name_split = names[0].split(" ")
    return(" ".join(name_split[:min([4, len(name_split)])]) + "...")


#_______________________________________________________________________________
#                 Mission Control
#_______________________________________________________________________________
# Every program has to start somewhere.

if __name__ == "__main__":
    dt = DecisionTree.from_csv("./sleutels/Heidesleutel_digitaal_werkversie.csv", sep = ",", header = 4)
    # print(dt.root)
    # dt.Print()
    # print ("\n____\n".join(map(str, [tr[1] for tr in dt.root.Traverse()])))
    # dt.PrintGraph("heidesleutel.svg")

    # print("\n".join(
    #     [f"{k}: {v}" \
    #      for k, v \
    #      in dt.ApplyToNodes(lambda node: node.ExtraInfo()).items() \
    #     ]))

    # for answer in dt.root.GetAnswers():
    #     get_remark(answer)

    print("\n".join([f"{k}:\t{v}" for k, v in dt.clades.items()]))
    dt.GetCladeMembers('50>60A')
