import json
import random
import re
import sys
import networkx as nx
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QMessageBox

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from collections import deque
from mainUI import Ui_StoryXpander


import ollama

from LLM_worker import *
from FinalVars import *



def number_to_letters(n):
    result = ""
    while n >= 0:
        result = chr(n % 26 + ord('A')) + result
        n = n // 26 - 1
    return result

#CLASS FOR THE THREADING



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        #Create the UI
        self.ui = Ui_StoryXpander()
        self.ui.setupUi(self)

        # This will be used for the graph
        self.graph = nx.DiGraph()

        #This wil lbe used for the canvas and replace the QFrame we've set up previously
        self.canvas = FigureCanvas(Figure(figsize=(8,8)))

        #Add commands for the canvas, like pan, zoom in/out and clicking

        #Will be userd for the dragging
        self.drag_start = None

        #Will be used for the current selected node
        self.current_selected_node = None

        #This is for the zoom in and zoom out
        self.canvas.mpl_connect("scroll_event", self.zoom_in_canvas)

        #This is for when the user clicks with both left click or right click
        self.canvas.mpl_connect("button_press_event", self.on_press_canvas)

        #This is for when the user moves the mouse on the canvas
        self.canvas.mpl_connect("motion_notify_event", self.on_motion_canvas)

        #This is for when the user relases the mouse button
        self.canvas.mpl_connect("button_release_event", self.on_release_canvas)


        #This add the Graph widget to the QFrame place without any margins
        self.layout_graph = QVBoxLayout(self.ui.nodes_frames)
        self.layout_graph.setContentsMargins(0,0,0,0)
        #self.layout_graph.addWidget(self.toolbar)
        self.layout_graph.addWidget(self.canvas)

        #this gives Axes to draw on
        self.ax = self.canvas.figure.add_subplot(111)

        # This is the root node, the whole graph will consist on this node
        self.rootnode = None

        # Layer list, it'll help with the Y shenanigans
        self.layers = {}

        # Layer count to keep track of the layers
        self.layer = 1

        # This will store each text giving the "letter" and then it'll provide the text, this will be used for the graph
        self.texts = {}

        # This will store the position of each node that will be used in the DRAW Function
        self.pos = {}

        # This will be used to generate the letter names based on the function number_to_letters
        self.counter = 0

        self.initial_node_creation(from_node="1",
                                   from_text=f"\"Alright! I got this, I found a new cave that's not in my maps, Adventure awaits!\" "
                                             f"said Lyara as she entered the cave, ready to explore the unknowness of the cave and bring"
                                             f" with her knowledge and treasure.She already imagines herself back in the guild showing of"
                                             f" her new discoveries and treasures, she would be the talk of the town! \"I'll show Bardus that I am a worthy"
                                             f" element in their guild!\"- Lyara said as she moved forward towards some stairs leading down.",
                                   to_node="2",

                                   to_text=f"After Climbing a set of stairs Lyara finds herself at where she was first when she started descending the cave stairs"
                                           f"\"This was incredible\" Said Lyara as she starts running towards town ready to tell the tales of her adventure"
                                           f"in the unknown cave. \"I'm sure they will name the cave my name after hearing my tales!\" Thought Lyara\n"
                                           f"THE END. ")



        #The logic of the buttons
        #The button connect
        self.ui.btn_expand.clicked.connect(self.handle_expand_button)

        self.ui.btn_export.clicked.connect(self.export_to_twine)
        #This just draws the graph, This is only being called here because it's the start of the program
        self.draw()

    """This function will add a new node to the graph, it'll get a new letter based on the counter and given the text from the user, if the text doesnt' exist just create some dummy text"""
    def _new_node(self, node_x, node_y, text = None) -> str:
        name = number_to_letters(self.counter)
        self.counter += 1

        if text is None:
            self.texts[name] = f"Dummy text for node {name}"
        else:
            self.texts[name] = f"{text}"

        self.pos[name] = (node_x, node_y)

        return name

    """This function will add a connecting between two nodes say for an example node 1 and 2 makes 1 - 2, This function will probably be used only once to create the initial graph,"""

    def initial_node_creation(self, from_node, from_text, to_node, to_text):
        # adds an edge to the main graph
        self.graph.add_edge(from_node, to_node)

        self.rootnode = from_node
        # The graph will start with nodes in (X = 0.5 and Y = -1) and (X = 0.5 and Y = -1) #MIGHT CHANGE LATER
        self.pos[from_node] = (0.5, 0)
        self.pos[to_node] = (0.5, -1)

        self.layers[self.layer] = from_node
        self.layer += 1
        self.layers[self.layer] = to_node

        # add the text to the nodes (Will be used when clicked over)
        self.texts[from_node] = f"{from_text}"
        self.texts[to_node] = f"{to_text}"

        self.add_text_to_information_box(f"Created node {from_node} to node {to_node}")
        self.ui.expand_nodes_list.addItem(f"{from_node}->{to_node}")

    """This function will contact the llm and then generate the given  """

    def getLLmText(self, start, end):
        to_return = {}
        text_from_llm = ollama.generate(model='eldoria-story',
                                        prompt=f"Node 1: {self.texts[start]} Node 2: {self.texts[end]}")

        text_from_llm = text_from_llm["response"]

        #THIS IS WHY WE CAN'T HAVE NICE THINGS
        #because the llm is unreliable we need to make sure things are returned in the right form:
        # First let's strip Markdown code blocks: ```json\n...\n``` or ```\n...\n```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text_from_llm, re.DOTALL)
        json_str = ""
        if match:
            json_str = match.group(1)
        else:
            #This is actually pure json
            json_str = text_from_llm.strip()

        #Before parsing the Text might have some issues with the texts so let's Sanitize this before we all go mad here

        #replace smart quotes with normal quotes
        json_str = json_str.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")

        # Strip any trailing commas or excessive whitespace
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*\]", "]", json_str)

        #Next let's try parsing this and if there's an error we'll catch it:
        try:
            to_return = json.loads(json_str)
        except json.JSONDecodeError:
            return ERROR_JSON_PARSING

        #Ok After parsing sometimes this LLM forgets that 4 IS NOT 6 or 5 IS NOT 6 soo we need to make sure that the amount of keys returned is exactly 6!
        #Since we're at it why not just add another secure verification just for the kicks of it:
        if not isinstance(to_return, dict):
            return ERROR_NOT_DICT

        # Now we'll check if the key are exactly as that final variable we created up at the top
        if set(to_return.keys()) != EXPECTED_LLM_KEYS:
            print(f"GOT: {to_return.keys()}")
            return ERROR_NUMBER_KEYS

        #Alright after all those verifications just return the dictionary
        return to_return

    """This function will organize the Y spacing between nodes"""

    def recalculate_layers(self, root):
        """Recalculate Y layers from the root node using BFS (longest path wins)"""
        # Root is always layer 0
        self.layers = {root: 0}

        # visited = set()
        queue = deque([root])
        while queue:
            current = queue.popleft()
            current_layer = self.layers[current]

            for neighbor in self.graph.successors(current):
                proposed_layer = current_layer + 1
                if neighbor not in self.layers or proposed_layer > self.layers[neighbor]:
                    self.layers[neighbor] = proposed_layer
                    queue.append(neighbor)

        # Update positions based on layers
        for node, layer in self.layers.items():
            x = self.pos[node][0]  # keep current x
            y = -layer * 1.0  # e.g., spacing 1.0 per layer
            self.pos[node] = (x, y)

    """With the help of LLM this will subdivide the given start and end node. In theory what will happen is, we'll use the power of llm to generate the needed nodes"""

    def subdivide(self, start, end, llmText):
        """
        giving the start and end node we can subdivide the passage into 6 nodes (including start and end)
        creating the configuration start - A - B/C - D - end
        then add the passages to the main Story dictionary

        Now create intermediate nodes from the algorithm
        since We're following the structure:
                        1
                        |
                        A
                       / \
                      B   C
                       \ /
                        D
                        |
                        2
        we want to keep this structure within our algorithm
        """

        text_a = llmText["A"]
        text_b = llmText["B"]
        text_c = llmText["C"]
        text_d = llmText["D"]

        start_node_pos = self.pos[start]

        xPos = start_node_pos[0]

        node_spacing = 0.50

        # TODO: CHECK IF THIS RANDOM VALUES ARE GOOD AS THEY ARE
        #Check if that random value can work like the way it is, maybe i need to make some changes
        if start_node_pos[0] < 0.5:
            xPos = start_node_pos[0] - random.random()
        elif start_node_pos[0] > 0.5:
            xPos = start_node_pos[0] + random.random()

        a = self._new_node(node_x=xPos, node_y=start_node_pos[1] - node_spacing, text=text_a)
        b = self._new_node(node_x=xPos - node_spacing, node_y=start_node_pos[1] - node_spacing * 2, text=text_b)
        c = self._new_node(node_x=xPos + node_spacing, node_y=start_node_pos[1] - node_spacing * 2, text=text_c)
        d = self._new_node(node_x=xPos, node_y=start_node_pos[1] - node_spacing * 3, text= text_d)

        # The nodes have been created, now let's create the edges
        self.graph.add_edge(start, a)
        self.graph.add_edge(a, b)
        self.graph.add_edge(a, c)
        self.graph.add_edge(b, d)
        self.graph.add_edge(c, d)
        self.graph.add_edge(d, end)

        # Don't manually adjust Y Anymore
        self.recalculate_layers(self.rootnode)

        #This will add the information to the information box
        self.add_text_to_information_box(f"Subdivided {start} -> {end} into {start} → {a} → {b}/{c} → {d} → {end}")

        #Add the allowed nodes to the list of nodes to expand
        self.ui.expand_nodes_list.addItem(f"{b}->{d}")
        self.ui.expand_nodes_list.addItem(f"{c}->{d}")

        # The connection exists now we remove that edge
        self.graph.remove_edge(start, end)

        self.draw()

        return True

    """This function will draw the graph in a way that can be visualized by the user. We will use matplot """

    def draw(self):

        #This clears the previous plot
        self.ax.clear()

        #Draw the graph with the given Axes

        node_colors = []
        for node in self.graph.nodes:
            if node == self.current_selected_node:
                node_colors.append("Orange") # this is in case a node is selected with right click
            else:
                node_colors.append("skyblue") #This is default color

        nx.draw(
            self.graph,
            pos=self.pos,
            ax=self.ax,
            with_labels=True,
            width=2,
            node_color=node_colors,
            node_size=1000,
            font_size=12,
            font_weight='bold',
            arrows=True
        )

        #self.ax.set_title("Story Graph")
        self.ax.set_axis_off()
        self.canvas.draw_idle()


    #This function is just to make my life easier, just in case I need to modify the way I insert the text later >_>
    def add_text_to_information_box(self, text):
        pos_init = QTextCursor(self.ui.information_box.document())
        pos_init.setPosition(0)
        self.ui.information_box.setTextCursor(pos_init)
        self.ui.information_box.insertPlainText(f"{text}\n")

    #This function will be called once the user clicks the button to expand
    def handle_expand_button(self):
        selected_items = self.ui.expand_nodes_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(
                self,
                "No node Selected!",
                "Please select a node from the list before expanding."
            )
            return

        #Select the node
        selected_item = selected_items[0]
        node_name = selected_item.text()

        #Gives the first and the second node
        nodes_split = node_name.split("->")

        #This is going to be for the thread when the user clicks on the button
        self.thread = QThread()
        self.worker = SubDivideWorker(nodes_split[0], nodes_split[1], self.getLLmText)
        self.worker.moveToThread(self.thread)

        self.set_buttons_toggle(False)
        #self.ui.btn_expand.setDisabled(True)
        #self.ui.btn_export.setDisabled(True)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_subdivide_finished)
        self.worker.error.connect(self.on_subdivide_error)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.thread.deleteLater)
        self.worker.done.connect(self.worker.deleteLater)
        self.worker.done.connect(lambda: self.set_buttons_toggle(True))

        self.add_text_to_information_box("-------------------------------------------------")
        self.add_text_to_information_box(f"Expanding nodes {node_name}")
        self.add_text_to_information_box(f"Please Wait a bit")

        self.thread.start()

    def on_subdivide_finished(self, start, end, llm_text):
        # this was success so inject pre-generated text into subivided logic
        self.subdivide(start, end, llm_text)

        selected_item = self.ui.expand_nodes_list.selectedItems()[0]
        row = self.ui.expand_nodes_list.row(selected_item)

        # Remove selected item from the list
        self.ui.expand_nodes_list.takeItem(row)

        # clear the selection just to prevent some unusual shenanigans
        self.ui.expand_nodes_list.clearSelection()

    def on_subdivide_error(self, int_error):
        if int_error is ERROR_JSON_PARSING:
            # Its empty, therefore there was an error.
            QMessageBox.warning(
                self,
                "Error Parsing!",
                "There was an error while Parsing Json, Please try again"
            )
            return None

        if int_error is ERROR_NOT_DICT:
            # Its empty, therefore there was an error.
            QMessageBox.warning(
                self,
                "Error Dictionary!",
                "Result Isn't a Dictionary, Please try again"
            )
            return None

        if int_error is ERROR_NUMBER_KEYS:
            # Its empty, therefore there was an error.
            QMessageBox.warning(
                self,
                "Error Keys!",
                "Resulted Keys Aren't the same!, Please try again"
            )
            return None

        self.add_text_to_information_box(f"Error Expanding Nodes!")

    def set_buttons_toggle(self, state):
        self.ui.btn_expand.setEnabled(state)
        self.ui.btn_export.setEnabled(state)


    #CANVAS FUNCTIONS
    def zoom_in_canvas(self, event):
        base_scale = 1.2
        ax = self.ax

        #get current canvas limits
        x_lim = ax.get_xlim()
        y_lim = ax.get_ylim()

        #Get mouse position in axis coords

        x_data = event.xdata
        y_data = event.ydata

        if x_data is None and y_data is None:
            #the user is outside the canvas limits so just ignore it
            return

        #zoom factor
        scale_factor = base_scale if event.button == 'up' else 1 / base_scale

        #New Limits
        new_x_lim = [
            x_data - (x_data - x_lim[0]) * scale_factor,
            x_data + (x_lim[1] - x_data) * scale_factor,
        ]

        new_y_lim = [
            y_data - (y_data - y_lim[0]) * scale_factor,
            y_data + (y_lim[1] - y_data) * scale_factor,
        ]

        ax.set_xlim(new_x_lim)
        ax.set_ylim(new_y_lim)
        self.canvas.draw_idle()

    def on_press_canvas(self, event):
        if event.button == 1 and event.inaxes:  # Left click inside the canvas axes
            self.drag_start = (event.x, event.y)

        elif event.button == 3 and event.inaxes: #Right click inside the canvas axes
            clicked_node = self.get_node_at_position(event)
            if clicked_node:
                text = self.graph.nodes[clicked_node].get("text", "(no text)")
                self.current_selected_node = clicked_node
                self.add_text_to_information_box("-------------------------------------------------")
                self.add_text_to_information_box(f"Node {clicked_node}: {self.texts[clicked_node]}")
                self.draw()

    def on_motion_canvas(self,event):
        if self.drag_start and event.inaxes:
            #The user has the left button on the mouse down and it's dragging inside the canvas
            #Which means there will be cake
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]

            ax = self.ax
            x_lim = ax.get_xlim()
            y_lim = ax.get_ylim()

            scale_x = (x_lim[1] - x_lim[0]) / self.canvas.width()
            scale_y = (y_lim[1] - y_lim[0]) / self.canvas.height()

            ax.set_xlim(x_lim[0] - dx * scale_x, x_lim[1] - dx * scale_x)
            ax.set_ylim(y_lim[0] + dy * scale_y, y_lim[1] + dy * scale_y)

            self.drag_start = (event.x, event.y)
            self.canvas.draw_idle()

    def on_release_canvas(self,event):
        self.drag_start = None


    def get_node_at_position(self, event):
        #This function will return the closest node within a tolerance radius.
        if not hasattr(self, 'pos'):
            return None

        click_x, click_y = event.xdata, event.ydata

        min_distance = 0.4 #Better change this number if it's too high or too low for the closest radius
        closest_node = None

        for node, (x,y) in self.pos.items():
            dist = ((x - click_x) ** 2 + (y - click_y) ** 2 ) ** 0.5
            if dist < min_distance:
                min_distance = dist
                closest_node = node

        return closest_node

    def export_to_twine(self):
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


